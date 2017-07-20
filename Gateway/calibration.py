#! /usr/bin/python

import math
import csv

def readRows(calibration_data, newSource, sensortype):
    print "source address is ", newSource
    for row in calibration_data:
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
        if newSource==Serial_Number:
#           print "Matching CSV Serial Number is: ",Serial_Number
#	    print "Sensor type is: " ,sensortype
            if sensortype == 0:
                return VOC_Slope,VOC_Intercept,PM10_Slope,PM10_Intercept,PM2_5_Slope,PM2_5_Intercept
            elif sensortype == 1: 
                return Temp_Slope,Temp_Intercept,Humid_Slope,Humid_Intercept,Lux_Slope,Lux_Intercept
	    elif sensortype == 2: 
	        return
	    elif sensortype == 3: 
	        return CO2_A,CO2_B
	    elif sensortype == 4: 
	        return CO2_A,CO2_B,VOC_Slope,VOC_Intercept,PM10_Slope,PM10_Intercept,PM2_5_Slope,PM2_5_Intercept
	    elif sensortype == 5: 
	        return 
	    else:
	        print "Unhandled sensor type in calibration routine"
                return
    else:
        print "sensor ID not found"
    
def calibrate_0(Calib_CSV,source,sensortype,floatTVOC,intPM2_5,intPM10):
    VOC_Slope,VOC_Intercept,PM10_Slope,PM10_Intercept,PM2_5_Slope,PM2_5_Intercept = readRows(Calib_CSV, source, sensortype)
    floatTVOC=round(floatTVOC*VOC_Slope+VOC_Intercept,2)
    intPM10=round(intPM10*PM10_Slope+PM10_Intercept,0)
    intPM2_5=round(intPM2_5*PM2_5_Slope+PM2_5_Intercept,0)
#    print (floatTVOC, intPM2_5, intPM10)
    return (floatTVOC, intPM2_5, intPM10)

def calibrate_1(Calib_CSV,packetSource,sensortype,floatTemp,floatHum,intLight):
    try:
        Temp_Slope,Temp_Intercept,Humid_Slope,Humid_Intercept,Lux_Slope,Lux_Intercept = readRows(Calib_CSV, packetSource, sensortype)
        floatTemp=round(floatTemp*Temp_Slope+Temp_Intercept,1)
        floatHum=round(floatHum*Humid_Slope+Humid_Intercept,1)
        intLight=round(intLight*Lux_Slope+Lux_Intercept,0)
#        print (floatTemp, floatHum, intLight)
        return (floatTemp, floatHum, intLight)
    except:
        print "calibration failed"
        return (floatTemp, floatHum, intLight)

def calibrate_2():
    return

def calibrate_3(Calib_CSV,packetSource,sensortype,preCO2):
    CO2_A, CO2_B = readRows(Calib_CSV, packetSource, sensortype)
    postCO2=round(CO2_A*(pow(preCO2,CO2_B)),0)
#    print postCO2
    return (postCO2)

def calibrate_4(Calib_CSV,packetSource,sensortype,preCO2,floatTVOC,intPM2_5,intPM10):
    CO2_A,CO2_B,VOC_Slope,VOC_Intercept,PM10_Slope,PM10_Intercept,PM2_5_Slope,PM2_5_Intercept = readRows(Calib_CSV, packetSource, sensortype)
    postCO2=round(CO2_A*pow(postCO2,CO2_B),0)
    floatTVOC=round(floatTVOC*VOC_Slope+VOC_Intercept,2)
    intPM10=round(intPM10*PM10_Slope+PM10_Intercept,0)
    intPM2_5=round(intPM2_5*PM2_5_Slope+PM2_5_Intercept,0)
#    print (postCO2,floatTVOC,intPM2_5,intPM10)
    return (postCO2,floatTVOC,intPM2_5,intPM10)
	
