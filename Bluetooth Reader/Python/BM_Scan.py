#!/usr/bin/env python3
__author__ = "Jesse Ross-Jones"
__license__ = "Public Domain"
__version__ = "1.0"

## Tested with Python 2.7
## Using bluepy, scan for bluetooth devices for 15 seconds.
## Search list of found devices and for devices matching broodminder manufacture data
## Decode and print the advertising data
## 
## DStrickler Sat, Apr 14, 2018
## Use bluepy module from https://github.com/IanHarvey/bluepy (has install instructions)
## Needs to be run with "sudo" so that the BLE library can sniff out devices. Otherwise will error out.
## On Ubuntu, I've found that I need to install the bluepy source from scratch to get it to work.
##
## DStrickler Mon, Apr 16, 2018
## Sniffs out all devices, but doesn't exclude weight when not a 43 device.
##
## DStrickler Mon, Jul 23, 2018
## Added preliminary upload test with Alpha API call (/api_public).
## Uploads temperature, humidity, weight and battery from all the BroodMinder
## devices that show up in a BLE scan.
## Note I am using an unpublished API call to upload data with this code.
##
## DStrickler Wed, Jan 16, 2019
## Added support for uploading the sample info as well.
##

from bluepy.btle import Scanner, DefaultDelegate
import urllib3


def byte(str, byteNum):
    # https://stackoverflow.com/questions/5649407/hexadecimal-string-to-byte-array-in-python
    # Trapping for 'str' passed as 'None'
    if (str == None):
        return ''

    return str[byteNum * 2] + str[byteNum * 2 + 1]


def checkBM(data):
    check = False
    byteCheck = 0
    BMIFLLC = str("8d02")
    # print(byte(data,byteCheck))
    if (BMIFLLC == byte(data, byteCheck) + byte(data, byteCheck + 1)):
        print("confirmed BroodMinder")
        check = True
    return check


def extractData(deviceId, data):
    offset = 8  # There are 8 bits less than described in BroodMinder documentation

    byteNumAdvdeviceModelIFllc_1 = 10 - offset
    byteNumAdvDeviceVersionMinor_1 = 11 - offset
    byteNumAdvDeviceVersionMajor_1 = 12 - offset
    byteNumAdvBattery_1V2 = 14 - offset
    byteNumAdvElapsed_2 = 15 - offset   # This is the sample number from the device.
    byteNumAdvTemperature_2 = 17 - offset
    byteNumAdvHumidity_1 = 24 - offset
    byteNumAdvElapsed_2V2 = 15 - offset
    byteNumAdvTemperature_2V2 = 17 - offset
    byteNumAdvWeightL_2V2 = 20 - offset
    byteNumAdvWeightR_2V2 = 22 - offset
    byteNumAdvHumidity_1V2 = 24 - offset
    byteNumAdvUUID_3V2 = 25 - offset

    # Version 2 advertising

    # Current sample number from the device.
    sampleNumber = int(byte(data, byteNumAdvElapsed_2), 16)

    # batteryPercent = e.data[byteNumAdvBattery_1V2]
    batteryPercent = int(byte(data, byteNumAdvBattery_1V2), 16)
    # Elapsed = e.data[byteNumAdvElapsed_2V2] + (e.data[byteNumAdvElapsed_2V2 + 1] << 8)

    # temperatureDegreesC = e.data[byteNumAdvTemperature_2V2] + (e.data[byteNumAdvTemperature_2V2 + 1] << 8)
    temperatureDegreesC = int(byte(data, byteNumAdvTemperature_2V2 + 1) + byte(data, byteNumAdvTemperature_2V2), 16)
    temperatureDegreesC = (temperatureDegreesC - 5000) / 100
    temperatureDegreesF = round((temperatureDegreesC * 9 / 5) + 32, 1)

    # humidityPercent = e.data[byteNumAdvHumidity_1V2]
    humidityPercent = int(byte(data, byteNumAdvHumidity_1V2), 16)

    # weightL = e.data[byteNumAdvWeightL_2V2+1] * 256 + e.data[byteNumAdvWeightL_2V2 + 0] - 32767
    weightL = int(byte(data, byteNumAdvWeightL_2V2 + 1) + byte(data, byteNumAdvWeightL_2V2 + 0), 16) - 32767
    weightScaledL = float(weightL) / 100
    # weightR = e.data[byteNumAdvWeightR_2V2 + 1] * 256 + e.data[byteNumAdvWeightR_2V2 + 0] - 32767
    weightR = int(byte(data, byteNumAdvWeightR_2V2 + 1) + byte(data, byteNumAdvWeightR_2V2 + 0), 16) - 32767
    weightScaledR = float(weightR) / 100
    weightScaledTotal = weightScaledL + weightScaledR

    # If the weight is a positive number, it's good. If it's negative, we know it's a false reading.
    # Note wildly negative readings happen on T&H devices, so we always need to trap for this.
    if (weightScaledTotal > -1):
        # We have a valid weight.
        print(
            "Sample = {}, Weight = {}, TemperatureF = {}, Humidity = {}, Battery = {}".format(sampleNumber, weightScaledTotal, temperatureDegreesF,
                                                                                 humidityPercent, batteryPercent))
        result = BroodMinderResult(deviceId, sampleNumber, temperatureDegreesC, humidityPercent, batteryPercent, weightScaledTotal)
    else:
        # We do not have a valid weight.
        print("Sample = {}, TemperatureF = {}, Humidity = {}, Battery = {}".format(sampleNumber, temperatureDegreesF, humidityPercent,
                                                                      batteryPercent))
        result = BroodMinderResult(deviceId, sampleNumber, temperatureDegreesC, humidityPercent, batteryPercent)
    
    sendDataToMyBroodMinder(result)
    print("-----------------------------------------------------------------------------")

