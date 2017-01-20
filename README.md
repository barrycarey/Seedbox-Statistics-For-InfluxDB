**Seedbox Statistics For Influxdb**
------------------------------

![Screenshot](https://puu.sh/ttcxJ/2919760fa3.PNG)

This tool will allow you to send stats from a torrent client to InfluxDB for displaying in Grafana

**Support Clients**
* Deluge

## Configuration within config.ini

#### GENERAL
|Key            |Description                                                                                                         |
|:--------------|:-------------------------------------------------------------------------------------------------------------------|
|Delay          |Delay between runs                                                                                                  |
|Output         |Write console output while tool is running                                                                          |
|Hostname       |Hostname to use as tag in InfluxDB.  Leaving black will auto-detect                                                 |
#### INFLUXDB
|Key            |Description                                                                                                         |
|:--------------|:-------------------------------------------------------------------------------------------------------------------|
|Address        |Delay between updating metrics                                                                                      |
|Port           |InfluxDB port to connect to.  8086 in most cases                                                                    |
|Database       |Database to write collected stats to                                                                                |
|Username       |User that has access to the database                                                                                |
|Password       |Password for above user                                                                                             |
#### TORRENTCLIENT
|Key            |Description                                                                                                         |
|:--------------|:-------------------------------------------------------------------------------------------------------------------|
|Client         |The torrent client to target.  Currently Support: deluge                                                            |
|Password       |Password to use when connecting to the API                                                                          |
|Url            |URL of the API to connect to.                                                                                       |
#### LOGGING
|Key            |Description                                                                                                         |
|:--------------|:-------------------------------------------------------------------------------------------------------------------|
|Enable         |Output logging messages to provided log file                                                                        |
|Level          |Minimum type of message to log.  Valid options are: critical, error, warning, info, debug                           |
|LogFile        |File to log messages to.  Can be relative or absolute path                                                          |
|CensorLogs     |Censor certain things like server names and IP addresses from logs                                                  |



**Usage**

Before the first use run pip3 install -r requirements.txt

Enter your desired information in config.ini and run influxdbSeedbox.py

Optionally, you can specify the --config argument to load the config file from a different location.  


***Requirements***

Python 3+

You will need the influxdb library installed to use this - [Found Here](https://github.com/influxdata/influxdb-python)

You will need the speedtest-cli library installed to use this - [Found Here](https://github.com/sivel/speedtest-cli)

You also MUST have the Deluge WebUI plugin installed
