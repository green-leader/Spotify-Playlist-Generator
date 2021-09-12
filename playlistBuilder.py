import os
from azure.identity import EnvironmentCredential
from azure.keyvault.secrets import SecretClient

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from AKVCacheHandler import AzureKeyVaultCacheHandler

# list of podcast shows to filter out
filter_show = ['spotify:show:6v1kAUP76SLtLI7ApsEgdH', 'spotify:show:0RrdRP2clWr5XCAYYA2j2A', 'spotify:show:0oYGnOWNIj93Q1CCfQ4Mj8', 'spotify:show:2GmNzw8t4uG70rn4XG9zcC']

VAULT_URL = os.environ["VAULT_URL"]

credential = EnvironmentCredential()
client = SecretClient(vault_url=VAULT_URL, credential=credential)

SCOPE = "playlist-modify-public,playlist-modify-private,playlist-read-private,user-library-read,user-read-playback-position, user-read-recently-played"

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id="91ed165161494fffae34d89d02619204",
                                               client_secret=client.get_secret("SpotifyClientSecret").value,
                                               redirect_uri="http://localhost/callback",
                                               scope=SCOPE,
                                               cache_handler=AzureKeyVaultCacheHandler()))

def get_playlist(field, search):
    '''Search through all of the playlists, and return the first uri that matches by field'''
    playlists = sp.current_user_playlists()
    while playlists:
        for playlist in playlists['items']:
            if playlist[field] == search:
                return playlist['uri']
        if playlists['next']:
            playlists = sp.next(playlists)
        else:
            playlists = None
    return None


def cullShows(items, filterList):
    '''
    Remove podcast shows we don't care for
    '''
    itemEpisodes = [ show['uri'] for show in items if show['uri'].split(':')[1] == 'episode' ]
    episodeLookup = [ episode['uri'] for episode in sp.episodes(itemEpisodes)['episodes'] ]

    return [x for x in items if x['uri'] not in episodeLookup ]


# Create playlist
def create_playlist(name, description=''):
    '''
    Create a playlist and return the playlistID.
    If the playlist already exists clean out the contents.
    '''
    PlaylistID = get_playlist('name', name)
    if not PlaylistID:
        sp.user_playlist_create(sp.me()['id'], name, public=False, description=description)

    return PlaylistID


def playlistTemplate(templateName):
    templatePlaylistID = get_playlist('name', templateName)

    fields='items(track),next' # Next permits pagination
    newPlaylist = [ playlistItem['track'] for playlistItem in sp.playlist_items(templatePlaylistID, fields=fields)['items'] if playlistItem['track'] is not None]
    tracks = list()
    episodes = list()
    for item in newPlaylist:
        if item['uri'].split(':')[1] == 'track':
            tracks.append(item)
        else:
            episodes.append(item)


    return tracks, episodes


def PodcastEpisodeListing():
    '''
    Retrieve a few episodes from all of the shows the user follows. Return in descending order of release.
    '''
    allEpisodes = list()

    savedShows = sp.current_user_saved_shows()
    while savedShows:
        itemsSavedShows = [ showSavedShows['show']['uri'] for showSavedShows in savedShows['items'] ]

        for itemSavedShow in itemsSavedShows:

            showEpisodes = sp.show_episodes(itemSavedShow)
            episodeListing = list()
            while showEpisodes:

                # Use pagination to grab batches of 50 and dump the episodes we've heard before.
                # Don't move on until we have 50 from each show.
                tempEpisodes = [ episode for episode in showEpisodes['items'] if not episode['resume_point']['fully_played'] \
                    and (episode['duration_ms'] - episode['resume_point']['resume_position_ms']) >= 120000 ]

                if len(tempEpisodes) < 50:
                    episodeListing.extend(tempEpisodes)
                    tempEpisodes = None
                else:
                    break 

                if showEpisodes['next']:
                    showEpisodes = sp.next(showEpisodes)
                else:
                    showEpisodes = None
            allEpisodes.extend(episodeListing)

        if savedShows['next']:
            savedShows = sp.next(savedShows)
        else:
            savedShows = None

    # sorted works on any iterable
    # reverse for descending order of date.
    allEpisodes = sorted(allEpisodes, key=lambda episode: episode['release_date'], reverse=True)
    return allEpisodes


def removeTracks(tracks, exclude=None):
    '''
    Remove duplicates and recently played
    Exclude is an optional argument wherein you can specify an existing playlist to use it's contents as a base to remove.
    '''

    # Get recently played
    # it would be nice to have 100 but it looks like the endpoint only supports 50
    recentPlayed = sp.current_user_recently_played()
    recentPlayedURI = list()
    while recentPlayed:
        recentPlayedURI.extend([recent['track']['uri'] for recent in recentPlayed['items']])
        if len(recentPlayedURI) < 50 and recentPlayed['next']:
            recentPlayed = sp.next(recentPlayed)
        else:
            recentPlayed = None

    if exclude is not None:
        excludeList = exclude['items']
        for recent in excludeList:
            if recent['track'] is None:
                continue
            if recent['track']['uri'].split(':')[1] == 'track':
                recentPlayedURI.append(recent['track']['uri'])

    noDupes = dict()
    for track in tracks:
        if track['uri'] not in recentPlayedURI:
            noDupes[track['uri']] = track

    newTracks = [track for track in noDupes.values()]
    trackRecommendCount = len(tracks) - len(newTracks)
    if trackRecommendCount:
        recommendations = sp.recommendations(seed_tracks=[track['id'] for track in tracks[:5]], limit=(trackRecommendCount))
        newTracks.extend(recommendations['tracks'])
    return newTracks

