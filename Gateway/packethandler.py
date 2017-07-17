#! /usr/bin/python

import math
import time

#Regressed sensitivity curves constants for Rs/Ro to ppm from sensor manufacturer's datasheet
#C7H8Curve = [37.22590719,2.078062258]                      #TGS2602 (0.3;1)( 0.8;10) (0.4;30)
#H2S_Curve = [0.05566582614,-2.954075758]                   #TGS2602 (0.8,0.1) (0.4,1) (0.25,3)
#C2H5OH_Curve = [0.5409499131,-2.312489623]                 #TGS2602 (0.75,1) (0.3,10) (0.17,30)  
NH3_Curve = [1052.3,-3377.3,4031.2,-2103.9,374.82,22.863]   #Ammonia sensitivity curve 
NH3_MMass = 17.03 #(g/mol)
Mvolume = 22.414

#calculates VOC concentration based on RsRo ratio - see TGS2602 datasheet for details
def TVOCcalc(RsRo):
    x = float(RsRo)
    tvoc = ((NH3_Curve[0]*pow(x,5))+(NH3_Curve[1]*pow(x,4))+(NH3_Curve[2]*pow(x,3))+(NH3_Curve[3]*pow(x,2)+NH3_Curve[4]*x)+NH3_Curve[5])
    if tvoc < 0:
        tvoc = 0
        print "Rs/Ro= ",RsRo
        print "= ", tvoc, "ppm"
        conc = 0.00
    else:
        #concentration(mg/m3) = concentration(ppm) X ( molar mass(g/mol) / molar volume(L) )
        print "Rs/Ro= ",RsRo
        print "= ",tvoc, "ppm"
        conc = round(tvoc*(NH3_MMass/Mvolume),2)
        print "= ", conc, "mg/m^3"
    return conc

#quick function to replace non-number Lux readings with zero
def is_number(s):
    print s
    if s == "NaN":
       s = 0
       return s         
    else:
       return s

#extract required values from incoming Xbee packet
def unpacket(packet, sensortype):
    incoming = packet['rf_data']
    if sensortype == 0:
        discardType,RsRo,PM2_5,PM10 = incoming.split(",")       #split data (comma separated values)
        floatRsRo = float(RsRo)
        tvoc = TVOCcalc(RsRo)
        floatTVOC = float(tvoc)
        intPM10 = int(PM10)
        intPM2_5 = int(PM2_5)
        return floatTVOC,PM2_5,PM10

    elif sensortype == 1:
        print "THL Qube"
        discardType,hum,temp,light = incoming.split(",")        
        lightReplace = light.replace('\n','')
        tempReplace = temp.replace(' ', '')
        nanLight = is_number(lightReplace)
        floatHum = float(hum)
        floatTemp = float(tempReplace)
        intLight = int(nanLight)
        return floatHum,floatTemp,intLight

    elif sensortype == 2:                                        
        print "TVOC & Lux Qube - sensor doesn't exist!"

    elif sensortype == 3:
        print "CO2 Qube"
        discardType,CO2 = incoming.split(",")                   
        intCO2 = int(CO2)
        print CO2                            
        return CO2                          

    elif sensortype == 4:
        print "PM, VOC & CO2 Qube"
        discardType,RsRo,PM2_5,PM10,CO2 = incoming.split(",")   
        tvoc = TVOCcalc(RsRo)
        floatTVOC = float(tvoc)
        intCO2 = int(CO2)
        intPM10 = int(PM10)
        intPM2_5 = int(PM2_5)
        print floatTVOC,intPM2_5,intPM10,intCO2
        return floatTVOC,intPM2_5,intPM10,intCO2

    elif sensortype == 5:
        print "NO2,Temp & Hum Qube"
        discardType,intNO2,floatTemp,floatHum = incoming.split(",")
        print intNO2,floatTemp,floatHum
        return intNO2,floatTemp,floatHum

    else:
