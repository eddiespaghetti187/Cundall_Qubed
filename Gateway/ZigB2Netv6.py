#!/usr/bin/python

#changelog
# v0.3 - included input and output of local JSON file including channel data to avoid crashes on startup when failing to connect
# also improved error handling throughout to improve stability
# need to improve Exception definitions to handle individual exceptions correctly, rather than passing
# v0.4 - included input and output of local JSON file including writekey data to avoid crashes on startup when failing to connect
# added 15 second delay to startup to help ensure network adapters are online before script starts
# improved local file handling (json format channel list and write key list nowused by default)
# v0.5 - added new function for calibrating readings based on csv coefficients
# v0.5.1 - modified CO2 calibration, changing from linear fitting to power fitting
# v0.5.2 - incorporated NO2 sensor (no calibration routine) and added filter to Lux sensor readings so darkness is recorded as 0, not NaN

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

#constants

##ZigBee interface constants
zbport = serial.Serial("/dev/ttyAMA0", baudrate=9600, timeout=1.0)    #Open serial port connected to XBEE
packet_queue = Queue.Queue()

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
headers = {"Content-type": "application/x-www-form-urlencoded","Accept": "text/plain"}  #standard headers for all Thspeak communications
conn = httplib.HTTPConnection("api.thingspeak.com:80")    #standard conn to main Thspeak server - update for personal server

##Regressed sensitivity curves constants for Rs/Ro to ppm from sensor manufacturer's datasheet

#C7H8Curve = [37.22590719,2.078062258]                   	#TGS2602 (0.3;1)( 0.8;10) (0.4;30)
#H2S_Curve = [0.05566582614,-2.954075758]        		#TGS2602 (0.8,0.1) (0.4,1) (0.25,3)
#C2H5OH_Curve = [0.5409499131,-2.312489623]      		#TGS2602 (0.75,1) (0.3,10) (0.17,30)  
NH3_Curve = [1052.3,-3377.3,4031.2,-2103.9,374.82,22.863]	#Ammonia sensitivity curve 
NH3_MMass = 17.03 #(g/mol)
Mvolume = 22.414

#global variables with initial values

hum = 50
temp = 20.0
light = 0
RsRo = 1.00
tvoc = 0.9
CO2 = 400
PM2_5 = 0
PM10 = 0
intPM10 = 0
intPM2_5 = 0
intCO2 = 400
intLight = 0
floatTVOC = 0
floatHum = 50
floatTemp = 20.0
intNO2 = 0

#creates a timestamp for log purposes only - NEED TO UPDATE TO SEND TIMESTAMP TO THINGSPEAK WITH DATA

def timestamp():
    stamp = time.strftime("%a, %d %b %Y %H:%M:%S ",time.localtime(time.time()))
    return stamp

#when message received, puts it in queue for processing
def packet_received(data)
    packet_queue.put(data, block=false)
    print "packet received and queued"

#calculates VOC concentration based on RsRo ratio - see TGS2602 datasheet for details

def TVOCcalc(RsRo):
    x = float(RsRo)
    tvoc = ((NH3_Curve[0]*pow(x,5))+(NH3_Curve[1]*pow(x,4))+(NH3_Curve[2]*pow(x,3))+(NH3_Curve[3]*pow(x,2)+NH3_Curve[4]*x)+NH3_Curve[5])
    if tvoc < 0:
    	tvoc = 0
        print "Rs/Ro= ",RsRo
    	print "= ",tvoc, "ppm"
        conc = 0.00
    else:
        #concentration(mg/m3) = concentration(ppm) X ( molar mass(g/mol) / molar volume(L) )
        print "Rs/Ro= ",RsRo
    	print "= ",tvoc, "ppm"
        conc = round(tvoc*(NH3_MMass/Mvolume),2)
        print "= ",conc,"mg/m^3"
    return conc

#defines parameters to use to create new channels, based on sensor type