def mainBuild(plName, plDescription=''):
    DailyListenID = create_playlist(name=plName, description=plDescription)
    tracks, episodes = playlistTemplate(templateName='Daily Drive')
    tracks = removeTracks(tracks, exclude=sp.playlist_items(DailyListenID))
    # Cull out blacklisted shows
    episodes = cullShows(episodes, filter_show)
    allEpisodes = PodcastEpisodeListing()


    # sampleData = ['spotify:track:3DKmwMaqRTOW5Ba5dHijgX', 'spotify:episode:19dyBsqL2gX74pFXK4RSNb', 'spotify:track:4yVJTuaJ4NlCaCUYe9ElIz', 'spotify:track:71hhuJLNpxBQLSbbQ6ZWr4', 'spotify:track:7j31rVgGX9Q2blT92VBEA0', 'spotify:track:7uSsHbBFFAnkRQR1rDwP3L', 'spotify:episode:1wF3w9zP9jlY1sdPbu2ala', 'spotify:track:1N3bdxmsu3wimLy3E4d4cf', 'spotify:track:707mVFEVPIpTWaejXjI7TY', 'spotify:track:5qNEPKqPOECw50RpOGT9ne', 'spotify:track:4DijrJqz7WYjnjHmvdlAyB', 'spotify:track:50jXnyrzW4mcBBqFTMEoAC', 'spotify:track:4wD6EgZCok8Qb5Fs8jszYc', 'spotify:track:6qZjm61s6u8Ead9sWxCDro', 'spotify:track:6QEvc1Xriqvn70EG2VrDy3', 'spotify:track:3SUNHWszXHmCx0J668tqq1', 'spotify:track:11cjKlgVaUvbBjEAAGv9MZ', 'spotify:track:0d28khcov6AiegSCpG5TuT', 'spotify:track:2zzLRQ78kKfPTx8FJQCdC2', 'spotify:track:4WQs5UIokNcsxWumMEfDt3', 'spotify:track:3p0rvHL2zfHAlXAgnHC4GI', 'spotify:track:72hSmnleYTiiOo23q8ZJIS', 'spotify:track:5AKYyNPYhumqKeOMhdEgQO', 'spotify:track:5ylAFXgB62LXZBxUy6cmYg', 'spotify:track:7vA9zWg6fmjLZn105Uj4TE', 'spotify:track:4jFLw7QqWlv3lZr980HyYW', 'spotify:track:03wKMRNYVvw6s9nm4I4jUS', 'spotify:track:7tCHpjktA50ihtkLz6bAnn', 'spotify:track:20I8RduZC2PWMWTDCZuuAN', 'spotify:track:1MzAV3ZqGVU2cmmwmJwymM', 'spotify:track:6E69aBnq0hr6cTGBo39cWD', 'spotify:episode:4Hkx7uiqlmrR4oPzpp2rsk', 'spotify:episode:5oxZSKaJjyjgo10bj7M8Xk', 'spotify:episode:6xYAXwz6oDPE6ApMt1HzV5', 'spotify:episode:5OO67nxhbmCS08l9IDt3It', 'spotify:episode:2yRvXnC1JQzGTmq9kqpCnH', 'spotify:episode:2om6UMZbU7PjLCUFQljNv6', 'spotify:episode:0WlyKekrux44Lxj1Mq2m9u', 'spotify:episode:0txUTbvgXbC57WpgzDXr0z', 'spotify:episode:6rqWdosPJz53cQRzeQ9nfF', 'spotify:episode:4HBdWIIQtrAz10G20esHaY', 'spotify:episode:783lK8XOohpbxoAIpOJyhk', 'spotify:episode:3NdbtyXttT6yJrvsFNIbG0', 'spotify:episode:6oEqn3yJ4I1VNssUGlbWgW', 'spotify:episode:1rPkyn605umnRfJMEbHhsd']

    for episode in episodes:
        allEpisodes.insert(0, episode)

    sortedPlaylist = list()

    while len(tracks) > 0:
        sortedPlaylist.append(allEpisodes.pop(0)['uri'])
        sortedPlaylist.append(tracks.pop(0)['uri'])
        try:
            sortedPlaylist.append(tracks.pop(0)['uri'])
        except IndexError:
            pass

    sp.user_playlist_replace_tracks(sp.me()['id'], DailyListenID, tracks=sortedPlaylist)


if __name__ == "__main__":
    mainBuild(plName="Daily Listen - Staging")