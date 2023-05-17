"""
Built spotify playlist and push it to the appropriate endpoint
"""

import json
import logging
import os
import random
import requests
import spotipy
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from spotipy.oauth2 import SpotifyOAuth
from akv_cachehandler import AzureKeyVaultCacheHandler


def _is_played(episode, timevar=120000):
    """
    Check if an episode is marked as played or
    if playtime remaining is less than designated minutes.
    """
    if episode["duration_ms"] < timevar:
        return episode["resume_point"]["fully_played"]
    elif (
        not episode["resume_point"]["fully_played"]
        and (episode["duration_ms"] - episode["resume_point"]["resume_position_ms"])
        <= timevar
    ):
        return True
    return episode["resume_point"]["fully_played"]


def _is_playable(track):
    """
    Check if track is currently in a state that can be played if selected.
    """
    if "US" in track["available_markets"]:
        return True


class PlaylistGenerator:
    """
    Create spotipy object and manage all the work needing to be done
    """

    def __init__(self, plname=None):
        if plname is None:
            raise AttributeError("A playlist name must be given via plname on init")
        self.plname = plname

        vault_url = os.environ["VAULT_URL"]

        credential = DefaultAzureCredential()
        client = SecretClient(vault_url=vault_url, credential=credential)

        scope = "playlist-modify-public, playlist-modify-private, playlist-read-private, \
            user-library-read, user-read-playback-position, user-read-recently-played"

        # Occasionally times out during function, quick search lead to a stackoverflow post
        # suggesting to increase the timeout and retry count.
        # ref: https://stackoverflow.com/questions/64815194/spotify-python-api-call-timeout-issues/66770782#66770782
        self.spotipy = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id="91ed165161494fffae34d89d02619204",
                client_secret=client.get_secret("SpotifyClientSecret").value,
                redirect_uri="http://localhost/callback",
                scope=scope,
                cache_handler=AzureKeyVaultCacheHandler(),
            ),
            requests_timeout=10,
            retries=10,
        )

        # Check for an environmental variable that will be defined on Production
        try:
            if "FUNCTIONS_WORKER_RUNTIME" not in os.environ:
                self.local_config = True
        except KeyError:
            pass
        self.config = None

    def load_config(self, local: bool = False) -> None:
        """
        Check if this is running in the cloud, if not try to load a config file locally.
        """
        if local:
            try:
                with open("config.staging.json", "r") as f:
                    self.config = json.load(f)
            except FileNotFoundError:
                self.config = {}
            return
        playlist = self.spotipy.playlist(self.get_playlist("name", self.plname))
        # Spotify escapes slashes, so we need to fix that
        config = str(playlist["description"]).replace("REMOTE_CONFIG=", "")
        config = config.replace("&#x2F;", "/")
        logging.info(config)
        req = requests.get(config)
        self.config = json.loads(req.content)

    def get_playlist(self, field, search):
        """
        Search through all of the playlists, and return the first uri that matches by field
        """
        playlists = self.spotipy.current_user_playlists()
        while playlists:
            for playlist in playlists["items"]:
                if playlist[field] == search:
                    return playlist["uri"]
            if playlists["next"]:
                playlists = self.spotipy.next(playlists)
            else:
                playlists = None
        return None

    def cull_shows(self, items, filterlist):
        """
        Remove podcast shows we don't care for
        """
        itemepisodes = [
            show["uri"] for show in items if show["uri"].split(":")[1] == "episode"
        ]
        episodelookup = list(self.spotipy.episodes(itemepisodes)["episodes"])

        result = []
        for item in episodelookup:
            if item["show"]["uri"] not in filterlist:
                result.append(item)

        return result

    def create_playlist(self, name, description=""):
        """
        Create a playlist and return the playlistID.
        If the playlist already exists return the ID.
        """
        playlistid = self.get_playlist("name", name)
        if not playlistid:
            self.spotipy.user_playlist_create(
                self.spotipy.me()["id"], name, public=False, description=description
            )

        return playlistid

    def playlist_template(self, templatename):
        """
        Use existing playlist as an initial seed for the new playlist
        """
        templateplaylistid = self.get_playlist("name", templatename)

        fields = "items(track),next"  # Next permits pagination
        newplaylist = [
            playlistitem["track"]
            for playlistitem in self.spotipy.playlist_items(
                templateplaylistid, fields=fields
            )["items"]
            if playlistitem["track"] is not None
        ]
        tracks = []
        episodes = []
        for item in newplaylist:
            if item["episode"]:
                if not _is_played(item):
                    episodes.append(item)
            else:
                tracks.append(item)

        return tracks, episodes

    def podcast_episode_listing(self, epcount=10):
        """
        Retrieve a few episodes from all of the shows the user follows.
        Return in descending order of release. (Newest first)
        keyword arguments:
        epcount -- the number of unplayed episodes to retrieve from each show
        """
        allepisodes = []

        saved_show_listing = []
        savedshows = self.spotipy.current_user_saved_shows()
        # we need to paginate this to make sure all saved shows are grabbed
        while savedshows:
            saved_show_listing.extend(savedshows["items"])
            if savedshows["next"]:
                savedshows = self.spotipy.next(savedshows)
            else:
                savedshows = None

        for show in saved_show_listing:
            showepisodes = self.spotipy.show_episodes(show["show"]["uri"])
            episodelisting = []
            while showepisodes:
                # Use pagination to grab batches and drop the episodes we've heard before.
                # Don't move on until we have at least epcount from each show.
                tempepisodes = [
                    episode
                    for episode in showepisodes["items"]
                    if not _is_played(episode)
                ]

                episodelisting.extend(tempepisodes)

                if len(episodelisting) > epcount:
                    break

                if showepisodes["next"]:
                    showepisodes = self.spotipy.next(showepisodes)
                else:
                    break
            allepisodes.extend(episodelisting)

        # sorted works on any iterable
        # reverse for descending order of date.
        allepisodes = sorted(
            allepisodes, key=lambda episode: episode["release_date"], reverse=True
        )
        return allepisodes

    def remove_tracks(self, tracks, exclude=None):
        """
        Remove duplicates and recently played
        Optionally provide a playlist to remove the contents of
        Explicity remove Spotify as an artist.
        """

        # Get recently played
        # it would be nice to have 100 but it looks like the endpoint only supports 50
        recentplayed = self.spotipy.current_user_recently_played()
        recentplayeduri = []
        while recentplayed:
            recentplayeduri.extend(
                [recent["track"]["uri"] for recent in recentplayed["items"]]
            )
            if len(recentplayeduri) < 50 and recentplayed["next"]:
                recentplayed = self.spotipy.next(recentplayed)
            else:
                recentplayed = None

        if exclude is not None:
            excludelist = exclude["items"]
            for recent in excludelist:
                if recent["track"] is None:
                    continue
                if recent["track"]["uri"].split(":")[1] == "track":
                    recentplayeduri.append(recent["track"]["uri"])

        tracks = list(filter(_is_playable, tracks))
        nodupes = {}
        for track in tracks:
            if (
                track["uri"] not in recentplayeduri
                and track["artists"][0]["uri"]
                != "spotify:artist:5UUG83KSlqPhrBssrducWV"
            ):
                nodupes[track["uri"]] = track

        newtracks = list(nodupes.values())
        trackrecommendcount = len(tracks) - len(newtracks)
        if trackrecommendcount:
            recommendations = self.spotipy.recommendations(
                seed_tracks=[track["id"] for track in tracks[:5]],
                limit=(trackrecommendcount),
            )
            newtracks.extend(recommendations["tracks"])
        return newtracks

    def get_tracks(self, origins: list = None, shuffle: bool = True) -> list:
        """
        Iterate through the origins list and grab all of the tracks found inside.
        origins should be a list of playlist names with songs that should be used.
        defaults to using 50 of the user's liked songs.
        returns a list of track items
        """
        tracks = []
        for origin in origins:
            if "" == origin:  # default case
                total_tracks = self.spotipy.current_user_saved_tracks(limit=50)["total"]
                random_offset = random.randint(0, total_tracks - 50)
                for item in self.spotipy.current_user_saved_tracks(
                    limit=50, offset=random_offset
                )["items"]:
                    tracks.append(item["track"])
                continue

            playlist_id = self.get_playlist("name", origin)
            for item in self.spotipy.playlist_tracks(playlist_id, fields="items")[
                "items"
            ]:
                if "track" in item["track"]["uri"]:
                    tracks.append(item["track"])
        if shuffle:
            random.shuffle(tracks)
        return tracks

    def main_build(self):
        """
        Entrypoint to actually build and push the playlist
        """
        dailylistenid = self.create_playlist(name=self.plname)

        if "playlist_template" in self.config:
            _, episodes = self.playlist_template(
                templatename=self.config["playlist_template"]
            )
        else:
            episodes = []

        if "song_origin" not in self.config:
            self.config["song_origin"] = [""]
        tracks = self.get_tracks(origins=self.config["song_origin"])
        tracks = self.remove_tracks(
            tracks, exclude=self.spotipy.playlist_items(dailylistenid)
        )
        # Cull out blacklisted shows
        if len(episodes) > 0:
            episodes = self.cull_shows(episodes, self.config["filter_show"])
        allepisodes = self.podcast_episode_listing()

        allepisodesdict = {}

        for entry in allepisodes:
            allepisodesdict[entry["uri"]] = entry

        for entry in episodes.copy():
            if entry["uri"] in allepisodesdict:
                episodes.remove(entry)
            allepisodesdict[entry["uri"]] = entry

        for episode in episodes:
            allepisodes.insert(0, episode)

        sortedplaylist = []

        while len(tracks) > 0:
            sortedplaylist.append(allepisodes.pop(0)["uri"])
            sortedplaylist.append(tracks.pop(0)["uri"])
            try:
                sortedplaylist.append(tracks.pop(0)["uri"])
            except IndexError:
                pass

        try:
            # spotify API says you can add a maximum of 100 tracks per request
            # limit to 99 as we're not sure wether it's inclusive or not
            self.spotipy.user_playlist_replace_tracks(
                self.spotipy.me()["id"], dailylistenid, tracks=sortedplaylist[:99]
            )

        except spotipy.exceptions.SpotifyException as err:
            str_err = str(err)
            if "429" in str_err and "500" in str_err:
                # Handle when the replace endpoint is broken
                print("429 error actually a 500 error")
                # Clear target playlist
                DailyListen = self.spotipy.playlist_items(
                    dailylistenid, fields="items(track(uri)),next"
                )
                while DailyListen:
                    itemsDailyListen = [
                        trackDailyListen["track"]["uri"]
                        for trackDailyListen in DailyListen["items"]
                        if trackDailyListen["track"] is not None
                    ]
                    self.spotipy.playlist_remove_all_occurrences_of_items(
                        dailylistenid, items=itemsDailyListen
                    )
                    if DailyListen["next"]:
                        DailyListen = self.spotipy.next(DailyListen)
                    else:
                        DailyListen = None
                # Write to target playlist
                self.spotipy.playlist_add_items(dailylistenid, items=sortedplaylist)


if __name__ == "__main__":
    import sys

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)

    build = PlaylistGenerator(plname="Daily Listen - Staging")
    build.load_config(local=build.local_config)
    build.main_build()