def newchannelParams(sensorID,sensortype):
    try:
        if sensortype == "0": #TVOC,PM2.5,PM10
            print "TVOC, PM2.5, PM10 Sensor"
            params = urllib.urlencode({'name': sensorID,'field1': field4name, 'field2':field5name, 'field3':field6name, 'api_key':user_key})
            return params
        elif sensortype == "1": #Temp,Hum,Lux sensor
            print "New Temp, Hum, Lux Sensor"
            params = urllib.urlencode({'name': sensorID,'field1': field1name, 'field2':field2name, 'field3':field3name, 'api_key':user_key})
            return params
        elif sensortype == "2": #TVOC,Lux sensor
            print "New TVOC, Lux Sensor"
            params = urllib.urlencode({'name': sensorID,'field1': field4name, 'field2':field3name, 'api_key':user_key})
            return params
        elif sensortype == "3": #CO2 Sensor
            print "New CO2 Sensor"
            params = urllib.urlencode({'name': sensorID,'field1': field7name, 'api_key':user_key})
            return params
        elif sensortype == "4": #TVOC,PM2.5,PM10,CO2 Sensor
            print "TVOC, PM2.5, PM10, CO2 Sensor"
            params = urllib.urlencode({'name': sensorID,'field1': field4name, 'field2':field5name, 'field3':field6name, 'field4':field7name,'api_key':user_key})
            return params
        elif sensortype == "5": #NO2 Sensor
            print "NO2, Temp, Humidity sensor"
            params = urllib.urlencode({'name': sensorID,'field1': field1name, 'field2':field2name,'field3':field3name,'api_key':user_key})
            return params
        else:
            print "Sensor type is not defined!"
    except:
            print "This shouldn't happen!"

#Defines upload parameters like field names and write key for each type of sensor

def uploadParams(sensortype,WriteKey):
    try:
        if sensortype == "0": #TVOC,PM10,PM2.5
            params = urllib.urlencode({'field1':floatTVOC, 'field2':intPM2_5, 'field3':intPM10, 'api_key': WriteKey})
            return params
        elif sensortype == "1": #Temp,Hum,Lux sensor
            params = urllib.urlencode({'field1':floatTemp, 'field2':floatHum, 'field3':intLight, 'api_key':WriteKey})
            return params
        elif sensortype == "2": #TVOC,Lux sensor
            params = urllib.urlencode({'field1':floatTVOC, 'field2':intLight, 'api_key':WriteKey})
            return params
        elif sensortype == "3": #CO2 sensor
            params = urllib.urlencode({'field1':intCO2, 'api_key':WriteKey})
            return params
        elif sensortype == "4": #TVOC,PM2.5,PM10,CO2 Sensor
            params = urllib.urlencode({'field1':floatTVOC, 'field2':intPM2_5, 'field3':intPM10, 'field4':intCO2, 'api_key': WriteKey})
            return params
        elif sensortype == "5": #NO2,Temp,Hum Sensor
            params = urllib.urlencode({'field1':intNO2, 'field2':floatTemp, 'field3':floatHum, 'api_key': WriteKey})
            return params
        else:
            print "Sensor type is not defined!"
    except Exception:
            print "This shouldn't happen!"

#Create New Thingspeak Channel

def createChannel(sensorID,sensortype):

    try:
        print "creating channel..."
        params = newchannelParams(sensorID,sensortype)
        conn.request("POST", "/channels.json", params, headers)
        response = conn.getresponse()
        print "got response"
        print response.status, response.reason
        if response.status == 200:
            data = response.read()
            json_data = json.loads(data)
            print "Channel created"
            newkey = json_data['id']
            return newkey
        else:
            print "Channel creation failed"
            print response.status
            conn.close()
    except:
        print "Create channel failed - connection probably failed"
        conn.close()

#reads local channel infomation file and returns dictionary of names & ids

def checkLocalChannels():

    with open ('channelList.json') as infile:
        json_data_from_file = json.load(infile)
    list_length = len(json_data_from_file['channels'])
    name_list = [0]*list_length
    id_list = [0]*list_length

    for i in range(0,list_length):
        name_list[i] = json_data_from_file['channels'][i]['name']
        id_list[i] = json_data_from_file['channels'][i]['id']
        i+1

    names_ids = dict(zip(name_list,id_list))
    return names_ids

# parses local Thingspeak write key list

