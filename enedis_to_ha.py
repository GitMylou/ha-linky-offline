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

HA_STAT_DAILY_CONSUMPTION = os.getenv("HA_STAT_DAILY_CONSUMPTION", "sensor.linky_daily_consumption")
HA_STAT_DAILY_CONSUMPTION_NAME = os.getenv("HA_STAT_DAILY_CONSUMPTION_NAME", "Daily consumption")
HA_STAT_CONSUMPTION_CURVE = os.getenv("HA_STAT_CONSUMPTION_CURVE", "sensor.linky_consumption_load_curve")
HA_STAT_CONSUMPTION_CURVE_NAME = os.getenv("HA_STAT_CONSUMPTION_CURVE_NAME", "Hourly Consumption")
HA_STAT_DAILY_PROD = os.getenv("HA_STAT_DAILY_PROD", "sensor.linky_daily_production")
HA_STAT_DAILY_PROD_NAME = os.getenv("HA_STAT_DAILY_PROD_NAME", "Daily Injection")
HA_STAT_PROD_CURVE = os.getenv("HA_STAT_PROD_CURVE", "sensor.linky_production_load_curve")
HA_STAT_PROD_CURVE_NAME = os.getenv("HA_STAT_PROD_CURVE_NAME", "Hourly Injection")

GMT="+03:00"

# Enable testing
LOAD_DATA_FROM_CACHE = False

##################################################################################
################################### Constantes ###################################
##################################################################################

LINKY_API = "https://conso.boris.sh/api/"
DAILY_CONSUMPTION = "daily_consumption"
CONSUMPTION_CURVE = "consumption_load_curve"
DAILY_PROD = "daily_production"
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
    numberOfStats = len(jsonData["interval_reading"])
    hasSum = numberOfStats != 1

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
        "stats": parseStats(jsonData, numberOfStats)
    }

    res = requests.post(url, headers=headers, json=payload)
    if res.status_code in (200, 201):
        print(f"Data sent to Home Assistant ({sensorId})")
    else:
        print(f"Error while sending data to Home Assistant ({sensorId}): {res.status_code} - {res.text}")

# Parse data from Conso API as Home Assistant format
#   jsonData: The Json data to parse for HA
#   numberOfStats: The number of stat in the data
def parseStats(jsonData, numberOfStats):
    stats = []

    # Daily production
    if numberOfStats == 1:
        entry = jsonData["interval_reading"][0]
        entryStat = {}
        entryStat["start"] = str(parser.isoparse(entry["date"]).isoformat(sep=' ')+GMT)
        entryStat["sum"] = int(entry["value"])
        stats.append(entryStat)
        return stats

    # Hourly production: We need to concatenate if one data each 30 minutes
    sumOfStats = 0
    sum30Mn = 0
    isFrequency30mn = False
    for entry in jsonData["interval_reading"]:
        date = parser.isoparse(entry["date"])
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
    dailyConsumptionData = loadDataFromCache(DAILY_CONSUMPTION)
    consumptionCurveData = loadDataFromCache(CONSUMPTION_CURVE)
    dailyProdData = loadDataFromCache(DAILY_PROD)
    prodCurveData = loadDataFromCache(PROD_CURVE)
else:
    print("Get data from API")
    dailyConsumptionData = retrieveDataFromLink(DAILY_CONSUMPTION, startDate, endDate)
    time.sleep(30)
    consumptionCurveData = retrieveDataFromLink(CONSUMPTION_CURVE, startDate, endDate)
    time.sleep(30)
    dailyProdData = retrieveDataFromLink(DAILY_PROD, startDate, endDate)
    time.sleep(30)
    prodCurveData = retrieveDataFromLink(PROD_CURVE, startDate, endDate)
    time.sleep(30)

if not (dailyConsumptionData or consumptionCurveData or dailyProdData or prodCurve):
    print("Load data failed !")
    exit(1)

print("Data Loaded")

print()
print("Push data to Home Assistant")
pushDataToHA(HA_STAT_DAILY_CONSUMPTION, HA_STAT_DAILY_CONSUMPTION_NAME, dailyConsumptionData)
pushDataToHA(HA_STAT_CONSUMPTION_CURVE, HA_STAT_CONSUMPTION_CURVE_NAME, consumptionCurveData)
pushDataToHA(HA_STAT_DAILY_PROD, HA_STAT_DAILY_PROD_NAME, dailyProdData)
pushDataToHA(HA_STAT_PROD_CURVE, HA_STAT_PROD_CURVE_NAME, prodCurveData)
print("Done")
