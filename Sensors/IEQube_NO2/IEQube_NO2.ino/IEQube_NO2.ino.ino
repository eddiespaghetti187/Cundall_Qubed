/*CUNDALL IEQUBE NO2 SENSOR

   Datasheet: 
   NO2 sensor requires 3.3V supply.
   VISUALLY CHECK CABLES BEFORE ALTERING CODE!
   PLEASE ENSURE YOU SELECT THE CORRECT ARDUINO BEFORE UPLOADING SKETCH

   On Pro-Micro only the following pins can be used for RX: 8, 9, 10, 11, 14 (MISO), 15 (SCK), 16 (MOSI).

  TODO: Calibration routine
  See datasheet for command refernces and calibration method

  Changelog:
  27/04/2017 - File created
  */
  
#include <Arduino.h>
#include <stdio.h>                //standard input/output library
#include <string.h>
#include <SoftwareSerial.h>       //Allows reprogramming of TX/RX pins
#include <XBee.h>                 //Allows use of the Xbee API

#define xbTX 8                    //Define Xbee softwareserial Transmit pin (Connect to Din/RX on XBee)
#define xbRX 9                    //Define Xbee softwareserial Receive pin (Connect to Dout/TX on XBee)
#define no2TX 7                   //Define CO2sensor softwareserial Transmit pin
#define no2RX 10                  //Define CO2sensor softwareserial Receive pin
#define SENSORTYPE 5              //4 = NO2; 3 = CO2; 2 = TVOC & Lux; 1 = Temp, Hum, Lux; 0 = TVOC,PM2.5,PM10
#define LENGTH 32
#define READ_DELAY (30000)        //delay between readings in milliseconds
#define INPUT_SIZE 63             //buffer length for NO2 sensor response

/*-----( Declare Global Variables )-----*/

char buff[16];                //used to hold results in 1 ASCII string for passing to Pi
int responseArray[11];       //holds response of NO2 sensor reading call
unsigned int no2ppm = 0;      //define CO2 value of the air detector module

/*Set the RX/TX pins*/
SoftwareSerial xbnss(xbRX, xbTX);
SoftwareSerial no2ss(no2RX, no2TX);

/*Instantiate an xbee*/
XBee xbee = XBee();
/* This is the XBee broadcast address. Should be replaced with the address of the coordinator */
XBeeAddress64 Broadcast = XBeeAddress64(0x0013A200, 0x40E832B0);
//XBeeAddress64 Broadcast = XBeeAddress64(0x00000000, 0x0000ffff);
ZBTxStatusResponse txStatus = ZBTxStatusResponse();

/*Setup routine runs once at startup*/
void setup() {
  Serial.begin(9600);
  Serial.println("Sensor warming up - please wait...");
  delay(5000);
  xbnss.begin(9600);
  xbee.setSerial(xbnss);
  no2ss.begin(9600);
  pinMode(no2RX, INPUT);
  pinMode(no2TX, OUTPUT);
  pinMode(xbRX, INPUT);
  pinMode(xbTX, OUTPUT);
  Serial.println("Initialisation all done!");
}

/*Main loop - reads on delay time and parses serial input if received*/
void loop() {
  Serial.println("Reading NO2 sensor");
  readSens();
  Serial.println("Readings received!");
  int no2ppm = responseArray[1];
  Serial.print(no2ppm); Serial.println("ppm");
  int temp = responseArray[2];
  Serial.print(temp); Serial.println("degC");
  int hum = responseArray[3];
  Serial.print(hum); Serial.println("%");
  
/*uses sprintf to pass results to Xbee as a string in comma separated format described below)*/
  xbnss.listen();
  sprintf(buff, "%d,%d,%d,%d", int(SENSORTYPE), int(no2ppm), int(temp), int(hum));
  Serial.println(buff);
  ZBTxRequest zbtx = ZBTxRequest(Broadcast, (uint8_t *)buff, strlen(buff));
  xbee.send(zbtx);
  Serial.println("Packet Sent!");
  getDeliveryStatus();
  
  delay(READ_DELAY);
}

/* Sends a carriage return to the sensor to call for a reading. Sensor returns the following
  SN[XXXXXXXXXXXX],PPB[0:999999],TEMP[-99:99],RH[0:99],RawSensor[ADCCount],TempDigital,RHDigital,Day[0:99],
  Hour[0:23],Minute[0:59],Second[0:59] as a string

  String is split by commas, then parsed, converted into integers, before assigning to responseArray
  */

int readSens()
{
  no2ss.listen();
  no2ss.write('\r');
  delay(4000);
  char input[INPUT_SIZE];
  byte size = no2ss.readBytes(input, INPUT_SIZE);
  input[size] = 0;
  Serial.println(input);
  char* reading = strtok(input, ",");
  int index = 0;
  int intreading = atoi(reading);
  index++;
  
  while (index < 11 )  
  {
    reading = strtok(NULL, ",");
    int intreading = atoi(reading);
    responseArray[index] = intreading;
    index++;
  }
  return responseArray;
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

