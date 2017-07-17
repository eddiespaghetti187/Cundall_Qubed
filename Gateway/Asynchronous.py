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

#receives packet data and places it into the queue
def packet_received(data):
    packetQueue.put(data, block = False)
    print 'queue length is',
    print packetQueue.qsize()

#creates a timestamp for log purposes only - NEED TO UPDATE TO SEND TIMESTAMP TO THINGSPEAK WITH DATA
def timestamp():
    stamp = time.strftime("%a, %d %b %Y %H:%M:%S ",time.localtime(time.time()))
    return stamp

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
            incoming = newPacket['rf_data']
            if incoming[0] == "0":
                sensortype = 0
                print "PM & VOC Qube"
                floatTVOC,PM2_5,PM10 = packethandler.unpacket(incoming, sensortype)
                print floatTVOC,PM2_5,PM10                
            elif incoming[0] == "1":
                sensortype = 1
                print "THL Qube"
                floatHum,floatTemp,intLight = packethandler.unpacket(incoming, sensortype)
                print floatHum,floatTemp,intLight
            elif incoming[0] == "2":                                        
                sensortype = 2
                print "TVOC & Lux Qube - sensor doesn't exist!"
            elif incoming[0] == "3":
                sensortype = 3
                print "CO2 Qube"
                CO2 = packethandler.unpacket(incoming,sensortype)
                print CO2                            
            elif incoming[0] == "4":
                sensortype = 4
                print "PM, VOC & CO2 Qube"
                floatTVOC,intPM2_5,intPM10,intCO2 = packethandler.unpacket(incoming,sensortype)
                print floatTVOC,intPM2_5,intPM10,intCO2
            elif incoming[0] == "5":
                print "NO2 Qube"
                sensortype = 5
                intNO2,floatTemp,floatHum = packethandler.unpacket(incoming,sensortype)
                print intNO2,floatTemp,floatHum
    except KeyboardInterrupt:
        break

# halt() must be called before closing the serial port to ensure proper thread shutdown
xbee.halt()
xbeeSerial.close()