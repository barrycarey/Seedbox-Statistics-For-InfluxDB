from rtorrent import RTorrent
from clients.torrentclient import TorrentClient
import sys
from urllib.parse import urlsplit


class rTorrentClient(TorrentClient):

    def __init__(self, logger, username=None, password=None, url=None, hostname=None):

        TorrentClient.__init__(self, logger, username=username, password=password, url=url, hostname=hostname)
        self.torrent_client = 'rTorrent'
        self._authenticate()
        self.rtorrent = None

        self._authenticate()

    def _authenticate(self):
        """
        Setup connection to rTorrent XMLRPC server
        :return:
        """

        try:
            self.rtorrent = RTorrent(self.url)
        except ConnectionRefusedError as e:
            self.send_log('Failed to connect to rTorrent.  Aborting', 'critical')
            sys.exit(1)

        self.send_log('Successfully connected to rTorrent', 'info')

    def _build_torrent_list(self, torrents):
        """
        Take the resulting torrent list and create a consistent structure shared through all clients
        :return:
        """
        self.send_log('Structuring list of torrents', 'debug')

        for torrent in torrents:
            self.torrent_list[torrent.info_hash] = {}
            self.torrent_list[torrent.info_hash]['name'] = torrent.name
            self.torrent_list[torrent.info_hash]['total_size'] = torrent.size_bytes
            self.torrent_list[torrent.info_hash]['progress'] = round((torrent.bytes_done / torrent.size_bytes * 100), 2)
            self.torrent_list[torrent.info_hash]['total_downloaded'] = torrent.bytes_done
            self.torrent_list[torrent.info_hash]['total_uploaded'] = 1 # TODO Need to figure out where to get this
            self.torrent_list[torrent.info_hash]['ratio'] = torrent.ratio
            self.torrent_list[torrent.info_hash]['total_seeds'] = 'N/A'
            self.torrent_list[torrent.info_hash]['state'] = torrent.get_state()
            self.torrent_list[torrent.info_hash]['tracker'] = urlsplit(torrent.get_trackers()[0].url).netloc
            self.torrent_list[torrent.info_hash]['total_files'] = torrent.size_files


    def get_all_torrents(self):
        """
        Return list of all torrents
        :return:
        """
        self._build_torrent_list(self.rtorrent.torrents)
