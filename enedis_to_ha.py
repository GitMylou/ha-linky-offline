import argparse
from datetime import datetime, timedelta
from dateutil import parser
import json
import os
import requests
import time

##################################################################################
################################## Configuration #################################
##################################################################################

# Linky configuration
LINKY_TOKEN = os.getenv("LINKY_TOKEN")
LINKY_PRM = os.getenv("LINKY_PRM")

# Home assistant configuration
HA_TOKEN = os.getenv("HA_TOKEN")
HA_URL = os.getenv("HA_URL")

HA_STAT_CONSUMPTION_CURVE = "sensor.linky_hourly_consumption"
HA_STAT_CONSUMPTION_CURVE_NAME = "Linky Hourly Consumption"
HA_STAT_PROD_CURVE = "sensor.linky_hourly_injection"
HA_STAT_PROD_CURVE_NAME = "Linky Hourly Injection"

GMT="+03:00"

# Enable testing
LOAD_DATA_FROM_CACHE = False

##################################################################################
################################### Constantes ###################################
##################################################################################

LINKY_API = "https://conso.boris.sh/api/"
CONSUMPTION_CURVE = "consumption_load_curve"
PROD_CURVE = "production_load_curve"

##################################################################################
################################ Helper functions ################################
##################################################################################

# Retrieve data from ENEDIS using Boris conso API
#   command: The API command to select which data to retrieve
#   startDate: start date of data
#   endDate: end date of data
def retrieveDataFromLink(command, startDate, endDate):
    url = LINKY_API + command
    headers = {"Authorization": f"Bearer {LINKY_TOKEN}"}
    params = {
        "prm": LINKY_PRM,
        "start": startDate.strftime("%Y-%m-%d"),
        "end": endDate.strftime("%Y-%m-%d"),
    }
    # Call API to get data
    response=requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    jsonData = response.json()

    cacheFile = command + ".json"
    with open(cacheFile, "w") as f:
        json.dump(jsonData, f, indent=2)
        print(f"Results saved into {cacheFile}")
    return jsonData

# Load data from Json file for testing
#   command: The API command to select which data to retrieve
def loadDataFromCache(command):
    cacheFile = command + ".json"
    try:
        with open(cacheFile, "r") as f:
            return json.load(f)
    except:
        print("Unable to open file " + cacheFile)
        return {}

# Push sensor data to home assistant
#   sensorId: The Sensor ID
#   sensorName: The Sensor Name
#   jsonData: The Json data to be loaded
def pushDataToHA(sensorId, sensorName, jsonData):
    url = f"{HA_URL}/api/services/recorder/import_statistics"
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "has_mean": False,
        "has_sum": True,
        "source": "recorder",
        "name": sensorName,
        "statistic_id": sensorId,
        "unit_of_measurement": "Wh",
        "stats": parseStats(sensorId, jsonData)
    }

    res = requests.post(url, headers=headers, json=payload)
    if res.status_code in (200, 201):
        print(f"Data sent to Home Assistant ({sensorId})")
    else:
        print(f"Error while sending data to Home Assistant ({sensorId}): {res.status_code} - {res.text}")

