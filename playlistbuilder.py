"""
Built spotify playlist and push it to the appropriate endpoint
"""

import os
import spotipy
from azure.identity import EnvironmentCredential
from azure.keyvault.secrets import SecretClient
from spotipy.oauth2 import SpotifyOAuth
from akv_cachehandler import AzureKeyVaultCacheHandler

# list of podcast shows to filter out
filter_show = ['spotify:show:6v1kAUP76SLtLI7ApsEgdH', 'spotify:show:0RrdRP2clWr5XCAYYA2j2A', \
        'spotify:show:0oYGnOWNIj93Q1CCfQ4Mj8', 'spotify:show:2GmNzw8t4uG70rn4XG9zcC', \
        'spotify:show:3yxUnWt3TJWXaKuRU2sLOg']

VAULT_URL = os.environ["VAULT_URL"]

credential = EnvironmentCredential()
client = SecretClient(vault_url=VAULT_URL, credential=credential)

SCOPE = "playlist-modify-public, playlist-modify-private, playlist-read-private, \
    user-library-read, user-read-playback-position, user-read-recently-played"

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id="91ed165161494fffae34d89d02619204", \
        client_secret=client.get_secret("SpotifyClientSecret").value, \
        redirect_uri="http://localhost/callback", \
        scope=SCOPE, \
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


def cull_shows(items, filterlist):
    '''
    Remove podcast shows we don't care for
    '''
    itemepisodes = [ show['uri'] for show in items if show['uri'].split(':')[1] == 'episode' ]
    episodelookup = list(sp.episodes(itemepisodes)['episodes'])

    result = list()
    for item in episodelookup:
        if item['show']['uri'] not in filterlist:
            result.append(item)

    return result


# Create playlist
def create_playlist(name, description=''):
    '''
    Create a playlist and return the playlistID.
    If the playlist already exists clean out the contents.
    '''
    playlistid = get_playlist('name', name)
    if not playlistid:
        sp.user_playlist_create(sp.me()['id'], name, public=False, description=description)

    return playlistid


def playlist_template(templatename):
    '''
    Use existing playlist as an initial seed for the new playlist
    '''
    templateplaylistid = get_playlist('name', templatename)

    fields='items(track),next' # Next permits pagination
    newplaylist = [ playlistitem['track'] for playlistitem in \
        sp.playlist_items(templateplaylistid, fields=fields)['items'] \
            if playlistitem['track'] is not None]
    tracks = list()
    episodes = list()
    for item in newplaylist:
        if item['uri'].split(':')[1] == 'track':
            tracks.append(item)
        else:
            episodes.append(item)


    return tracks, episodes


def podcast_episode_listing():
    '''
    Retrieve a few episodes from all of the shows the user follows.
    Return in descending order of release. (Newest first)
    '''
    allepisodes = list()

    savedshows = sp.current_user_saved_shows()
    while savedshows:
        itemssavedshows = [ showsavedshows['show']['uri'] for \
            showsavedshows in savedshows['items'] ]

        for itemsavedshow in itemssavedshows:

            showepisodes = sp.show_episodes(itemsavedshow)
            episodelisting = list()
            while showepisodes:

                # Use pagination to grab batches of 50 and dump the episodes we've heard before.
                # Don't move on until we have 50 from each show.
                tempepisodes = [ episode for episode in \
                    showepisodes['items'] if not episode['resume_point']['fully_played'] and \
                    (episode['duration_ms'] - episode['resume_point']['resume_position_ms']) >= 120000 ] # pylint: disable=line-too-long

                if len(tempepisodes) < 50:
                    episodelisting.extend(tempepisodes)
                    tempepisodes = None
                else:
                    break

                if showepisodes['next']:
                    showepisodes = sp.next(showepisodes)
                else:
                    showepisodes = None
            allepisodes.extend(episodelisting)

        if savedshows['next']:
            savedshows = sp.next(savedshows)
        else:
            savedshows = None

    # sorted works on any iterable
    # reverse for descending order of date.
    allepisodes = sorted(allepisodes, key=lambda episode: episode['release_date'], reverse=True)
    return allepisodes


def remove_tracks(tracks, exclude=None):
    '''
    Remove duplicates and recently played
    Optionally provide a playlist to remove the contents of
    Explicity remove Spotify as an artist.
    '''

    # Get recently played
    # it would be nice to have 100 but it looks like the endpoint only supports 50
    recentplayed = sp.current_user_recently_played()
    recentplayeduri = list()
    while recentplayed:
        recentplayeduri.extend([recent['track']['uri'] for recent in recentplayed['items']])
        if len(recentplayeduri) < 50 and recentplayed['next']:
            recentplayed = sp.next(recentplayed)
        else:
            recentplayed = None

    if exclude is not None:
        excludelist = exclude['items']
        for recent in excludelist:
            if recent['track'] is None:
                continue
            if recent['track']['uri'].split(':')[1] == 'track':
                recentplayeduri.append(recent['track']['uri'])

    nodupes = dict()
    for track in tracks:
        if track['uri'] not in recentplayeduri and track['artists'][0]['uri'] != \
            'spotify:artist:5UUG83KSlqPhrBssrducWV':
            nodupes[track['uri']] = track

    newtracks = list(nodupes.values())
    trackrecommendcount = len(tracks) - len(newtracks)
    if trackrecommendcount:
        recommendations = sp.recommendations(\
            seed_tracks=[track['id'] for track in tracks[:5]], limit=(trackrecommendcount))
        newtracks.extend(recommendations['tracks'])
    return newtracks

def main_build(plname, pldescription=''):
    '''
    Entrypoint to actually build and push the playlist
    '''
    dailylistenid = create_playlist(name=plname, description=pldescription)
    tracks, episodes = playlist_template(templatename='Daily Drive')
    tracks = remove_tracks(tracks, exclude=sp.playlist_items(dailylistenid))
    # Cull out blacklisted shows
    episodes = cull_shows(episodes, filter_show)
    allepisodes = podcast_episode_listing()

    allepisodesdict = dict()

    for entry in allepisodes:
        allepisodesdict[entry['uri']] = entry
    
    for entry in episodes.copy():
        if entry['uri'] in allepisodesdict.keys():
            episodes.remove(entry)
        allepisodesdict[entry['uri']] = entry
    
    for episode in episodes:
        allepisodes.insert(0, episode)

    sortedplaylist = list()

    while len(tracks) > 0:
        sortedplaylist.append(allepisodes.pop(0)['uri'])
        sortedplaylist.append(tracks.pop(0)['uri'])
        try:
            sortedplaylist.append(tracks.pop(0)['uri'])
        except IndexError:
            pass

    sp.user_playlist_replace_tracks(sp.me()['id'], dailylistenid, tracks=sortedplaylist)


if __name__ == "__main__":
    main_build(plname="Daily Listen - Staging")
