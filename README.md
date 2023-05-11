### Config file
When creating your initial playlist that's going to be adjusted set the description to a URL that points to a world readable config file. An example config is below.

```json
{
	"playlist_template": "Daily Drive"
	,"filter_show": [
		"spotify:show:6v1kAUP76SLtLI7ApsEgdH",
		"spotify:show:0RrdRP2clWr5XCAYYA2j2A"
	]
	,"song_origin": [
		"Goblincore Mix",
        "Koto Strawhatz : Oriental Trap Hip Hop"
	]
	
}
```

`playlist_template`: (optional) This is a playlist that will be used as a template before adding all user content. "Daily Drive" is a good example, bringing in both podcasts and music.

`filter_show`: (optional) Shows we don't want on end playlist. This makes the most sense when used with the `playlist_template` key as it will primarily impact shows that are not subscribed. But it can also be with podcasts you follow but don't want automatically added.

`song_origin`: (optional If `playlist_template` is used) playlists that songs should be pulled from. If you want to pull songs from the users library (likes) specify an entry of `""`.