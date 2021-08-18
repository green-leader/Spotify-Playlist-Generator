import spotipy
from spotipy.oauth2 import SpotifyOAuth

with open("./.secrets") as f:
    CLIENT_SECRET = f.read().splitlines()[0]

SCOPE = "playlist-modify-public,playlist-modify-private,playlist-read-private,user-library-read,user-read-playback-position"

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id="91ed165161494fffae34d89d02619204",
                                               client_secret=CLIENT_SECRET,
                                               redirect_uri="http://localhost/callback",
                                               scope=SCOPE))

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

DailyDriveID = get_playlist('name', 'Daily Drive')

# Create playlist
if not get_playlist('name', 'Daily Listen'):
    sp.user_playlist_create(sp.me()['id'],'Daily Listen',public=False, description='Playlist for the day')


DailyListenID = get_playlist('name', 'Daily Listen')

DailyListen = sp.playlist_items(DailyListenID, fields='items(track(uri)),next')
while DailyListen:
    itemsDailyListen = [ trackDailyListen['track']['uri'] for trackDailyListen in DailyListen['items'] ]
    sp.playlist_remove_all_occurrences_of_items(DailyListenID, items=itemsDailyListen)
    if DailyListen['next']:
        DailyListen = sp.next(DailyListen)
    else:
        DailyListen = None

# Copy playlist contents to target
fields='items(track(uri)),next' # Next permits pagination
DailyDrive = sp.playlist_items(DailyDriveID, fields=fields)
while DailyDrive:
    itemsDailyDrive = [ trackDailyDrive['track']['uri'] for trackDailyDrive in DailyDrive['items'] ]
    sp.playlist_add_items(DailyListenID, items=itemsDailyDrive)
    if DailyDrive['next']:
        DailyDrive = sp.next(DailyDrive)
    else:
        DailyDrive = None

# Get URI list of shows being followed

allEpisodes = list()

savedShows = sp.current_user_saved_shows()
while savedShows:
    itemsSavedShows = [ showSavedShows['show']['uri'] for showSavedShows in savedShows['items'] ]

    for itemSavedShow in itemsSavedShows:
        episodes = [ episode for episode in sp.show_episodes(itemSavedShow)['items'] if not episode['resume_point']['fully_played']]
        allEpisodes.extend(episodes)

    if savedShows['next']:
        savedShows = sp.next(savedShows)
    else:
        savedShows = None

# sorted works on any iterable
# reverse for descending order of date.
allEpisodes = sorted(allEpisodes, key=lambda episode: episode['release_date'], reverse=True)

singleEpisodes = [ episode['uri'] for episode in allEpisodes[:99] ]
sp.playlist_add_items(DailyListenID, items=singleEpisodes)