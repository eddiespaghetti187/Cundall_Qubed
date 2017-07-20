import os.path
import httplib, urllib
from collections import defaultdict

"""This routine checks if local json files exist in the normal locations. 
If they do exist, they are passed back to the main routine as dictionaries to enable uploading. 
If they don't, the channel list is downloaded and saved to channelList.json."""

# parses local Thingspeak writeKeys list

user_ID = cundalltest
user_key = ZZJAWMDUFLD5BBHS
headers = {"Content-type": "application/x-www-form-urlencoded","Accept": "text/plain"}  #standard headers for all Thspeak communications
conn = httplib.HTTPConnection("api.thingspeak.com:80")    #standard conn to main Thspeak server - update for personal server

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

# checks if local channellist exists

def channelListFileCheck():
	print "checking channel list exists..."
	if os.path.isfile("/home/pi/Cundall_Qubed/Gateway/channelList.json"):
    	print "Channel list exists"
    	sensorID_dict = checkLocalChannels()
    	print "sensorID_dict from file is", sensorID_dict
	else:
	    print "No saved channel list...downloading remote list"
	    try :
	         sensorID_dict = downloadChannels();
	    except Exception:
	         print "error downloading channel list"
	         pass

# checks if writekeylist exists

def writeKeyListFileCheck():
	if os.path.isfile("/home/pi/Cundall_Qubed/Gateway/writeKeys.json"):
    	print "Writekey list exists"
    	writeKey_dict = checkLocalKeyList()
    	print "writeKey_dict from file is", writeKey_dict
	else:
    	print "No saved writekey list"


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

# test routines

checkLocalChannels()