# Parse data from Conso API as Home Assistant format
#   sensorId: The Sensor ID
#   jsonData: The Json data to parse for HA
def parseStats(sensorId, jsonData):
    stats = []

    # Energy dashboard use a cumulative sum. 
    # Try to retrieve statistics from the previous day
    firstEntry = jsonData["interval_reading"][0]
    firstDate = parser.isoparse(firstEntry["date"])
    sumOfStats = 0
    firstStatistics = getStatistics(sensorId, firstDate.replace(hour=0))
    if firstStatistics:
        sumOfStats = firstStatistics

    # We need also to check the last day. 
    # If statistics for last day already exists, we need to drop the last value
    # Otherwise, next day will be corrupted....
    lastEntry = jsonData["interval_reading"][-1]
    lastEntryDate = parser.isoparse(lastEntry["date"])
    lastEntryStatistics = getStatistics(sensorId, lastEntryDate)
    # A reset has been done starting from next day.
    # We need to drop the lastday value at 23h
    dropDate = None
    if lastEntryStatistics == 0:
        print("Found statistic 0 for next day.")
        print("We will not write the last value to avoid corrupting next days.")
        lastEntryDate = lastEntryDate - timedelta(days=1)
        lastEntryDate.replace(hour=23)
        dropDate = lastEntryDate

    # Hourly production: We need to concatenate if one data each 30 minutes
    isFrequency30mn = False
    for entry in jsonData["interval_reading"]:
        date = parser.isoparse(entry["date"])

        # Drop last entries if needed
        if dropDate and date == dropDate:
            return stats

        # If update each 30minutes, we don't update database but we register half hour value
        if date.minute == 30:
            sumOfStats += int(entry["value"]) / 2
            isFrequency30mn = True
        else:
            entryStat = {}
            entryStat["start"] = str(date.isoformat(sep=' ')+GMT)
            if isFrequency30mn:
                sumOfStats += int(entry["value"]) / 2
                entryStat["sum"] = sumOfStats
            else:
                sumOfStats += int(entry["value"])
                entryStat["sum"] = sumOfStats
            stats.append(entryStat)
    return stats

# Get long term statistics for specific date
#   sensorId: The Sensor ID
#   jsonData: The date to get the statistics
def getStatistics(sensorId, date):
    url = f"{HA_URL}/api/long_term_stats"
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }
    params = {
        "entity_id": sensorId,
        "datetime": str(date.isoformat(sep=' ')+GMT)
    }

    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        print("Found previous statistic for ", sensorId, ": ", data["message"]["sum"])
        return data["message"]["sum"]
    else:
        print("No previous statistic found for ", sensorId, ". Starting from 0")
        return None

##################################################################################
################################# Input Arguments ################################
##################################################################################
argparser = argparse.ArgumentParser(description="Get data from Enedis and inject to HA. If no date given, process data from yesterday.")
argparser.add_argument("--startDate", required=False, help="Start date in format YYYY-MM-DD")
argparser.add_argument("--endDate", required=False, help="End date in format YYYY-MM-DD")
args = argparser.parse_args()

##################################################################################
################################## Main script ###################################
##################################################################################

# Sanity checks
if not LINKY_TOKEN or not LINKY_PRM:
    print("LINKY_TOKEN or LINKY_PRM missing")
    exit(1)
if not HA_TOKEN or not HA_URL:
    print("HA_TOKEN or HA_URL missing")
    exit(1)

# Get range of date to process
startDate = ""
endDate = ""
if args.startDate and args.endDate:
    try:
        startDate = datetime.strptime(args.startDate, "%Y-%m-%d")
        endDate = datetime.strptime(args.endDate, "%Y-%m-%d")
    except ValueError as e:
        print("Error parsing dates:", e)
        exit(1)
else:
    print("No date given. Processing data from yesterday.")
    yesterday = datetime.now() - timedelta(days=1)
    startDate = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
    endDate = startDate + timedelta(days=1)
print("processing Data from ", startDate, " to ", endDate)

# Retrieve Linky data
print()
dailyConsumptionData = {}
consumptionCurveData = {}
dailyProdData = {}
prodCurveData = {}
if LOAD_DATA_FROM_CACHE:
    print("Get data from cache....")
    consumptionCurveData = loadDataFromCache(CONSUMPTION_CURVE)
    prodCurveData = loadDataFromCache(PROD_CURVE)
else:
    print("Get data from API")
    consumptionCurveData = retrieveDataFromLink(CONSUMPTION_CURVE, startDate, endDate)
    time.sleep(30)
    prodCurveData = retrieveDataFromLink(PROD_CURVE, startDate, endDate)
    time.sleep(30)

if not (dailyConsumptionData or consumptionCurveData or dailyProdData or prodCurve):
    print("Load data failed !")
    exit(1)

print("Data Loaded")

print()
print("Push data to Home Assistant")
pushDataToHA(HA_STAT_CONSUMPTION_CURVE, HA_STAT_CONSUMPTION_CURVE_NAME, consumptionCurveData)
pushDataToHA(HA_STAT_PROD_CURVE, HA_STAT_PROD_CURVE_NAME, prodCurveData)
print("Done")