def checkLocalKeyList():

    with open ('writeKeys.json') as infile:
        json_data_from_file = json.load(infile)
    return json_data_from_file

# Downloads existing channel info from Thingspeak on startup

def downloadChannels():

    try:
         params = urllib.urlencode({'api_key': user_key})
         conn.request("GET", "/users/" + user_ID + "/channels.json/", params, headers)
         response =  conn.getresponse()
         print response.status, response.reason
         if response.status == 200:
             print "Got response OK"
             data = response.read()
#            print data
             json_data = json.loads(data)
             conn.close()
             print "writing channel list to local file"
             with open ('channelList.json', 'w') as outfile:
                 json.dump(json_data, outfile, sort_keys = True, indent = 4)
             with open ('channelList.json') as infile:
                 json_data_from_file = json.load(infile)
#                 print json_data_from_file
             list_length = len(json_data_from_file['channels'])
             name_list = [0]*list_length
             id_list = [0]*list_length
             for i in range(0,list_length):
                 name_list[i] = json_data_from_file['channels'][i]['name']
                 id_list[i] = json_data_from_file["channels"][i]["id"]
                 i+1
             print "created ID list"
         else:
             print response.status, response.reason
             conn.close()
    except Exception:
         print "No response - had difficulty communicating with Thingspeak"
         print "Check network connection"
         conn.close()
         pass
    else:
         names_ids = dict(zip(name_list,id_list))
         print "returned list of existing sensors"
         return names_ids


# checks which channels already exist on Thingspeak using userID. 
# If in localDB (local, non-persistent dictionary), returns the existing dictionary without download
# otherwise contacts Thingspeak and downloads list of all existing channels

def checkChannel(sensorID, sensorID_dict):

    print sensorID
    if sensorID in sensorID_dict:
        print "Already have sensorID in local DB"
        return sensorID_dict
    else:
         print "Downloading existing channel information"
    try:
         params = urllib.urlencode({'api_key': user_key})
         conn.request("GET", "/users/" + user_ID + "/channels.json/", params, headers)
         response =  conn.getresponse()
         print response.status, response.reason
         if response.status == 200:
             print "Got response OK"
             data = response.read()
             print data
             json_data = json.loads(data)
             conn.close()
             print "writing channel list to local file"
             with open ('channelList.json', 'w') as outfile:
                 json.dump(json_data, outfile, sort_keys = True, indent = 4)
             with open ('channelList.json') as infile:
                 json_data_from_file = json.load(infile)
                 print json_data_from_file
             list_length = len(json_data_from_file['channels'])
             name_list = [0]*list_length
             id_list = [0]*list_length
             for i in range(0,list_length):
                 name_list[i] = json_data_from_file['channels'][i]['name']
                 id_list[i] = json_data_from_file["channels"][i]["id"]
                 i+1
             print "created ID list"
         else:
             print response.status, response.reason
             conn.close()
    except Exception:
         print "No response - had difficulty communicating with Thingspeak"
         print "Check network connection"
         conn.close()
         pass
    else:
         names_ids = dict(zip(name_list,id_list))
         print "returned list of existing sensors"
         return names_ids

#does a false update of the channel to retrieve the writekey as a single string

def getWriteKey(CHANNEL_ID):
    uploadID = str(CHANNEL_ID)
    try:
        print "getting write key"
        params = urllib.urlencode({'api_key': user_key})
        conn.request("PUT", "/channels/" + uploadID + ".json", params, headers)
        response = conn.getresponse()
        print response.status, response.reason
        if response.status == 200:
            print "got key!"
            data = response.read()
            json_data = json.loads(data)
            apikeys = json_data['api_keys']
            return apikeys
        else:
            print response.status, response.reason
            conn.close()
    except:
        print "Get write key failed - connection probably timed-out"
        conn.close()

def storeWriteKeys(writeKey_dict):
     print "appending write key to local file..."
     json_data = writeKey_dict
#     print "json key data is", json_data
     with open ('writeKeys.json', 'w') as f:
         json.dump(json_data,f, indent=4)
     print "Done"
     return    

def is_number(s):
    print s
    if s == "NaN":
       s = 0
       return s         
    else:
       return s

