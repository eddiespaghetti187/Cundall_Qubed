
/*CUNDALL BLACKBOX TEMPERATURE, HUMIDITY, PRESSURE, ILLUMINANCE SENSOR

   All sensors require 3.3V supply.
   XBee's can be safely connected directly to 3.3V Arduino.
   PLEASE ENSURE YOU SELECT THE CORRECT ARDUINO BEFORE UPLOADING SKETCH

   On Pro-Micro only the following pins can be used for RX: 8, 9, 10, 11, 14 (MISO), 15 (SCK), 16 (MOSI).

  TODO: Calibration routine
        Atm value passing to XBee
        Sleep routine for powering from battery
*/

#include <Wire.h>
#include <Adafruit_Sensor.h>      //Adafruit library (needed for TSL)
#include <Adafruit_BME280.h>
#include <Adafruit_TSL2561_U.h>   //TSL2561 light sensor library
#include <stdio.h>                //standard input/output library
#include <XBee.h>                 //Allows use of the Xbee API
#include <SoftwareSerial.h>       //Allows reprogramming of TX/RX pins

#define xbTX 8                    //Define Xbee softwareserial Transmit pin (Connect to Din/RX on XBee)
#define xbRX 9                    //Define Xbee softwareserial Transmit pin (Connect to Din/RX on XBee)
#define SENSORTYPE 1              //3 = CO2; 2 = TVOC & Lux; 1 = Temp, Hum, Lux; 0 = TVOC,PM2.5,PM10
#define BME_SCK 15
#define BME_MISO 14
#define BME_MOSI 16
#define BME_CS 10
#define READ_DELAY (30000)        //delay between readings in milliseconds

/*WIRING:: Ard pin5(xbRX)->XBee(Tx/Dout), Ard pin6(xbTX)->XBee(Rx/Din))*/

long int readtime = 60000 * 0.5;         //replace second number with desired read interval in minutes

//Setup a TSL261 instance
Adafruit_TSL2561_Unified tsl = Adafruit_TSL2561_Unified(TSL2561_ADDR_FLOAT, 2561);

//Setup a BME280 instance
Adafruit_BME280 bme(BME_CS, BME_MOSI, BME_MISO,  BME_SCK);

//used to hold results in 1 ASCII string for passing to Pi
char buff[64];

/*Set the RX/TX pins*/
SoftwareSerial xbnss(xbRX, xbTX);

/*Instantiate an xbee*/
XBee xbee = XBee();
/* This is the XBee broadcast address. Should be replaced with the address of the coordinator */
XBeeAddress64 Broadcast = XBeeAddress64(0x0013A200, 0x414E526F);

//XBeeAddress64 Broadcast = XBeeAddress64(0x00000000, 0x0000ffff);
ZBTxStatusResponse txStatus = ZBTxStatusResponse();

void setup() {
  //start serial
  Serial.begin(9600);
  delay(15000);
  xbnss.begin(9600);
  xbee.setSerial(xbnss);
  Serial.println("Xbee Initialization all done!");
 
  /*Initialise the Temp, Hum, Pressure sensor*/
  Serial.println(F("BME280 test"));
  if (!bme.begin()) {
    Serial.println("Could not find a valid BME280 sensor, check wiring!");
    while (1);
  }

  /* Initialise the Lux sensor */
  if (!tsl.begin())
  {
    Serial.println("No Lux Sensor detected ...");
    while (1);
  }
  configureSensor();
  Serial.println("Sensor OK");
}

void loop() {

  /* Get a new sensor event for light sensor*/
  sensors_event_t event;
  tsl.getEvent(&event);

  float temp = bme.readTemperature();
  Serial.print("Temperature = ");
  Serial.print(temp);
  Serial.println(" *C");

  float atm = (bme.readPressure() / 100.0F);
  Serial.print("Pressure = ");
  Serial.print(atm);
  Serial.println(" hPa");

  float humid = bme.readHumidity();
  Serial.print("Humidity = ");
  Serial.print(humid);
  Serial.println(" %");

  /* Display the results (light is measured in lux) */
  if (event.light)
  {
    /*uses sprintf to pass results as a string in comma separated format described below)*/
    int lightLevel = event.light;
    sprintf(buff, "%d,%d.%d,%d.%2d,%d\n", int(SENSORTYPE), int(humid), frac(humid), int(temp), frac(temp), int(lightLevel));
    ZBTxRequest zbtx = ZBTxRequest(Broadcast, (uint8_t *)buff, strlen(buff));
    xbee.send(zbtx);
    Serial.println("Packet Sent!");
    Serial.print(lightLevel); Serial.println("lux, ");
    Serial.print(humid);
    Serial.print("%, ");
    Serial.print(temp);
    Serial.println("*C");
    getDeliveryStatus();
  }
  else
  {
    /* If event.light = 0 lux the sensor is either saturated or it's dark. No reliable data could be generated! */
    sprintf(buff, "%d,%d.%d,%d.%2d,NaN\n", int(SENSORTYPE), int(humid), frac(humid), int(temp), frac(temp));
    ZBTxRequest zbtx = ZBTxRequest(Broadcast, (uint8_t *)buff, strlen(buff));
    xbee.send(zbtx);
    Serial.println("Packet Sent!");
    Serial.println("No Lux reading!");
    getDeliveryStatus();
  }

  delay(readtime);

}

void configureSensor(void)
{
  /* You can also manually set the gain or enable auto-gain support */
  // tsl.setGain(TSL2561_GAIN_1X);      /* No gain ... use in bright light to avoid sensor saturation */
  // tsl.setGain(TSL2561_GAIN_16X);     /* 16x gain ... use in low light to boost sensitivity */
  tsl.enableAutoRange(true);            /* Auto-gain ... switches automatically between 1x and 16x */

  /* Changing the integration time gives you better sensor resolution (402ms = 16-bit data) */
  // tsl.setIntegrationTime(TSL2561_INTEGRATIONTIME_13MS);      /* fast but low resolution */
  tsl.setIntegrationTime(TSL2561_INTEGRATIONTIME_101MS);  /* medium resolution and speed   */
  // tsl.setIntegrationTime(TSL2561_INTEGRATIONTIME_402MS);  /* 16-bit data but slowest conversions */

  /* Update these values depending on what you've set above! */
  Serial.println("Gain:Auto Timing:101ms");
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

/*This routine gives info on Xbee packet delivery - check wiring first if something goes wrong*/

void getDeliveryStatus(void)
{
  // after sending a tx request, we expect a status response
  // wait up to a second for the status response
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


