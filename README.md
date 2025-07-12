# Linky Data Injection for Home Assistant

This repository contains the necessary scripts to retrieve data from linky and inject those data to Home Assistant (HA).

This script is based on the work done by Bobuk:
- Home Assistant Plugin: https://github.com/bokub/ha-linky
- Conso API: https://github.com/bokub/conso-api

This repository provides an alternative to ha-linky if the HA installation does not support add-ons (this is the case for instance of HA Core) and/or if the machine hosting the HA Installation does not have access to internet.

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
      - name: "Daily consumption"
        unique_id: linky_daily_consumption
        state: 0
        device_class: energy
        state_class: total_increasing
        unit_of_measurement: "Wh"

      - name: "Hourly Consumption"
        unique_id: linky_consumption_load_curve
        state: 0
        device_class: energy
        state_class: total_increasing
        unit_of_measurement: "Wh"

      - name: "Daily Injection"
        unique_id: linky_daily_production
        state: 0
        device_class: energy
        state_class: total_increasing
        unit_of_measurement: "Wh"

      - name: "Hourly Injection"
        unique_id: linky_production_load_curve
        state: 0
        device_class: energy
        state_class: total_increasing
        unit_of_measurement: "Wh"
```

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

# You can modify those variables if you want custom names
export HA_STAT_DAILY_CONSUMPTION=sensor.linky_daily_consumption
export HA_STAT_CONSUMPTION_CURVE=sensor.linky_consumption_load_curve
export HA_STAT_DAILY_PROD=sensor.linky_daily_production
export HA_STAT_PROD_CURVE=sensor.linky_production_load_curve
```

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