#uploads sensor data using writekey

def uploadData(WriteKey,sensortype):
    params = uploadParams(sensortype,WriteKey)
    try:
        print "Uploading data..."
        conn.request("POST", "/update", params, headers)
        response = conn.getresponse()
        print response.status, response.reason
        if response.status == 200:
            print "UPLOADED!"
            print "**********"
            conn.close()
        else:
            print response.status, response.reason
            conn.close()
    except:
        print "connection probably timed-out"
        conn.close()

def Calibration(source,sensortype,floatTemp,floatHum,intLight,intCO2,floatTVOC,intPM10,intPM2_5):
    Calib_CSV=csv.DictReader(open('Calib_CSV.csv','rb'))
    print "Sensor serial number is: " , source
    for row in Calib_CSV:
        Serial_Number=row["Serial Number"]
        Temp_Slope=float(row["Temp_Slope"])
        Temp_Intercept=float(row["Temp_Intercept"])
        Humid_Slope=float(row["Humid_Slope"])
        Humid_Intercept=float(row["Humid_Intercept"])
        Lux_Slope=float(row["Lux_Slope"])
        Lux_Intercept=float(row["Lux_Intercept"])
        CO2_A=float(row["CO2_A"])
        CO2_B=float(row["CO2_B"])
        VOC_Slope=float(row["VOC_Slope"])
        VOC_Intercept=float(row["VOC_Intercept"])
        PM10_Slope=float(row["PM10_Slope"])
        PM10_Intercept=float(row["PM10_Intercept"])
        PM2_5_Slope=float(row["PM25_Slope"])
        PM2_5_Intercept=float(row["PM25_Intercept"])
        if source==Serial_Number:
            print "Matching CSV Serial Number is: ",Serial_Number
            print "Sensor type is: " ,sensortype
            if sensortype == "0":
                floatTVOC=round(floatTVOC*VOC_Slope+VOC_Intercept,2)
                intPM10=round(intPM10*PM10_Slope+PM10_Intercept,0)
                intPM2_5=round(intPM2_5*PM2_5_Slope+PM2_5_Intercept,0)
                print (floatTVOC, intPM10, intPM2_5)
		return (floatTVOC, intPM10, intPM2_5)
            elif sensortype == "1":
                print (floatTemp, floatHum, intLight)
                floatTemp=round(floatTemp*Temp_Slope+Temp_Intercept,1)
                floatHum=round(floatHum*Humid_Slope+Humid_Intercept,1)
                intLight=round(intLight*Lux_Slope+Lux_Intercept,0)
                print (floatTemp, floatHum, intLight)
		return (floatTemp, floatHum, intLight)
            elif sensortype == "2":
                floatTVOC=round(floatTVOC*VOC_Slope+VOC_Intercept,2)
                intLight=round(intLight*Lux_Slope+Lux_Intercept,0)
                print (floatTVOC, intLight)
		return (floatTVOC, intLight)
            elif sensortype == "3":
                intCO2=round(CO2_A*(pow(intCO2,CO2_B)),0)
                print intCO2
		return intCO2
            elif sensortype == "4":
                print intCO2, floatTVOC, intPM10, PM2_5
                intCO2=round(CO2_A*pow(intCO2,CO2_B),0)
                floatTVOC=round(floatTVOC*VOC_Slope+VOC_Intercept,2)
                intPM10=round(intPM10*PM10_Slope+PM10_Intercept,0)
                intPM2_5=round(intPM2_5*PM2_5_Slope+PM2_5_Intercept,0)
                print (intCO2,floatTVOC,intPM10,intPM2_5)
		return (intCO2,floatTVOC,intPM10,intPM2_5)
	    else:
                print "There's no sensor match!"
    
        
###################################### Main sub-routine #############################################
# Checks if sensor exists in db, or on thingspeak and does all required calls to get info to upload #

