import urllib.request
from urllib.request import Request, urlopen, URLError
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
import json
import re
from clients.torrentclient import TorrentClient

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

        self.send_log('Attempting To Get Token From URL {}'.format(token_url), 'info')

        opener.open(token_url)
        urllib.request.install_opener(opener)
        req = Request(self.url + '/token.html')
        res = urlopen(req)
        self.cookie = res.headers['Set-Cookie'].split(';')[0]
        soup = BeautifulSoup(res, 'html.parser')
        token = soup.find("div", {"id": "token"}).text
        self.send_log('Got Token: {}'.format(token), 'info')
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
        msg = 'Creating request with url: {}'.format(url)
        self.send_log(msg, 'debug')

        req = self._add_common_headers(Request(url))

        return req

    def _build_torrent_list(self, torrents):
        """
        Take the resulting torrent list and create a consistent structure shared through all clients
        :return:
        """

        self.send_log('Structuring list of torrents', 'debug')

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
        self.send_log(msg, 'debug')

        req = self._create_request(params='action=getprops&hash={}'.format(hash))

        try:
            res = urlopen(req).read().decode('utf-8')
        except URLError as e:
            msg = 'Failed to get trackers from URL for hash {}'.format(hash)
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
        self.send_log(msg, 'debug')

        req = self._create_request(params='action=getfiles&hash={}'.format(hash))

        try:
            res = urlopen(req).read().decode('utf-8')
        except URLError as e:
            msg = 'Failed to get file list from URL for hash {}'.format(hash)
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
        self.send_log(msg, 'debug')

        req = self._create_request(params='list=1')

        try:
            res = urlopen(req)
            final = res.read().decode('utf-8')
        except URLError as e:
            msg = 'Failed to get list of all torrents'
            print(e)
            self.send_log(msg, 'error')
            self.torrent_list = {}
            return

        final_json = json.loads(final)

        self._build_torrent_list(final_json['torrents'])