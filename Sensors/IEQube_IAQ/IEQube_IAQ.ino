/*CUNDALL BLACKBOX PM10, PM2.5, TVOC, CO2 SENSOR

   All sensors require 5V supply.
   Please ensure XBee's have a logic/voltage shifter when connected to 5V supply otherwise they'll die!
   PM sensor has large current draw (~200mA), ensure adequate power supply is used
   PLEASE ENSURE YOU SELECT THE CORRECT ARDUINO BEFORE UPLOADING SKETCH
   Calibrate TVOC sensor to Arduino voltage for each different power supply (see Parse function for details)

   On Pro-Micro only the following pins can be used for RX: 8, 9, 10, 11, 14 (MISO), 15 (SCK), 16 (MOSI).

  TODO: Calibration routine for PMs?
        Calibration routine for CO2
        Store lowest voltage reading into EEPROM so survives reset (i.e. long term calibration)

  Changelog:
  03/08/2016 - EW - Added Checksum routine to CO2 reading
  04/08/2016 - EW - Amended CO2 sensor low and high bit processing to correct incorrect data sheet. Values of high bit is incrementing
                    down when low bit is negative - add 1 to high bit on negative low bits to correct.
  26/09/2016 - EW - Added CO2 sensor back into PM, VOC and Particulate routine.
  10/02/2017 - EW - VOC sensor cleanest air value Ro now written to EEPROM to survive power off
*/

#include <Arduino.h>
#include <SPI.h>
#include <Wire.h>
#include <EEPROM.h>
#include <VoltageReference.h>
#include <stdio.h>                //standard input/output library
#include <XBee.h>                 //Allows use of the Xbee API
#include <SoftwareSerial.h>       //Allows reprogramming of TX/RX pins

/*-----( Declare Constants and Pin Numbers )-----*/
#define VREF_EEPROM_ADDR (E2END - 2)    // sets the storage area to the very end of the EEPROM
#define DEFAULT_REFERENCE_CALIBRATION (1111410)
#define TGS2602_SENSOR A0               //define the analog input pin for VOC sensor
#define xbRX 16                         //Define Xbee softwareserial Receive pin
#define xbTX 3                          //Define Xbee softwareserial Transmit pin
#define pmRX 9                          //Define PMsensor softwareserial Transmit pin
#define pmTX 21                         //Define PMsensor softwareserial Receive pin (not actually used)
#define co2TX 7                         //Define CO2sensor softwareserial Transmit pin
#define co2RX 10                        //Define CO2sensor softwareserial Receive pin
#define SENSORTYPE 4                    //4 = TVOC,PM2.5,PM10,CO2; 3 = CO2; 2 = VOCL & Lux; 1 = Temp, Hum, Lux; 0 = TVOC,PM2.5,PM10
#define LENGTH 32
#define READ_DELAY (30000)              //delay between readings in milliseconds

/*-----( Declare Global Variables )-----*/
//***************************VOC Sensor Variables*****************************
int address = VREF_EEPROM_ADDR;
int eeAddress = 256;      // EEPROM location for Ro value - somewhere in the middle!
uint32_t calibration = 0;
float Ro1 = 20000;      // Sensor resistance in fresh air for calibrated reading of VOC
float Rs;               // Sensor resistance in specified VOC calculated from Vout - CURRENT READING
int RL = 1020;          // Load resistance in Ohms (measured resistance of potentiometer)
float rs_ro = 1.0;      // Initialise as default in clean air

unsigned int co2ppm = 0;      //define CO2 value of the air detector module
byte cmd[9] = {0xFF, 0x01, 0x86, 0x00, 0x00, 0x00, 0x00, 0x00, 0x79};

word PM2_5Value = 0;
word PM10Value = 0;

//used to hold results in 1 ASCII string for passing to Pi
char buff[16];

/*Set the RX/TX pins*/
SoftwareSerial xbnss(xbRX, xbTX);
SoftwareSerial pmss(pmRX, pmTX);
SoftwareSerial co2ss(co2RX, co2TX);

/*Instantiate an xbee*/
XBee xbee = XBee();
/* This is the XBee broadcast address. Should be replaced with the address of the coordinator */
XBeeAddress64 Broadcast = XBeeAddress64(0x0013A200, 0x40E7CC0C);
//XBeeAddress64 Broadcast = XBeeAddress64(0x00000000, 0x0000ffff);
ZBTxStatusResponse txStatus = ZBTxStatusResponse();

/*Instantiate a vRef object*/
VoltageReference vRef;

