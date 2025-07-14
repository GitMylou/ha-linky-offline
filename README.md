# Linky Data Injection for Home Assistant

This repository contains the necessary scripts to retrieve data from linky and inject those data to Home Assistant (HA).

This script is based on the work done by Bobuk:
- Home Assistant Plugin: https://github.com/bokub/ha-linky
- Conso API: https://github.com/bokub/conso-api

This repository provides an alternative to ha-linky if the HA installation does not support add-ons (this is the case for instance of HA Core) and/or if the machine hosting the HA Installation does not have access to internet.

## Known issue

The energy dasboard expect a cumulative sum. howevere, the data injected start from 0 and create a wrong value from 00h00 to 01h00. 

I tried to setup the field last_reset but it seems ignored. 
I cannot retrieve history of a long term statistic to get the last value. 
I am working on it but if you have idea... Next idea would be to retrieve index from linky instead of consumption, to write historic in file, or to target directly the database 

## Setup

This repository was tested with the following setup:
- A Smartphone is running HA Core on Termux Debian distribution. The smartphone does not have direct access to internet
- A computer with internet access can run the python script and inject data from ENEDIS (via Conso API) to HA. A job can be scheduled to execute the python script every day automatically.

## Prerequisites

You will need:
- a Linky meter
- an Enedis account
- Enable hourly consumption collection from your Enedis account ([tutorial](https://github.com/bokub/ha-linky/wiki/Activer-la-collecte-de-la-consommation-horaire))
- An access token for [Conso API](https://conso.boris.sh/)

## Installation

### Home Assistant sensors

Add sensors to your home assistant configuration.

Modify your configuration.yaml file:

```yaml
template:
  - sensor:
      - name: "Linky Hourly Consumption"
        unique_id: linky_hourly_consumption
        state: 0
        device_class: energy
        state_class: total_increasing
        unit_of_measurement: "Wh"

      - name: "Linky Hourly Injection"
        unique_id: linky_hourly_injection
        state: 0
        device_class: energy
        state_class: total_increasing
        unit_of_measurement: "Wh"
```

### Long Term Statistics API

Install the following API 
https://github.com/GitMylou/ha-get-statistics#

### Environment file

on the computer where you want to execute the python script (and with an internet connection), clone this repository

```sh
git clone https://github.com/GitMylou/ha-linky-offline.git
cd ha-linky-offline
```

Create a .env file next to the python 

```yaml
export LINKY_TOKEN=<your enedis token>

export HA_URL=http://<your ha IP>:8123
export HA_TOKEN=<your ha long life token>

## Usage

Run the python script to retrieve data from ENEDIS and inject to Home Assistant

CAUTION: If you make too many request to the API, your IP can be ban definitely!!!!

```sh
# Source environment variable
source .env

# Process data from yesterday
python3 enedis_to_ha.py

# Process data from a given range of dates
python3 enedis_to_ha.py  --startDate 2025-07-06 --endDate 2025-07-11
```

The script will takes some minutes to process data ( I added wait to avoid too many requests per seconds...). 
Be patient and wait for the script to exit.

## Troubleshooting

### no module named dateutil

if you face the following error: 

```sh
import dateutil ImportError: No module named 'dateutil'
```
you need to install the python module dateutil 
```sh
pip3 install python-dateutil
```

