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



## Usage

Before the first use run pip3 install -r requirements.txt

Enter your desired information in config.ini and run influxdbSeedbox.py

Optionally, you can specify the --config argument to load the config file from a different location.  


## Notes About Specific Clients

**Deluge**
* You must have the WebUI plugin installed.
* The URL to use in the config will usually look like: http://ADDRESS:8112/json
* Only the password is required in the config.ini

**uTorrent**
* You must have the Web Interface enabled with a Username/Password set
* The URL to use in the config will usually look like: http://localhost:8080/gui
* You must have both a username and password in the config

**rTorrent**
* Neither username or password are needed in the config
* URL can very depending on configuration

rTorrent is tricky since you need something to forward the SCGI requests. For my testing I used nginx to forward requests on port 8000
Setting this up is beyond the scope of this tool. 
However, you can refer to [this guide](http://elektito.com/2016/02/10/rtorrent-xmlrpc/)

***Requirements***

Python 3+

You will need the influxdb library installed to use this - [Found Here](https://github.com/influxdata/influxdb-python)

You will need the speedtest-cli library installed to use this - [Found Here](https://github.com/sivel/speedtest-cli)

You also MUST have the Deluge WebUI plugin installed
