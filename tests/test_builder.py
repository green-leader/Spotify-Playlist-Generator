import unittest
from playlistbuilder import PlaylistGenerator
from playlistbuilder import _is_played


sampleepisode = {'audio_preview_url': 'https://p.scdn.co/mp3-preview/060812a16680d06fbb4def02c4ada0e02f9af98c', 'description': '<description snipped>', 'duration_ms': 1432943, 'explicit': False, 'external_urls': {'spotify': 'https://open.spotify.com/episode/0BqdbC2mOYXI6ywXpVpiMc'}, 'href': 'https://api.spotify.com/v1/episodes/0BqdbC2mOYXI6ywXpVpiMc', 'html_description': '<description snipped>', 'id': '0BqdbC2mOYXI6ywXpVpiMc', 'images': [{'height': 640, 'url': 'https://i.scdn.co/image/1b5af843be11feb6c563e0d95f5fe0dad659b757', 'width': 640}, {'height': 300, 'url': 'https://i.scdn.co/image/ef570afd43d43da66c9e5df3957e049f5c3464c3', 'width': 300}, {'height': 64, 'url': 'https://i.scdn.co/image/7fe2b992063ef9490d236547b1eccee07db8a87d', 'width': 64}], 'is_externally_hosted': False, 'is_playable': True, 'language': 'en', 'languages': ['en'], 'name': 'Why Spending Too Little Could Backfire on Democrats', 'release_date': '2021-10-26', 'release_date_precision': 'day', 'resume_point': {'fully_played': False, 'resume_position_ms': 0}, 'type': 'episode', 'uri': 'spotify:episode:0BqdbC2mOYXI6ywXpVpiMc'}  # noqa: E501

class Test_is_played_Method(unittest.TestCase):
    def test_is_played_not_played(self,):
        episode = sampleepisode.copy()
        episode['resume_point']['fully_played'] = False
        episode['resume_point']['resume_position_ms'] = 0
        assert _is_played(episode) == False

    def test_is_played_fully_played(self,):
        episode = sampleepisode.copy()
        episode['resume_point']['fully_played'] = True
        assert _is_played(episode) == True

    def test_is_played_partially_played(self,):
        episode = sampleepisode.copy()
        episode['resume_point']['fully_played'] = False
        episode['resume_point']['resume_position_ms'] = episode['duration_ms'] - 60000
        assert _is_played(episode) == True
    
    def test_is_played_short_episode(self,):
        episode = sampleepisode.copy()
        episode['resume_point']['fully_played'] = False
        episode['duration_ms'] = 59999
        assert _is_played(episode) == False


class TestInitMethod(unittest.TestCase):
    def test_no_plname_given(self,):
        with self.assertRaises(AttributeError) as context:
            build = PlaylistGenerator()
