# media-scripts

Some utilities for media/download server tasks

Requirements
- Python 3.8+
- Packages: `pip install requests rich`

Script Overview
- `test-trackers.py` — Tests bittorrent trackers from public tracker lists, measures latency, saves valid/fast trackers to `valid_trackers.txt`.
- `movie-folders.sh` — Moves video files into their own folders (Plex requirement) then cleans up small/empty folders.

Notes
- `test-trackers.py` edit configuration variables to your preference.
- `movie-folders.sh` will rm -rf for cleaned folders — use at own risk!
