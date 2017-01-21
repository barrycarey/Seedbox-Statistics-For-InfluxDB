__author__ = 'barry'
import urllib.request
from urllib.request import Request, urlopen, URLError
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
import json
import sys
import re
import gzip

# TODO Deal with slashes in client URL
# TODO Unify the final torrent list so it can be built into json structure by parent instead of each child

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

    def _add_common_headers(self, req, headers=None):
        """
        Add common headers to request
        :param req: Request object to add headers to
        :param headers: Dict of headers to add
        :return:
        """

        if not headers:
            return req

        self.send_log('Adding headers to request', 'info')
        for k, v in headers.items():
            req.add_header(k, v)

        return req

    def _create_request(self, method=None, params=None):
        """
        Needs to be implemented in the child to deal with unique API requirements
        :param method: Used in Deluge request
        :param params: Extra data unique to the request
        :return: Request
        """
        raise NotImplementedError

    def _process_response(self, res):
        # TODO May only be needed for deluge.  Remove from parent if that's the case
        raise NotImplementedError

    def _authenticate(self):
        """
        Needs to be implemented in the child to deal with unique API requirements
        :return: None
        """
        raise NotImplementedError

    def _build_torrent_list(self, torrents):
        """
        Take the raw list of torrents from the API and build a unified structure shared by all clients
        Expected to be implemented in each child to deal with unique returns from each API
        :param torrents:
        :return:
        """
        raise NotImplementedError

    def get_all_torrents(self):
        """
        Needs to be implemented in the child to deal with unique API requirements

        Retrieve a list of all torrents from the client.  Send them on to _build_torrent_list() to put the output
        into a consistent format that can be used in the parent

        :return: None
        """
        raise NotImplementedError

    def get_active_plugins(self):
        # TODO probably only needed in Deluge.
        raise NotImplementedError

    def process_tracker_list(self):
        """
        Go through the list of torrents and build the list of trackers
        :return: list of JSON objects for each tracker
        """
        if len(self.torrent_list) == 0:
            return None

        trackers = {}
        json_list = []

        # The tracker list is a dict of torrent hashes.  The value for each hash is another dict with data about the
        # torrent
        for hash, data in self.torrent_list.items():
            if data['tracker'] in trackers:
                trackers[data['tracker']]['total_torrents'] += 1
                trackers[data['tracker']]['total_uploaded'] += data['total_uploaded']
                trackers[data['tracker']]['total_downloaded'] += data['total_downloaded']
                trackers[data['tracker']]['total_size'] += data['total_size']
            else:
                trackers[data['tracker']] = {}
                trackers[data['tracker']]['total_torrents'] = 1
                trackers[data['tracker']]['total_uploaded'] = data['total_uploaded']
                trackers[data['tracker']]['total_downloaded'] = data['total_downloaded']
                trackers[data['tracker']]['total_size'] = data['total_size']

        for k, v in trackers.items():
            print(v)
            total_ratio = round(v['total_uploaded'] / v['total_size'], 3)
            tracker_json = [
                {
                    'measurement': 'trackers',
                    'fields': {
                        'total_torrents': v['total_torrents'],
                        'total_upload': v['total_uploaded'],
                        'total_download': v['total_downloaded'],
                        'total_ratio': total_ratio
                    },
                    'tags': {
                        'host': self.hostname,
                        'tracker': k,
                        'client': self.torrent_client
                    }
                }
            ]

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
                        'tracker': data['tracker'],
                        'name': data['name'],
                        'state': data['state'],
                        'uploaded': data['total_uploaded'],
                        'downloaded': data['total_downloaded'],
                        'ratio': round(data['ratio'], 2),
                        'progress': round(data['progress'], 2),
                        'seeds': data['total_seeds'],
                        'size': data['total_size'],
                        'total_files': data['total_files'],
                    },
                    'tags': {

                        'host': self.hostname,
                        'hash': hash,
                        'tracker': data['tracker'],
                        'client': self.torrent_client

                    }
                }
            ]

            json_list.append(torrent_json)

        return json_list