class ScanDelegate(DefaultDelegate):
    def __init__(self):
        DefaultDelegate.__init__(self)

    def handleDiscovery(self, dev, isNewDev, isNewData):
        if isNewDev:
            # print "Discovered device", dev.addr
            print("Discovered device {}".format(dev.addr))
        elif isNewData:
            # print "Received new data from", dev.addr
            print("Received new data from {}".format(dev.addr))

class BroodMinderResult:
    def __init__(self, deviceId, sampleNumber, temperatureC, humidityPercent, batteryPercent, weight = None):
        self.DeviceId = deviceId
        self.SampleNumber = sampleNumber
        self.TemperatureC = temperatureC
        self.HumidityPercent = humidityPercent
        self.BatteryPercent = batteryPercent
        self.Weight = weight # TH devices don't have weight, so by default this will be None.
        # The MyBroodMinder API expects the temperature in F :(
        self.TemperatureF = round((temperatureC * 9 / 5) + 32, 1)

def sendDataToMyBroodMinder(data: BroodMinderResult):
    # Send the info to MyBroodMinder.com
    print("Sending device '{}' data to the MyBroodMinder Cloud ...".format(data.DeviceId))
    url_string = "https://mybroodminder.com/api_public/devices/upload?device_id={}&sample={}&temperature={}&humidity={}&battery_charge={}".format(
        data.DeviceId, data.SampleNumber, data.TemperatureF, data.HumidityPercent, data.BatteryPercent)
    if data.Weight is not None: # Not all results will have weight, so only include it if we have a value.
        url_string += "&weight={}".format(data.Weight)
    print(url_string)
    # Fire off the GET request which uploads the data. This should really be POST but that's not how the API works.
    urllib3.urlopen(url_string).read()

scanner = Scanner().withDelegate(ScanDelegate())
devices = scanner.scan(15.0)

for dev in devices:
    if (checkBM(dev.getValueText(255))):
        # print "BroodMinder Found!"
        # print "Device %s (%s), RSSI=%d dB" % (dev.addr, dev.addrType, dev.rssi)
        print("Device {} ({}), RSSI={} dB".format(dev.addr, dev.addrType, dev.rssi))
        for (adtype, desc, value) in dev.getScanData():
            # print "  %s = %s" % (desc, value)
            print ("{} = {}".format(desc, value))

            # Trap for the BroodMinder ID
            if (desc == "Complete Local Name"):
                deviceId = value

        extractData(deviceId, dev.getValueText(255))
    else:
        print("Device {} is not a broodminder - ignoring".format(dev.addr))
