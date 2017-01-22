__author__ = 'barry'
from urllib.request import urlopen, URLError
import sys

# TODO Deal with slashes in client URL

"""
Base class for torrent clients
"""

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

        self.send_log('Adding headers to request', 'debug')
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

    def _make_request(self, req, genmsg='', fail_msg='', abort_on_fail=None):
        """
        Make the web request.  Doing it here avoids a lot of duplicate exception handling
        :param gen_msg: Message we can print to console or logs so we know about the request
        :param fail_msg: Message we can print to console or logs on failure
        :param abort_on_fail: Exit on failed request
        :return: Response
        """

        if genmsg:
            self.send_log(genmsg, 'info')

        try:
            res = urlopen(req)
        except URLError as e:

            if fail_msg:
                msg = fail_msg
            else:
                msg = 'Failed to make request'

            if abort_on_fail:
                self.send_log(msg, 'critical')
                self.send_log('Aborting', 'critical')
                sys.exit(1)
            else:
                self.send_log(msg, 'error')

            return None

        return res

    def _process_response(self, res):
        """
        Perform response handling for the specific torrent client.  Each line requires different processing/decoding of
        the response
        :param res:
        :return:
        """
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
                trackers[data['tracker']]['total_ratio'] += data['ratio']
            else:
                trackers[data['tracker']] = {}
                trackers[data['tracker']]['total_torrents'] = 1
                trackers[data['tracker']]['total_uploaded'] = data['total_uploaded']
                trackers[data['tracker']]['total_downloaded'] = data['total_downloaded']
                trackers[data['tracker']]['total_size'] = data['total_size']
                trackers[data['tracker']]['total_ratio'] = data['ratio']

        for k, v in trackers.items():

            tracker_json = [
                {
                    'measurement': 'trackers',
                    'fields': {
                        'total_torrents': v['total_torrents'],
                        'total_upload': v['total_uploaded'],
                        'total_download': v['total_downloaded'],
                        'total_ratio': v['total_ratio'],
                        'tracker': k,
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