/*Setup routine runs once at startup - Loads last stored calibration value from EEPROM*/
void setup() {

  Serial.begin(9600);
  delay(10000);
  Serial.println("Sensor warming up - please wait...");
  delay(10000);
  pinMode(pmRX, INPUT);
  pinMode(pmTX, OUTPUT);
  pinMode(xbRX, INPUT);
  pinMode(xbTX, OUTPUT);
  pinMode(co2RX, INPUT);
  pinMode(co2TX, OUTPUT);
  xbee.setSerial(xbnss);
  Serial.println("Serial initialisation all done!");
  vRef.begin();
  load(address);
  Serial.println("Enter 4 digit calibration voltage in next 5 seconds...");
  delay(5000);
  //If calibration value is waiting, read it and deal with it
  if (Serial.available() > 0) {
    parse();
  }
  Serial.println("Using existing value");

  Serial.println("Retrieving cleanest air reading from EEPROM");
  EEPROM.get( eeAddress, Ro1);
  Serial.print("EEPROM value is: ");
  Serial.println(Ro1);
  Serial.println("Ro1 set to EEPROM value");
  Serial.print("new Ro1 is:");
  Serial.println(Ro1);
  if (Ro1 != Ro1) {
    Serial.println("Ro1 set to default 10000");
    Ro1 = 10000;
  }
  co2ss.begin(9600);
  pmss.begin(9600);
  xbnss.begin(9600);
}

/*Main loop - reads on delay time and parses serial input if received*/
void loop() {
  co2ss.listen();
  delay(100);
  Serial.println("Reading CO2 sensor");
  /*Read CO2 sensor*/
  int CO2ppm = readCO2();
  Serial.print("C02 = "); Serial.print(CO2ppm); Serial.println("ppm");
  //  Serial.println("Reading PM sensor");

  /* Read PM sensor*/
  pmss.flush();
  pmss.listen();
  Serial.println("Reading PM sensor");
  readPMvalues();

  Serial.println("Reading VOC sensor");
  /*Read VOC sensor*/
  double analog = readConcentration();
  int vcc = vRef.readVcc();
  //Serial.print("Vcc is ");
  //Serial.print(vcc);
  //Serial.print("mV, analog pin voltage is ");
  float vout = (analog / 1023 * vcc );
  //Serial.print(vout);
  //Serial.println("mV");
  rs_ro = calcConcentration(vout, vcc);
  Serial.print("rs_ro = "); Serial.println(rs_ro);

  /*uses sprintf to pass results to Xbee as a string in comma separated format described below)*/
  xbnss.listen();
  sprintf(buff, "%d,%d.%d,%d,%d,%d", int(SENSORTYPE), int(rs_ro), frac(rs_ro), int(PM2_5Value), int(PM10Value), int(co2ppm));
  Serial.println(buff);
  /*Send the data and wait for response*/
  ZBTxRequest zbtx = ZBTxRequest(Broadcast, (uint8_t *)buff, strlen(buff));
  xbee.send(zbtx);
  Serial.println("Packet Sent!");
  getDeliveryStatus();
  delay(READ_DELAY);
}

void readPMvalues()
{
  PM2_5Value = 0;
  PM10Value = 0;
  delay(1250);
  //For PM sensor, check the data is complete before passing to other functions
  char buf[LENGTH];
  pmss.readBytes(buf, LENGTH);
  if (buf[0] == 0x42 && buf[1] == 0x4d) {
    PM2_5Value = transmitPM2_5(buf);  //count PM2.5 value of the air detector module
    PM10Value = transmitPM10(buf);    //count PM10 value of the air detector module
  }
}

/*Calculates Rs_Ro ratio for passing to Pi*/
float calcConcentration(float Vout, int vcc)
{
  float Rs_Ro_ratio = 0;
  Rs = ResistanceCalc(Vout, vcc);
  //Serial.print("current Ro1= ");
  //Serial.print(Ro1);
  //Serial.println(" Ohms");
  Rs_Ro_ratio = Rs / Ro1;
  return Rs_Ro_ratio;
}

/*Takes average of 50 readings on the VOC sensor to try to improve accuracy*/
double readConcentration()
{
  int readnumber = 50;
  int i;
  double analog = 0;
  for (i = 0; i < readnumber; i++) {
    analog += analogRead(TGS2602_SENSOR);
    delay(10);
  }
  analog = analog / readnumber;
  return analog;
}

/****************** ResistanceCalc ****************************************
  Input:   Vout - converted adc value
  Output:  the calculated sensor resistance
  Remarks: The sensor and the load resistor forms a voltage divider. Given the voltage across the load resistor and
  its resistance, the resistance of the sensor can be derived.
************************************************************************************/

