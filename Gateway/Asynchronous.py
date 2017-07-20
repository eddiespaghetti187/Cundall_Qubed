#! /usr/bin/python

import math
import json
import serial
import httplib, urllib
import os.path
import time
import Queue
import csv
from xbee import ZigBee
from collections import defaultdict

import packethandler

PORT = '/dev/ttyAMA0'
BAUD_RATE = 9600

packetQueue = Queue.Queue()

##Thingspeak interface constants
user_ID = 'cundall'         #User ID used to create Thingspeak account - VITAL
user_key = ''      #write API key - found at https://thingspeak.com/account, allows read & write operations - VITAL

field1name = 'Dry Bulb Temperature - *C'
field2name = 'Relative Humidity - %'
field3name = 'Illuminance - Lux'
field4name = 'TVOC - ug/m3'
field5name = 'PM2.5 - ug/m3'
field6name = 'PM10 - ug/m3'
field7name = 'CO2 - ppm'
field8name = 'NO2 - ppm'

headers = {"Content-type": "application/x-www-form-urlencoded","Accept": "text/plain"}  
conn = httplib.HTTPConnection("api.thingspeak.com:80")    

#Regressed sensitivity curve constants for Rs/Ro to ppm from sensor manufacturer's datasheet.
#C7H8Curve = [37.22590719,2.078062258]                      
#H2S_Curve = [0.05566582614,-2.954075758]                   
#C2H5OH_Curve = [0.5409499131,-2.312489623]                  
NH3_Curve = [1052.3,-3377.3,4031.2,-2103.9,374.82,22.863]   
NH3_MMass = 17.03 #(g/mol)
Mvolume = 22.414

#global variables with initial values
CO2 = 400
floatHum = 50
floatTemp = 20.0
floatTVOC = 0
hum = 50
intCO2 = 400
intLight = 0
intNO2 = 0
intPM10 = 0
intPM2_5 = 0
light = 0
PM10 = 0
PM2_5 = 0
temp = 20.0
tvoc = 0.9

# Open serial port
xbeeSerial = serial.Serial(PORT, BAUD_RATE)

# read calibration files
Calib_CSV=csv.DictReader(open('Calib_CSV.csv','rb'))

#receives packet data and places it into the queue
def packet_received(data):
    packetQueue.put(data, block = False)

# Create API object, which spawns a new thread
xbee = ZigBee(xbeeSerial, callback=packet_received)

# main thread
xbeeSerial.flushInput()            #clear serial buffer

while True:
    try:
        time.sleep(0.1)
        if packetQueue.qsize() > 0:
            newPacket = packetQueue.get_nowait()
            print 'newPacket received'
            print 'queue length is now', packetQueue.qsize()
            source = newPacket['source_addr_long'].encode('hex')
            incoming = newPacket['rf_data']
            if incoming[0] == "0":	#PM+VOC Qube
                sensortype = 0
                stamp,floatTVOC,PM2_5,PM10 = packethandler.unpacket(incoming, sensortype)
                print stamp,floatTVOC,PM2_5,PM10                
                print " " 
            elif incoming[0] == "1":	#Temp+Hum+Lux Qube
                sensortype = 1
                stamp,floatHum,floatTemp,intLight = packethandler.unpacket(incoming, sensortype)
                print stamp,floatHum,floatTemp,intLight
                calibration.calibrate_1(Calib_CSV,source,sensortype,floatTemp,floatHum,intLight)
                print " " 
            elif incoming[0] == "2":	#Temp,Hum,Lux,CO2 Qube
                sensortype = 2
                print "THLCO2 Qube - doesn't exist yet!"
                print " " 
            elif incoming[0] == "3":	#CO2 Qube
                sensortype = 3
                stamp,CO2 = packethandler.unpacket(incoming,sensortype)
                print stamp,CO2                            
                print " " 
            elif incoming[0] == "4":	#PM,VOC,CO2 Qube
                sensortype = 4
                stamp,floatTVOC,intPM2_5,intPM10,intCO2 = packethandler.unpacket(incoming,sensortype)
                print stamp,floatTVOC,intPM2_5,intPM10,intCO2
                print " " 
            elif incoming[0] == "5":	#NO2,Temp,Hum Qube
                sensortype = 5
                stamp,intNO2,floatTemp,floatHum = packethandler.unpacket(incoming,sensortype)
                print stamp,intNO2,floatTemp,floatHum,
                print " " 

    except KeyboardInterrupt:
        break

# halt() must be called before closing the serial port to ensure proper thread shutdown
xbee.halt()
xbeeSerial.close()
