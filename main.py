import spotipy
from spotipy.oauth2 import SpotifyOAuth

# list of podcast shows to filter out
filter_show = ['spotify:show:6v1kAUP76SLtLI7ApsEgdH', 'spotify:show:0RrdRP2clWr5XCAYYA2j2A', 'spotify:show:0oYGnOWNIj93Q1CCfQ4Mj8?', 'spotify:show:2GmNzw8t4uG70rn4XG9zcC']

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


def cullBlacklist(items, filterList):
    itemEpisodes = [ show for show in items if show.split(':')[1] == 'episode' ]
    episodeLookup = [ [episode['show']['uri'], episode['uri']] for episode in sp.episodes(itemEpisodes)['episodes'] ]
    
    for x in episodeLookup:
        if x[0] in filterList:
            items.remove(x[1])
    return items


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


DailyDriveID = get_playlist('name', 'Daily Drive')

fields='items(track(uri)),next' # Next permits pagination
newPlaylist = [ playlistItem['track']['uri'] for playlistItem in sp.playlist_items(DailyDriveID, fields=fields)['items'] ]

# Cull out blacklisted shows
newPlaylist = cullBlacklist(newPlaylist, filter_show)

# Get URI list of shows being followed

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

# Get count of songs, we want half of that for podcasts
songCount = 0
for x in newPlaylist:
    if x.split(':')[1] == "track":
        songCount = songCount + 1

singleEpisodes = [ episode['uri'] for episode in allEpisodes[:round(songCount/2)] ]
newPlaylist.extend(singleEpisodes)

# sampleData = ['spotify:track:3DKmwMaqRTOW5Ba5dHijgX', 'spotify:episode:19dyBsqL2gX74pFXK4RSNb', 'spotify:track:4yVJTuaJ4NlCaCUYe9ElIz', 'spotify:track:71hhuJLNpxBQLSbbQ6ZWr4', 'spotify:track:7j31rVgGX9Q2blT92VBEA0', 'spotify:track:7uSsHbBFFAnkRQR1rDwP3L', 'spotify:episode:1wF3w9zP9jlY1sdPbu2ala', 'spotify:track:1N3bdxmsu3wimLy3E4d4cf', 'spotify:track:707mVFEVPIpTWaejXjI7TY', 'spotify:track:5qNEPKqPOECw50RpOGT9ne', 'spotify:track:4DijrJqz7WYjnjHmvdlAyB', 'spotify:track:50jXnyrzW4mcBBqFTMEoAC', 'spotify:track:4wD6EgZCok8Qb5Fs8jszYc', 'spotify:track:6qZjm61s6u8Ead9sWxCDro', 'spotify:track:6QEvc1Xriqvn70EG2VrDy3', 'spotify:track:3SUNHWszXHmCx0J668tqq1', 'spotify:track:11cjKlgVaUvbBjEAAGv9MZ', 'spotify:track:0d28khcov6AiegSCpG5TuT', 'spotify:track:2zzLRQ78kKfPTx8FJQCdC2', 'spotify:track:4WQs5UIokNcsxWumMEfDt3', 'spotify:track:3p0rvHL2zfHAlXAgnHC4GI', 'spotify:track:72hSmnleYTiiOo23q8ZJIS', 'spotify:track:5AKYyNPYhumqKeOMhdEgQO', 'spotify:track:5ylAFXgB62LXZBxUy6cmYg', 'spotify:track:7vA9zWg6fmjLZn105Uj4TE', 'spotify:track:4jFLw7QqWlv3lZr980HyYW', 'spotify:track:03wKMRNYVvw6s9nm4I4jUS', 'spotify:track:7tCHpjktA50ihtkLz6bAnn', 'spotify:track:20I8RduZC2PWMWTDCZuuAN', 'spotify:track:1MzAV3ZqGVU2cmmwmJwymM', 'spotify:track:6E69aBnq0hr6cTGBo39cWD', 'spotify:episode:4Hkx7uiqlmrR4oPzpp2rsk', 'spotify:episode:5oxZSKaJjyjgo10bj7M8Xk', 'spotify:episode:6xYAXwz6oDPE6ApMt1HzV5', 'spotify:episode:5OO67nxhbmCS08l9IDt3It', 'spotify:episode:2yRvXnC1JQzGTmq9kqpCnH', 'spotify:episode:2om6UMZbU7PjLCUFQljNv6', 'spotify:episode:0WlyKekrux44Lxj1Mq2m9u', 'spotify:episode:0txUTbvgXbC57WpgzDXr0z', 'spotify:episode:6rqWdosPJz53cQRzeQ9nfF', 'spotify:episode:4HBdWIIQtrAz10G20esHaY', 'spotify:episode:783lK8XOohpbxoAIpOJyhk', 'spotify:episode:3NdbtyXttT6yJrvsFNIbG0', 'spotify:episode:6oEqn3yJ4I1VNssUGlbWgW', 'spotify:episode:1rPkyn605umnRfJMEbHhsd']

tracks = [ track for track in newPlaylist if track.split(':')[1] == 'track']
episodes = [episode for episode in newPlaylist if episode.split(':')[1] == 'episode']

sortedPlaylist = list()

while len(tracks) > 0:
    sortedPlaylist.append(episodes.pop(0))
    sortedPlaylist.append(tracks.pop(0))
    try:
        sortedPlaylist.append(tracks.pop(0))
    except:
        pass

sp.playlist_add_items(DailyListenID, items=sortedPlaylist)