def ThingspeakProcess(source,sensortype,sensorID_dict,writeKey_dict):
    if source in sensorID_dict:
        print "1 Source in sensorID_dict"
        if source in writeKey_dict:
            print "1-1 source in writeKey_dict"
            if len(writeKey_dict[source]) == 2:
            	print "1-1-1 source in both db"
                uploadData(writeKey_dict[source][1],sensortype)       #upload
            else:
                print "1-1-2 source in both db, no write key?"
                channelID = sensorID_dict[source]
                readwritekey = getWriteKey(channelID)   #get key object from thingspeak json response
                writekey = readwritekey[0]['api_key']   #get writekey from object
                writeKey_dict[source].append(writekey)  #write key into DB
                uploadData(writekey,sensortype)         #upload
        else:
            print "1-2 source not in writeKey_dict"
            channelID = sensorID_dict[source]           #create new channel with source_addr as name - returns ID of new channel
            writeKey_dict[source] = [channelID,0]       #insert channelID and empty list item for writekey
            readwritekey = getWriteKey(channelID)
            writekey = readwritekey[0]['api_key']
            writeKey_dict[source][1] = writekey         #write key into DB
            uploadData(writekey,sensortype)             #upload
    
    elif source not in sensorID_dict:                   # = new sensor = create a channel, add the write API key to memory
        print "2 Source not in sensorID_dict"
        if source not in writeKey_dict:
            print "2-1 source not in writeKey_dict"
            channelID = createChannel(source,sensortype)#create new channel with source_addr as name - returns ID of new channel
            sensorID_dict[source] = [channelID]         #add new channelID to sensorIDlist
            writeKey_dict[source] = [channelID,0]       #insert channelID and empty list item for writekey
            readwritekey = getWriteKey(channelID)       #get key object from thingspeak json resposne
            writekey = readwritekey[0]['api_key']       #get writekey from object
            writeKey_dict[source][1] = writekey         #write key int DB
            uploadData(writekey,sensortype)             #upload
        else:
            print "2-2 source already in writeKey_dict"
            writeKey_dict[source][1] = writekey         #write key into DB
            uploadData(writekey,sensortype)             #upload
    else:
        print "this shouldn't happen"
        conn.close()
    return writeKey_dict, sensorID_dict

##################### MAIN GATEWAY ROUTINE #######################
# Routine waits until a packet is received from a remote sensors #
#    checks source and sensor type then calls main sub-routine   #
##################################################################

# list = [0,0]
# sensorID_dict = {}                                      #global dictionary for storing checkChannel results
# writeKey_dict = dict.fromkeys(range(1),list)               #global dictionary for storing writekeys, 
# print timestamp()
# print "Starting Thingspeak processes"
# time.sleep(3)
# print "Checking for saved channel list"

# if os.path.isfile("/home/pi/zigb2net/channelList.json"):
#     print "Channel list exists"
#     sensorID_dict = checkLocalChannels()
#     print "sensorID_dict from file is", sensorID_dict
# else:
#     print "No saved channel list...downloading remote list"
#     try :
#          sensorID_dict = downloadChannels();
#     except Exception:
#          print "error downloading channel list"
#          pass

# if os.path.isfile("/home/pi/zigb2net/writeKeys.json"):
#     print "Writekey list exists"
#     writeKey_dict = checkLocalKeyList()
#     print "writeKey_dict from file is", writeKey_dict
# else:
#     print "No saved writekey list"

