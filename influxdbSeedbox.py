import configparser
import os
import sys
import argparse
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError, InfluxDBServerError
import time
import logging
import re
import json
import gzip
from urllib.request import Request, URLError, urlopen
import socket

# TODO Move urlopen login in each method call to one central method
# TODO Keep track of tracker overall ratios
__author__ = 'barry'
class configManager():

    #TODO Validate given client url

    def __init__(self, config):

        self.valid_torrent_clients = ['deluge']

        print('Loading Configuration File {}'.format(config))
        config_file = os.path.join(os.getcwd(), config)
        if os.path.isfile(config_file):
            self.config = configparser.ConfigParser()
            self.config.read(config_file)
        else:
            print('ERROR: Unable To Load Config File: {}'.format(config_file))
            sys.exit(1)

        self._load_config_values()
        self._validate_logging_level()
        self._validate_torrent_client()
        print('Configuration Successfully Loaded')

    def _load_config_values(self):

        # General
        self.delay = self.config['GENERAL'].getint('Delay', fallback=2)
        self.output = self.config['GENERAL'].getboolean('Output', fallback=True)
        self.hostname = self.config['GENERAL'].get('Hostname')
        if not self.hostname:
            self.hostname = socket.gethostname()


        # InfluxDB
        self.influx_address = self.config['INFLUXDB']['Address']
        self.influx_port = self.config['INFLUXDB'].getint('Port', fallback=8086)
        self.influx_database = self.config['INFLUXDB'].get('Database', fallback='speedtests')
        self.influx_user = self.config['INFLUXDB'].get('Username', fallback='')
        self.influx_password = self.config['INFLUXDB'].get('Password', fallback='')
        self.influx_ssl = self.config['INFLUXDB'].getboolean('SSL', fallback=False)
        self.influx_verify_ssl = self.config['INFLUXDB'].getboolean('Verify_SSL', fallback=True)

        #Logging
        self.logging = self.config['LOGGING'].getboolean('Enable', fallback=False)
        self.logging_level = self.config['LOGGING']['Level'].lower()
        self.logging_file = self.config['LOGGING']['LogFile']
        self.logging_censor = self.config['LOGGING'].getboolean('CensorLogs', fallback=True)

        # TorrentClient
        self.tor_client = self.config['TORRENTCLIENT'].get('Client', fallback=None)
        self.tor_client_user = self.config['TORRENTCLIENT'].get('Username', fallback=None)
        self.tor_client_password = self.config['TORRENTCLIENT'].get('Password', fallback=None)
        self.tor_client_url = self.config['TORRENTCLIENT'].get('Url', fallback=None)

    def _validate_torrent_client(self):

        if self.tor_client not in self.valid_torrent_clients:
            print('ERROR: {} Is Not a Valid or Support Torrent Client.  Aborting'.format(self.tor_client))
            sys.exit(1)

    def _validate_logging_level(self):
        """
        Make sure we get a valid logging level
        :return:
        """

        valid_levels = ['critical', 'error', 'warning', 'info', 'debug']
        if self.logging_level in valid_levels:
            self.logging_level = self.logging_level.upper()
            return
        else:
            print('Invalid logging level provided. {}'.format(self.logging_level))
            print('Logging will be disabled')
            print('Valid options are: {}'.format(', '.join(valid_levels)))
            self.logging = None