class UTorrentClient(TorrentClient):

    def __init__(self, logger, username=None, password=None, url=None, hostname=None):
        TorrentClient.__init__(self, logger, username=username, password=password, url=url, hostname=hostname)

        self.token = None
        self.cookie = None
        self.torrent_client = 'uTorrent'

        self._authenticate()

    def _authenticate(self):

        # TODO Clean this whole mess up.  It's barely functional
        pwd_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        pwd_mgr.add_password(None, self.url, self.username, self.password)
        handler = urllib.request.HTTPBasicAuthHandler(pwd_mgr)
        opener = urllib.request.build_opener(handler)
        token_url = self.url + '/token.html'
        print('Attempting To Get Token From URL {}'.format(token_url))
        self.send_log('Attempting To Get Token From URL {}'.format(token_url), 'info')
        opener.open(token_url)
        urllib.request.install_opener(opener)
        req = Request(self.url + '/token.html')
        res = urlopen(req)
        self.cookie = res.headers['Set-Cookie'].split(';')[0]
        soup = BeautifulSoup(res, 'html.parser')
        token = soup.find("div", {"id": "token"}).text
        print('Got Token: ' + token)
        self.token = token

    def _add_common_headers(self, req, headers=None):
        """
        Add common headers to the request
        :param req:
        :return:
        """

        headers = {
            'cache-control': 'no-cache',
            'Cookie': self.cookie
        }

        return TorrentClient._add_common_headers(self, req, headers=headers)

    def _create_request(self, method=None, params=None):
        # TODO Validate that we get params
        url = self.url + '/?token={}&{}'.format(self.token, params)
        print('Creating request with url: ' + url)

        req = self._add_common_headers(Request(url))

        return req

    def _build_torrent_list(self, torrents):
        """
        Take the resulting torrent list and create a consistent structure shared through all clients
        :return:
        """

        msg = 'Structuring list of torrents'
        self.send_log(msg, 'debug')

        for torrent in torrents:
            self.torrent_list[torrent[0]] = {}
            self.torrent_list[torrent[0]]['name'] = torrent[2]
            self.torrent_list[torrent[0]]['total_size'] = torrent[3]
            self.torrent_list[torrent[0]]['progress'] = torrent[4] / 1000 * 100
            self.torrent_list[torrent[0]]['total_downloaded'] = torrent[5]
            self.torrent_list[torrent[0]]['total_uploaded'] = torrent[6]
            self.torrent_list[torrent[0]]['ratio'] = torrent[7] / 1000
            self.torrent_list[torrent[0]]['total_seeds'] = torrent[15]
            self.torrent_list[torrent[0]]['state'] = torrent[22]
            self.torrent_list[torrent[0]]['tracker'] = self._get_tracker(torrent[0])
            self.torrent_list[torrent[0]]['total_files'] = self._get_file_count(torrent[0])


    def _get_tracker(self, hash):
        """
        Get the tracker for a specific torrent for uTorrent
        :param hash:
        :return:
        """

        msg = 'Attempting to get tracker for hash {}'.format(hash)
        print(msg)
        self.send_log(msg, 'debug')
        req = self._create_request(params='action=getprops&hash={}'.format(hash))

        try:
            res = urlopen(req).read().decode('utf-8')
        except URLError as e:
            msg = 'Failed to get trackers from URL for hash {}'.format(hash)
            print(msg)
            self.send_log(msg, 'error')
            return 'N/A'

        res_json = json.loads(res)

        tracker = res_json['props'][0]['trackers'].split()[0]

        tracker_url = urlsplit(tracker).netloc

        # TODO Exception here.  Deal with it or just return URL with port
        # Remove port from URL
        for match in re.findall(r":\d{4,4}", tracker_url):
            tracker_url = tracker_url.replace(match, '')

        return tracker_url

    def _get_file_count(self, hash):
        """
        Method for uTorrent to get total file since it requires another API call
        :param hash:
        :return:
        """

        msg = 'Attempting to get file list for hash {}'.format(hash)
        print(msg)
        self.send_log(msg, 'debug')

        req = self._create_request(params='action=getfiles&hash={}'.format(hash))

        try:
            res = urlopen(req).read().decode('utf-8')
        except URLError as e:
            msg = 'Failed to get file list from URL for hash {}'.format(hash)
            print(msg)
            self.send_log(msg, 'error')
            return 'N/A'

        res_json = json.loads(res)

        return len(res_json['files'][1])

    def get_all_torrents(self):
        """
        Get all torrents that are currently active
        :return:
        """

        msg = 'Attempting to get all torrents from {}'.format(self.url)
        print(msg)
        self.send_log(msg, 'info')

        req = self._create_request(params='list=1')

        try:
            res = urlopen(req)
            final = res.read().decode('utf-8')
        except URLError as e:
            msg = 'Failed to get list of all torrents'
            print(msg)
            print(e)
            self.send_log(msg, 'error')
            self.torrent_list = {}
            return

        final_json = json.loads(final)

        self._build_torrent_list(final_json['torrents'])




class DelugeClient(TorrentClient):

    def __init__(self, logger, username=None, password=None, url=None, hostname=None):
        TorrentClient.__init__(self, logger, username=username, password=password, url=url, hostname=hostname)

        self.session_id = None
        self.request_id = 0
        self.torrent_client = 'Deluge'

        self._authenticate()

    def _add_common_headers(self, req, headers=None):
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

    def _build_torrent_list(self, torrents):
        """
        Take the resulting torrent list and create a consistent structure shared through all clients
        :return:
        """
        msg = 'Structuring list of torrents'
        self.send_log(msg, 'debug')

        for hash, data in torrents.items():
            self.torrent_list[hash] = {}
            self.torrent_list[hash]['name'] = data['name']
            self.torrent_list[hash]['total_size'] = data['total_size']
            self.torrent_list[hash]['progress'] = round(data['progress'], 2)
            self.torrent_list[hash]['total_downloaded'] = data['all_time_download']
            self.torrent_list[hash]['total_uploaded'] = data['total_uploaded']
            self.torrent_list[hash]['ratio'] = round(data['ratio'], 2)
            self.torrent_list[hash]['total_seeds'] = data['total_seeds']
            self.torrent_list[hash]['state'] = data['state']
            self.torrent_list[hash]['tracker'] = data['tracker_host']
            self.torrent_list[hash]['total_files'] = data['num_files']


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
            self.torrent_list = {}
            return

        output = self._process_response(res)
        if output['error']:
            msg = 'Problem getting torrent list from {}. Error: {}'.format(self.torrent_client, output['error'])
            print(msg)
            self.send_log(msg, 'error')
            self.torrent_list = {}
            return

        self._build_torrent_list(output['result'])

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