# while True:
#     try:
#         zbport.flushInput()                                 #clear serial buffer
#         print "Waiting for packet..."
#         packet = zb.wait_read_frame()                       #wait for incoming packet
#         source = packet['source_addr_long'].encode('hex')   #read sending address
#         incoming = packet['rf_data']                        #read incoming packet data
#         print incoming					    #show what's coming in
#         if incoming[0] == "0":
#             print "PM and VOC Data"
#             sensortype,RsRo,PM2_5,PM10 = incoming.split(",")       #split data (comma separated values)
#             print source,sensortype,RsRo,PM2_5,PM10                #print to verify
# 	    tvoc = TVOCcalc(RsRo)
# 	    floatTVOC = float(tvoc)
#             intPM10 = int(PM10)
#             intPM2_5 = int(PM2_5)
# 	    floatTVOC,intPM10,intPM2_5=Calibration(source,sensortype,floatTemp,floatHum,intLight,intCO2,floatTVOC,intPM10,intPM2_5)
#         elif incoming[0] == "1":
#             print "Temp,Hum & Lux Data"
#             sensortype,hum,temp,light = incoming.split(",")        #split data (comma separated values)
#             tempReplace = temp.replace(' ', '')
#             lightReplace = light.replace('\n','')
#             floatTemp = float(tempReplace)
#             floatHum = float(hum)
#             nanLight = is_number(lightReplace)
#             intLight = int(nanLight)
#             print "Pre-calibration values are: " ,floatTemp,floatHum,intLight                 #print to verify
#             floatTemp, floatHum,intLight=Calibration(source,sensortype,floatTemp,floatHum,intLight,intCO2,floatTVOC,intPM10,intPM2_5) #send to calibration function
#             print "Post-calibration values are: " ,floatTemp,floatHum,intLight                #print to verify   
#         elif incoming[0] == "2":                                        
#             print "TVOC & Lux Data"
#             sensortype,RsRo,light = incoming.split(",")            #add light to this once sensor hooked up
#             lightReplace = light.replace('\n','')
# 	    tvoc = TVOCcalc(RsRo)                                  #not used!
# 	    floatTVOC = float(tvoc)
#             print source,sensortype,RsRo,light
#             floatTVOC,intLight=Calibration(source,sensortype,floatTemp,floatHum,intLight,intCO2,floatTVOC,intPM10,intPM2_5)
#         elif incoming[0] == "3":
# 	    print "CO2 Data"
# 	    sensortype,CO2 = incoming.split(",")                   #split data (comma separated values)
# 	    intCO2 = int(CO2)
#             print source,sensortype,CO2                            #print to verify#
#             intCO2=Calibration(source,sensortype,floatTemp,floatHum,intLight,intCO2,floatTVOC,intPM10,intPM2_5)
#         elif incoming[0] == "4":
#             print "PM, VOC & CO2 Data"
#             sensortype,RsRo,PM2_5,PM10,CO2 = incoming.split(",")   #split data (comma separated values)            
#             tvoc = TVOCcalc(RsRo)
#             intCO2 = int(CO2)
#             floatTVOC = float(tvoc)
#             intPM10 = int(PM10)
#             intPM2_5 = int(PM2_5)
#             print "Pre-calibration values are: " ,intCO2,floatTVOC,intPM10,intPM2_5            #print to verify
#             intCO2,floatTVOC,intPM10,intPM2_5=Calibration(source,sensortype,floatTemp,floatHum,intLight,intCO2,floatTVOC,intPM10,intPM2_5)
#             print "Post-calibration values are: " ,intCO2,floatTVOC,intPM10,intPM2_5
#         elif incoming[0] == "5":
#             print "NO2,Temp & Hum Data"
#             sensortype,intNO2,floatTemp,floatHum = incoming.split(",")   #split data (comma separated values)            
#             print source,sensortype,intNO2,floatTemp,floatHum                            #print to verify#
#         else:
#             print "Non-recognised sensor type in Gateway Routine, Ed need to fix this!"
#         try:
#             print timestamp()
#             sensorID_dict = checkChannel(source, sensorID_dict)
#         except Exception:
#             sensorID_dict = {}
#         ThingspeakProcess(source,sensortype,sensorID_dict,writeKey_dict)
#         storeWriteKeys(writeKey_dict)
#     except Exception:
#        print "error is preventing upload, please check logs"
#        pass

# zbport.close()

zb = ZigBee(zbport, callback=packet_received)         #instantiate a Zigbee on the port above

# Do other stuff in the main thread
while True:
        try:
                time.sleep(0.1)
                if packet_queue.qsize() > 0:
                        print packet_queue.qsize
                        # got a packet from recv thread
                        # See, the receive thread gets them
                        # puts them on a queue and here is
                        # where I pick them off to use
                        newPacket = packet_queue.get_nowait()
                        # now go dismantle the packet
                        # and use it.
                        handlePacket(newPacket)
        except KeyboardInterrupt:
                break

# halt() must be called before closing the serial
# port in order to ensure proper thread shutdown
zb.halt()
ser.close()