float ResistanceCalc(float Vout, float Vcc)
{
  Rs = (((Vcc - Vout) / Vout) * RL);
  if ( Rs > Ro1) {
    Ro1 = Rs;
    Serial.print("New freshest value! Writing this Ro to EEPROM:");      //used after calibration incase air wasn't as fresh as you thought
    Serial.println(Ro1);
    EEPROM.put(eeAddress, Ro1);
    Serial.println("Done!");
  }
  else {
    Ro1 = Ro1;
  }
  return Rs;
}
/* this function prints the characters of a c string one at a time
  without any formatting to confuse or hide things */

void printbuffer(char *buffer) {
  while (*buffer) {
    Serial.write(*buffer++);
  }
}

/* this little function will return the first two digits after the decimal
  point of a float as an int to help with sprintf() (won't work for negative values)
  the .005 is there for rounding. */

int frac(float num) {
  return ( ((num + .005) - (int)num) * 100);
}

/*Loads the calibration value from EEPROM*/
uint32_t load(uint16_t address) {
  calibration = DEFAULT_REFERENCE_CALIBRATION;
  byte msb = EEPROM.read(address);
  byte mid = EEPROM.read(address + 1);
  byte lsb = EEPROM.read(address + 2);
  calibration = (((long) msb) << 16) | ((mid << 8) | ((lsb & 0xFF) & 0xFFFF));
  if (calibration == 16777215L) {
    Serial.println("No calibration value stored into EEPROM, using default");
    calibration = DEFAULT_REFERENCE_CALIBRATION;
  } else {
    Serial.print("Read from EEPROM address ");
    Serial.print(address);
    Serial.print(" calibration value ");
    Serial.println(calibration);
  }
  return calibration;
}

/*Saves the calibration value into EEPROM*/
void save(uint16_t address, uint32_t calibration) {
  EEPROM.write(address, calibration >> 16);
  EEPROM.write(address + 1, calibration >> 8);
  EEPROM.write(address + 2, calibration & 0xFF);
  Serial.println("Saved calibration value into EEPROM");
}

/*Parses serial in order to calibrate the INPUT voltage of the arduino on a given power supply
  To use, read the actual voltage across the arduino when connected to power, then type the
  value in mV into the serial and press enter - only needs to be done once, then stored to EEPROM*/

void parse() {
  char c = Serial.read();
  char* buffer = new char[5];
  uint8_t i = 0;
  if (isalpha(c)) {
    Serial.println("Please enter measured circuit voltage in mV");
    Serial.flush();
    return;
  } else if (isdigit(c)) {
    while (isdigit(c)) {
      buffer[i++] = c;
      c = Serial.read();
    }
    buffer[i++] = '\0';
    long voltage = atol(buffer);
    Serial.print("Calibrating for Vcc ");
    Serial.print(voltage);
    Serial.println("mV");
    calibration = vRef.calibrate(voltage);
    save(address, calibration);
    Serial.print("Calibration value is ");
    Serial.println(calibration);
    Serial.print("Real bandgap voltage is ");
    Serial.print((calibration + (ANALOG_MAX_VALUE / 2)) / ANALOG_MAX_VALUE);
    Serial.println("mV");
    vRef.begin(calibration);
  } else {
    Serial.flush();
    return;
  }
}

void getDeliveryStatus(void)
{
  /* for Xbee after sending a tx request, we expect a status response
    wait up to half second for the status response */

  if (xbee.readPacket(500)) {
    // got a response!

    // should be a znet tx status
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
    Serial.println("No TX Response - Check wiring on both Xbees");
  }
}

//For PM sensor, check the data is complete before passing to other functions
//Seems to not be working correctly
//char checkValue(char *thebuf, char leng)
//{
//  char receiveflag = 0;
//  int receiveSum = 0;
//  char i = 0;
//
//  for (i = 0; i < leng; i++)
//  {
//    receiveSum = receiveSum + thebuf[i];
//  }
//
//  if (receiveSum == ((thebuf[leng - 2] << 8) + thebuf[leng - 1] + thebuf[leng - 2] + thebuf[leng - 1])) //check the serial data
//  {
//    receiveSum = 0;
//    receiveflag = 1;
//  }
//  return receiveflag;
//}

// transmit PM2.5 Value to Arduino
int transmitPM2_5(char *thebuf)
{
  word PM2_5Val;
  PM2_5Val = ((thebuf[6] << 8) + thebuf[7]); //count PM2.5 value of the air detector module
  Serial.print("PM2.5 = ");
  Serial.print(PM2_5Val);
  Serial.println("ug/m3");
  return PM2_5Val;
}

// transmit PM10 Value to PC
int transmitPM10(char *thebuf)
{
  word PM10Val;
  PM10Val = ((thebuf[8] << 8) + thebuf[9]); //count PM10 value of the air detector module
  Serial.print("PM10 = ");
  Serial.print(PM10Val);
  Serial.println("ug/m3");
  return PM10Val;
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
      co2ppm = (responseHigh + 1) * 256 + responseLow;
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
