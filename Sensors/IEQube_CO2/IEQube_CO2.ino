/*CUNDALL BLACKBOX CO2 SENSOR

   Datasheet: http://www.futurlec.com/Datasheet/Sensor/MH-Z14.pdf
   CO2 sensor requires 5V supply and doesn't play well with others!
   VISUALLY CHECK CABLES BEFORE ALTERING CODE!
   please ensure XBee's have a logic/voltage shifter when connected to 5V supply otherwise they'll die!
   PLEASE ENSURE YOU SELECT THE CORRECT ARDUINO BEFORE UPLOADING SKETCH

   On Pro-Micro only the following pins can be used for RX: 8, 9, 10, 11, 14 (MISO), 15 (SCK), 16 (MOSI).

  TODO: Calibration routine
  See datasheet for command refernces and calibration method

  Changelog:
  03/08/2016 - EW - Added Checksum routine
  04/08/2016 - EW - Amended sensor low and high bit processing to correct incorrect data sheet. Values of high bit is incrementing
                    down when low bit is negative - add 1 to high bit on negative low bits to correct.
*/

#include <Arduino.h>
#include <SPI.h>
#include <Wire.h>
#include <VoltageReference.h>
#include <stdio.h>                //standard input/output library
#include <XBee.h>                 //Allows use of the Xbee API
#include <SoftwareSerial.h>       //Allows reprogramming of TX/RX pins

#define xbTX 8                    //Define Xbee softwareserial Transmit pin (Connect to Din/RX on XBee)
#define xbRX 9                    //Define Xbee softwareserial Receive pin (Connect to Dout/TX on XBee)
#define co2TX 7                   //Define CO2sensor softwareserial Transmit pin
#define co2RX 10                  //Define CO2sensor softwareserial Receive pin
#define SENSORTYPE 3              //3 = CO2; 2 = TVOC & Lux; 1 = Temp, Hum, Lux; 0 = TVOC,PM2.5,PM10
#define LENGTH 32
#define READ_DELAY (30000)        //delay between readings in milliseconds

/*-----( Declare Global Variables )-----*/
unsigned int co2ppm = 0;      //define CO2 value of the air detector module
byte cmd[9] = {0xFF, 0x01, 0x86, 0x00, 0x00, 0x00, 0x00, 0x00, 0x79};

//used to hold results in 1 ASCII string for passing to Pi
char buff[16];

/*Set the RX/TX pins*/
SoftwareSerial xbnss(xbRX, xbTX);
SoftwareSerial co2ss(co2RX, co2TX);

/*Instantiate an xbee*/
XBee xbee = XBee();
/* This is the XBee broadcast address. Should be replaced with the address of the coordinator */
XBeeAddress64 Broadcast = XBeeAddress64(0x0013A200, 0x414E526F);
//XBeeAddress64 Broadcast = XBeeAddress64(0x00000000, 0x0000ffff);
ZBTxStatusResponse txStatus = ZBTxStatusResponse();

/*Setup routine runs once at startup*/
void setup() {
  Serial.begin(9600);
  delay(15000);
  Serial.println("Sensor warming up - please wait...");
  delay(15000);
  co2ss.begin(9600);
  xbnss.begin(9600);
  xbee.setSerial(xbnss);
  pinMode(co2RX, INPUT);
  pinMode(co2TX, OUTPUT);
  pinMode(xbRX, INPUT);
  pinMode(xbTX, OUTPUT);
  Serial.println("Initialisation all done!");
  //If calibration value is waiting, read it and deal with it
}

/*Main loop - reads on delay time and parses serial input if received*/
void loop() {
  co2ss.listen();
  delay(100);
  Serial.println("Reading CO2 sensor");
  /*Read CO2 sensor*/
  int CO2ppm = readCO2();
  Serial.print("C02 = "); Serial.print(CO2ppm); Serial.println("ppm");

  /*uses sprintf to pass results to Xbee as a string in comma separated format described below)*/
  xbnss.listen();
  sprintf(buff, "%d,%d", int(SENSORTYPE), int(CO2ppm));
  Serial.println(buff);
  ZBTxRequest zbtx = ZBTxRequest(Broadcast, (uint8_t *)buff, strlen(buff));
  xbee.send(zbtx);
  Serial.println("Packet Sent!");
  getDeliveryStatus();

  delay(READ_DELAY);
}

// this function prints the characters of a c string one at a time
// without any formatting to confuse or hide things

void printbuffer(char *buffer) {
  while (*buffer) {
    Serial.write(*buffer++);
  }
}

// for Xbee after sending a tx request, we expect a status response
// wait up to half second for the status response

void getDeliveryStatus(void)
{
  if (xbee.readPacket(500)) {
    // got a response!

    if (xbee.getResponse().getApiId() == ZB_TX_STATUS_RESPONSE) {
      xbee.getResponse().getZBTxStatusResponse(txStatus);
      // get the delivery status, the fifth byte
      if (txStatus.getDeliveryStatus() == SUCCESS) {
        // success.  time to celebrate
        Serial.println("Packet received!\n");
      } else {
        // the remote XBee did not receive our packet. is it powered on?
        Serial.println("Remote Xbee did not receive the packet\n");
      }
    }
  } else if (xbee.getResponse().isError()) {
    Serial.print("Error reading packet.  Error code: ");
    Serial.println(xbee.getResponse().getErrorCode());
  } else {
    // local XBee did not provide a timely TX Status Response -- should not happen
    Serial.println("No TX Response, check wiring on both Xbees (Pro-Micro SoftwareSerial RX limited to certain pins)");
  }
}

// For CO2 sensor, ping sensor with read command, pass to buffer and process response

int readCO2()
{
  char response[9];
  co2ss.write(cmd, 9);
  delay(1500);
  co2ss.readBytes(response, 9);
  Serial.println(response[8], DEC);

    int i = 0;
  while (i < 9)
  {
    Serial.print(response[i], DEC);
    Serial.print(" ");
    i++;
  }
  Serial.println("");
  Serial.println("");
  
  if (getCheckSum(response) == response[8]) {
    Serial.println("Checksum OK!");
    int responseHigh = (int) response[2];
    int responseLow = (int) response[3];
    if  (responseLow >= 0) {
      Serial.println("Low bit is positive");
      Serial.print("current highbit = ");
      Serial.println(responseHigh);
      Serial.print("current lowbit = ");
      Serial.println(responseLow);
      co2ppm = responseHigh * 256 + responseLow;
      return co2ppm;
    } else {
      Serial.println("Low bit is negative");
      Serial.print("current highbit = ");
      Serial.println(responseHigh);
      Serial.print("current lowbit = ");
      Serial.println(responseLow);
      co2ppm = (responseHigh+1) * 256 + responseLow;
      return co2ppm;
    }
  } else {
    Serial.println("Checksum failed - sensor error!");
    co2ppm = -1;
    return co2ppm;
  }
}

char getCheckSum(char *packet)
{
  char i, checksum;
  for (i = 1; i < 8; i++)
  {
    checksum += packet[i];
  }
  checksum = 0xff - checksum;
  checksum += 1;
  Serial.print("checkSum = ");
  Serial.println(checksum, DEC);
  return checksum;
}