class influxdbSeedbox():

    def __init__(self, config=None):

        self.config = configManager(config=config)

        self.output = self.config.output
        self.logger = None
        self.delay = self.config.delay

        self.influx_client = InfluxDBClient(
            self.config.influx_address,
            self.config.influx_port,
            database=self.config.influx_database,
            ssl=self.config.influx_ssl,
            verify_ssl=self.config.influx_verify_ssl
        )
        self._set_logging()

        if self.config.tor_client == 'deluge':
            print('Generating Deluge Client')
            self.tor_client = DelugeClient(self.send_log,
                                           username=self.config.tor_client_user,
                                           password=self.config.tor_client_password,
                                           url=self.config.tor_client_url,
                                           hostname=self.config.hostname)

    def _set_logging(self):
        """
        Create the logger object if enabled in the config
        :return: None
        """

        if self.config.logging:
            print('Logging is enabled.  Log output will be sent to {}'.format(self.config.logging_file))
            self.logger = logging.getLogger(__name__)
            self.logger.setLevel(self.config.logging_level)
            formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
            fhandle = logging.FileHandler(self.config.logging_file)
            fhandle.setFormatter(formatter)
            self.logger.addHandler(fhandle)

    def send_log(self, msg, level):
        """
        Used as a shim to write log messages.  Allows us to sanitize input before logging
        :param msg: Message to log
        :param level: Level to log message at
        :return: None
        """

        if not self.logger:
            return

        # Make sure a good level was given
        if not hasattr(self.logger, level):
            self.logger.error('Invalid log level provided to send_log')
            return

        output = self._sanitize_log_message(msg)

        log_method = getattr(self.logger, level)
        log_method(output)

    def _sanitize_log_message(self, msg):
        """
        Take the incoming log message and clean and sensitive data out
        :param msg: incoming message string
        :return: cleaned message string
        """

        if not self.config.logging_censor:
            return msg

        # Remove server addresses
        msg = msg.replace(self.config.tor_client_url, 'http://*******:8112/json')

        # Remove IP addresses
        for match in re.findall(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", msg):
            msg = msg.replace(match, '***.***.***.***')

        return msg

    def write_influx_data(self, json_data):
        """
        Writes the provided JSON to the database
        :param json_data:
        :return:
        """
        if self.output:
            print(json_data)

        # TODO This bit of fuckery may turn out to not be a good idea.
        """
        The idea is we only write 1 series at a time but we can get passed a bunch of series.  If the incoming list
        has more than 1 thing, we know it's a bunch of points to write.  We loop through them and recursively call this
        method which each series.  The recursive call will only have 1 series so it passes on to be written to Influx.

        I know, brilliant right?  Probably not
        """
        if len(json_data) > 1:
            for series in json_data:
                self.write_influx_data(series)
            return

        try:
            self.influx_client.write_points(json_data)
        except (InfluxDBClientError, ConnectionError, InfluxDBServerError) as e:
            if hasattr(e, 'code') and e.code == 404:
                print('Database {} Does Not Exist.  Attempting To Create')

                self.send_log('Database {} Does Not Exist.  Attempting To Create', 'error')

                # TODO Grab exception here
                self.influx_client.create_database(self.config.influx_database)
                self.influx_client.write_points(json_data)

                return

            self.send_log('Failed to write data to InfluxDB', 'error')

            print('ERROR: Failed To Write To InfluxDB')
            print(e)

        self.send_log('Written To Influx: {}'.format(json_data), 'debug')



    def run(self):
        while True:
            self.tor_client.get_all_torrents()
            torrent_json = self.tor_client.process_torrents()
            if torrent_json:
                self.write_influx_data(torrent_json)
            self.tor_client.get_active_plugins()
            tracker_json = self.tor_client.process_tracker_list()
            if tracker_json:
                self.write_influx_data(tracker_json)
            time.sleep(self.delay)


class TorrentClient:
    """
    Stub class to base individual torrent client classes on
    """
    def __init__(self, logger, username=None, password=None, url=None, hostname=None):

        self.send_log = logger
        self.hostname = hostname

        # TODO Validate we're not getting None

        # API Data
        self.username = username
        self.password = password
        self.url = url

        # Torrent Data
        self.torrent_client = None
        self.torrent_list = {}
        self.trackers = []
        self.active_plugins = []

    def _create_request(self):
        raise NotImplementedError

    def _process_response(self, res):
        raise NotImplementedError

    def _authenticate(self):
        raise NotImplementedError

    def get_all_torrents(self):
        raise NotImplementedError

    def get_active_plugins(self):
        raise NotImplementedError

    def process_tracker_list(self):
        raise NotImplementedError

    def process_torrents(self):
        raise NotImplementedError


class DelugeClient(TorrentClient):

    def __init__(self, logger, username=None, password=None, url=None, hostname=None):
        TorrentClient.__init__(self, logger, username=username, password=password, url=url, hostname=hostname)

        self.session_id = None
        self.request_id = 0
        self.torrent_client = 'Deluge'

        self._authenticate()

    def _add_common_headers(self, req):
        """
        Add common headers needed to make the API requests
        :return: request
        """

        self.send_log('Adding headers to request', 'info')

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        for k, v in headers.items():
            req.add_header(k, v)

        if self.session_id:
            req.add_header('Cookie', self.session_id)

        return req

    def _check_session(self):
        """
        Make sure we still have an active session. If not, authenticate again
        :return:
        """

        self.send_log('Checking Session State', 'debug')

        req = self._create_request(method='auth.check_session', params=[''])

        try:
            res = urlopen(req)
        except URLError as e:
            msg = 'Failed To check session state.  HTTP Error'
            self.send_log(msg, 'error')
            print(msg)
            print(e)
            return None

        result = self._process_response(res)

        if not result:
            self.send_log('No active session. Attempting to re-authenticate', 'error')
            self._authenticate()
            return

        self.send_log('Session is still active', 'debug')

    def _create_request(self, method=None, params=None):
        """
        Creates and returns a Request object, Allowing us to track request IDs in one spot.
        We also add the common headers here
        :return:
        """

        # TODO Validate method and params
        data = json.dumps({
            'id': self.request_id,
            'method': method,
            'params': params
        }).encode('utf-8')

        req = self._add_common_headers(Request(self.url, data=data))
        self.request_id += 1

        return req

    def _process_response(self, res):
        """
        Take the response object and return JSON
        :param res:
        :return:
        """
        # TODO Figure out exceptions here
        if res.headers['Content-Encoding'] == 'gzip':
            self.send_log('Detected gzipped response', 'debug')
            raw_output = gzip.decompress(res.read()).decode('utf-8')
        else:
            self.send_log('Detected other type of response encoding: {}'.format(res.headers['Content-Encoding']), 'debug')
            raw_output = res.read().decode('utf-8')

        json_output = json.loads(raw_output)

        return json_output if json_output['result'] else None

    def _authenticate(self):
        """
        Authenticate against torrent client so we can make future requests
        If we return from this method we assume we are authenticated for all future requests
        :return: None
        """
        msg = 'Attempting to authenticate against {} API'.format(self.torrent_client)
        self.send_log(msg, 'info')
        print(msg)

        req = self._create_request(method='auth.login', params=[self.password])

        try:
            res = urlopen(req)
        except URLError as e:
            msg = 'Failed To Authenticate with torrent client.  HTTP Error'
            self.send_log(msg, 'critical')
            print(msg)
            print(e)
            sys.exit(1)

        # We need the session ID to send with future requests
        self.session_id = res.headers['Set-Cookie'].split(';')[0]

        output = self._process_response(res)

        if output and not output['result']:
            msg = 'Failed to authenticate to {} API. Aborting'.format(self.torrent_client)
            self.send_log(msg, 'error')
            print(msg)
            sys.exit(1)

        msg = 'Successfully Authenticated With {} API'.format(self.torrent_client)
        self.send_log(msg, 'info')
        print(msg)

    def get_all_torrents(self):
        """
        Return a list of all torrents from the API
        :return:
        """

        req = self._create_request(method='core.get_torrents_status', params=['',''])
        try:
            self._check_session() # Make sure we still have an active session
            res = urlopen(req)
        except URLError as e:
            msg = 'Failed to get list of torrents.  HTTP Error'
            self.send_log(msg, 'error')
            print(msg)
            print(e)
            self.torrent_list = []
            return

        output = self._process_response(res)
        if output['error']:
            msg = 'Problem getting torrent list from {}. Error: {}'.format(self.torrent_client, output['error'])
            print(msg)
            self.send_log(msg, 'error')
            self.torrent_list = []
            return

        self.torrent_list = output['result']

        # Temp trap to find weird characters that won't decode
        """
        for k, v in output['result'].items():
            print(k)
            print(v.keys())
            for k2, v2 in v.items():
                try:
                    print('Key: ' + k2)
                    print('Value: ' + str(v2))
                except Exception as e:
                    print('test')
                    print(e)
        """


    def get_active_plugins(self):
        """
        Return all active plugins
        :return:
        """

        req = self._create_request(method='core.get_enabled_plugins', params=[])
        try:
            self._check_session() # Make sure we still have an active session
            res = urlopen(req)
        except URLError as e:
            msg = 'Failed to get list of plugins.  HTTP Error'
            self.send_log(msg, 'error')
            print(msg)
            print(e)
            self.active_plugins = []
            return

        output = self._process_response(res)
        if output['error']:
            msg = 'Problem getting plugin list from {}. Error: {}'.format(self.torrent_client, output['error'])
            print(msg)
            self.send_log(msg, 'error')
            self.active_plugins = []
            return

        self.active_plugins = output['result']


    def process_tracker_list(self):
        """
        Loop through each torrent and pull the tracker data.  This will allow us to track how many torrents we are
        downloading from each tracker
        :return:
        """

        if len(self.torrent_list) == 0:
            return None

        trackers = {}
        json_list = []

        # The tracker list is a dict of torrent hashes.  The value for each hash is another dict with data about the
        # torrent
        for hash, data in self.torrent_list.items():
            if data['tracker_host'] in trackers:
                trackers[data['tracker_host']]['total_torrents'] += 1
                trackers[data['tracker_host']]['total_upload'] += data['total_uploaded']
                trackers[data['tracker_host']]['total_download'] += data['all_time_download']
            else:
                trackers[data['tracker_host']] = {}
                trackers[data['tracker_host']]['total_torrents'] = 1
                trackers[data['tracker_host']]['total_upload'] = data['total_uploaded']
                trackers[data['tracker_host']]['total_download'] = data['all_time_download']

        for k, v in trackers.items():

            total_ratio = round(v['total_upload'] / v['total_download'], 3)
            tracker_json = [
                {
                    'measurement': 'trackers',
                    'fields': {
                        'total_torrents': v['total_torrents'],
                        'total_upload': v['total_upload'],
                        'total_download': v['total_download'],
                        'total_ratio': total_ratio
                    },
                    'tags': {
                        'host': self.hostname,
                        'tracker': k
                    }
                }
            ]
            #return tracker_json
            json_list.append(tracker_json)
        return json_list


    def process_torrents(self):
        """
        Go through the list of torrents, format them in JSON and send to influx
        :return:
        """
        if len(self.torrent_list) == 0:
            return None

        json_list = []

        for hash, data in self.torrent_list.items():

            torrent_json = [
                {
                    'measurement': 'torrents',
                    'fields': {
                        'hash': hash,
                        'tracker': data['tracker_host'],
                        'name': data['name'],
                        'state': data['state'],
                        'uploaded': data['total_uploaded'],
                        'downloaded': data['all_time_download'],
                        'ratio': round(data['ratio'], 2),
                        'progress': round(data['progress'], 2),
                        'seeds': data['total_seeds'],
                        'size': data['total_size'],
                        'total_files': data['num_files'],
                    },
                    'tags': {

                        'host': self.hostname,
                        'hash': hash,
                        'tracker': data['tracker_host'],

                    }
                }
            ]
            #return torrent_json
            json_list.append(torrent_json)
        return json_list

def main():

    parser = argparse.ArgumentParser(description="A tool to send Torrent Client statistics to InfluxDB")
    parser.add_argument('--config', default='config.ini', dest='config', help='Specify a custom location for the config file')
    args = parser.parse_args()
    monitor = influxdbSeedbox(config=args.config)
    monitor.run()


if __name__ == '__main__':
    main()
