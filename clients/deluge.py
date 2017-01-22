from clients.torrentclient import TorrentClient
from urllib.request import Request, urlopen, URLError
import json
import sys
import gzip


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
        # TODO pass this to parent
        self.send_log('Adding headers to request', 'debug')

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

        res = self._make_request(req, fail_msg='Failed To check session state.  HTTP Error')

        if not res:
            return

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

        return json_output

    def _authenticate(self):
        """
        Authenticate against torrent client so we can make future requests
        If we return from this method we assume we are authenticated for all future requests
        :return: None
        """
        msg = 'Attempting to authenticate against {} API'.format(self.torrent_client)

        req = self._create_request(method='auth.login', params=[self.password])

        res = self._make_request(req, genmsg=msg, fail_msg='Failed to contact API for authentication', abort_on_fail=True)

        output = self._process_response(res)

        # If response has result but it's None than the login failed
        if 'result' in output and not output['result']:
            msg = 'Failed to authenticate to {} API. Check your password and try again.'.format(self.torrent_client)
            self.send_log(msg, 'critical')
            sys.exit(1)

        # We need the session ID to send with future requests
        if 'Set-Cookie' in res.headers:
            self.session_id = res.headers['Set-Cookie'].split(';')[0]
        else:
            self.send_log('No authentication cookie in response.  Aborting', 'critical')
            sys.exit(1)

        msg = 'Successfully Authenticated With {} API'.format(self.torrent_client)
        self.send_log(msg, 'info')

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
            self.torrent_list[hash]['ratio'] = data['ratio']
            self.torrent_list[hash]['total_seeds'] = data['total_seeds']
            self.torrent_list[hash]['state'] = data['state']
            self.torrent_list[hash]['tracker'] = data['tracker_host']
            self.torrent_list[hash]['total_files'] = data['num_files']

    def get_all_torrents(self):
        """
        Return a list of all torrents from the API
        :return:
        """

        self.send_log('Getting list of torrents', 'debug')

        req = self._create_request(method='core.get_torrents_status', params=['',''])

        self._check_session() # Make sure we still have an active session

        res = self._make_request(req, fail_msg='Failed to get list of torrents from API')

        if not res:
            self.torrent_list = {}
            return

        output = self._process_response(res)

        if not output:
            return

        if output['error']:
            msg = 'Problem getting torrent list from {}. Error: {}'.format(self.torrent_client, output['error'])
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