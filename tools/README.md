# Tools

Utility scripts for file management and testing. Most should be run manually as needed.

See [main README](../README.md) for repo setup and configuration, and dependency installation.

## `prune-small-dirs.py`

Interactively deletes small subfolders from the media library — leftover/failed folders well
under the size of real media. Detection is **size only**: for each folder in `SCAN_FOLDERS` it
lists the immediate subfolders under a size threshold as `Category > Title`, shows each one's
size, and deletes **nothing** until you confirm.

There are **no command-line arguments** — edit the constants at the top and run it. Built to be
paranoid, after an earlier attempt at this wiped the whole library:

- **Confirm first.** You see the exact list (size + `Category > Title`) and choose `[a]ll`,
  `[s]tep through each`, or `[q]uit`. Piped/non-interactive input deletes nothing.
- **Only the listed folders.** The only things ever deleted are the **immediate** subfolders of
  a `SCAN_FOLDERS` path — one level down, never deeper. The scan folders themselves, and anything
  outside them, are never touched; symlinks are skipped.
- **Video folders only.** `SCAN_FOLDERS` lists the video categories, where a small folder really
  means junk (a real film/episode is gigabytes). Books/music are left out, since small folders
  there are normal.
- **Size only, no magic.** If a listed folder's size looks surprising, inspect it by hand before
  confirming. Each folder's size is re-checked immediately before removal.

**Configuration** (top of `prune-small-dirs.py`):
- `SCAN_FOLDERS` — full paths of the folders to scan (their subfolders are the candidates)
- `MAX_SIZE_BYTES` — folders smaller than this are offered for deletion (default 100 MB)
- `IGNORE` — subfolder names skipped even when small (`@eaDir`, `#recycle`, `.Trash-1000`)

**Usage:**
```bash
python3 prune-small-dirs.py
```

Over-size folders are abandoned early during the scan, so a sweep stays quick.

## `media-extensions.py`

Restores file extensions for photos and videos by analyzing magic bytes.

**Features:**
- Detects file types from binary headers/magic bytes
- Supports images: JPEG, PNG, GIF, BMP, TIFF, HEIC, HEIF, AVIF, WebP
- Supports videos: MP4, M4V, MOV, 3GP, MKV, FLV, MPEG, OGG, AVI, WebM
- Handles equivalent extensions (.jpg/.jpeg, .tiff/.tif, etc.)
- Skips system files (.DS_Store, Thumbs.db, etc.)
- Dry-run mode available for preview

**Usage:**
```bash
# Preview changes without modifying files
python3 media-extensions.py /path/to/files --dry-run

# Execute and rename files (default mode)
python3 media-extensions.py /path/to/files

# Move files with no recognized type to a separate folder
python3 media-extensions.py /path/to/files --move-unknown /path/to/unknown

# Also clean problematic characters from filenames
python3 media-extensions.py /path/to/files --sanitize-names
```

## `strip-subtitles.py`

Removes unwanted subtitle tracks from video files, keeping the languages you choose.
Originally written to drop every subtitle track, which helped with 4K playback issues on
Plex client apps; it now keeps a language list instead.

**Features:**
- Keeps **every** track of a wanted language, forced and SDH variants included
- MKV goes through `mkvmerge`, which preserves chapters, attachments, tags and track
  metadata; other containers fall back to `ffmpeg`
- Matches on the container's own language tags, so ISO 639-2/B spellings work -
  `en`/`eng`, `fr`/`fra`/`fre`, `de`/`ger`/`deu`, `pt-BR` all resolve correctly
- Skips a file that already holds only wanted tracks, so a re-run costs nothing
- Rebuilds beside the original and swaps it in only after verifying the result
- Refuses to start unless there is free space for the rebuilt copy

**Requires:** `mkvmerge` (mkvtoolnix), `ffmpeg`, `ffprobe`, tqdm.

**Configuration:**

All constants are at the top of `strip-subtitles.py`:
- `KEEP_LANGUAGES` - languages to keep, any spelling; an empty tuple removes all subtitles
- `KEEP_UNTAGGED` - also keep tracks carrying no language tag
- `FILENAME_FILTER` - only touch filenames containing this; `""` processes everything
- `DRY_RUN` - print what would change without rewriting anything
- `FREE_SPACE_MARGIN_BYTES` - headroom demanded beyond the size of the file itself

**Usage:**
```bash
python3 strip-subtitles.py /path/to/media
```

Removing tracks means rewriting the whole container - roughly the file's size read *and*
written per file, so budget hours for a season of 4K episodes. Run `DRY_RUN` first.

Matching is on the track's **language tag**, never its content or the file's audio language.
Two ways that bites: a track carrying no tag (or `und`) is dropped unless `KEEP_UNTAGGED = True`,
and a mistagged track is judged on its tag rather than what it actually contains - so a release
that ships its only English subtitles untagged loses them. `DRY_RUN` lists exactly what each file
would keep and drop; use it before a batch.

Order matters: run `extract-pgs-subtitles.py` **before** stripping if you want SRTs, since
deleting the PGS tracks destroys the only source those subtitles can be generated from.

## `find-domain.py`

Not really related to media server but fun and may be useful.

Finds available domains where the prefix + TLD suffix forms an English word (e.g. `mu.ch`, `bea.ch`, `rea.ch`).

**Features:**
- Checks availability via WHOIS with DNS SOA as fallback for unsupported TLDs
- Supports multiple TLD suffixes in one run
- Caches registered domains to skip on reruns (cache expires after 14 days)
- Verbose mode (`-v`) to show all checks, not just available domains
- Integration tests across 20 popular TLDs (`-t`)
- Concurrent checks with a progress bar

> **Note:** Results may not be 100% accurate. WHOIS responses vary by registrar and TLD — some return ambiguous data for unregistered domains, causing the DNS fallback to be used instead. DNS SOA checks can produce false positives if nameservers are unreachable or during propagation delays after registration. Always verify through a registrar before attempting to register.

**Usage:**
```bash
# Single TLD
python3 find-domain.py net 10

# Multiple TLDs, max word length 12
python3 find-domain.py 'com,net,io' 12

# Verbose (show all checks, not just available)
python3 find-domain.py ch 8 -v

# Run integration tests against known domains across 20 popular TLDs
python3 find-domain.py -t
```

Arguments:
- `suffixes` — TLD or comma-separated list of TLDs (without leading dot)
- `max_length` — maximum total word length to consider

## `test-trackers.py`

Filters public lists of BitTorrent trackers for validity and performance.

Suggest running from your actual environment/country as results may vary. Australian users can try the `valid_trackers.txt` as is.

**Features:**
- Fetches tracker lists from multiple public sources
- Tests UDP and HTTP trackers concurrently
- Measures tracker response latency
- Filters out dead/slow trackers
- Saves valid trackers to `valid_trackers.txt`
- Progress bar and logging to `response_log.txt`

**Configuration:**

Optionally configure in `test-trackers.py`:
- `TRACKER_LISTS` - Source URLs to pull potential trackers from
- `OUTPUT_FILE` - Output file for valid trackers
- `LOG_FILE` - Log file for test results

**Usage:**
```bash
python3 test-trackers.py
```

Output files:
- `valid_trackers.txt` - List of working trackers
- `response_log.txt` - Detailed test results

## `extract-pgs-subtitles.py`

OCRs the English PGS (bitmap) subtitles baked into video files and writes plain `.srt` sidecars,
so subtitle font and size become customisable in the player.

**Features:**
- Walks a library recursively; detects the container with `ffprobe`, not the file extension
- Chooses between multiple English tracks **by content**: it extracts every candidate in a
  single pass over the file and keeps whichever decodes to the most subtitles
- Decodes the PGS bitstream directly (palette, run-length images, display-set timing)
- Timing is copied verbatim from the PGS timestamps, so it stays as in-sync as the source
- Deletes an episode's old `.srt` immediately before regenerating that one episode, so an
  interrupted run leaves at most one episode without subtitles
- `START_AT` names the episode to do **first**; `WRAP_AROUND` then comes back for the ones
  before it, so a run started mid-series still covers everything

**Requires:** `ffmpeg`, `ffprobe`, `tesseract-ocr` + `tesseract-ocr-eng`, Pillow, numpy.

For better accuracy than the packaged model, fetch the `tessdata_best` English data:

```bash
mkdir -p ~/.local/share/tessdata && curl -L -o ~/.local/share/tessdata/eng.traineddata \
  https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/main/eng.traineddata
```

**Configuration:**

All constants are at the top of `extract-pgs-subtitles.py`:
- `ROOT_DIR` - library to walk (a path argument overrides it)
- `START_AT` - episode to process first, e.g. `"S02E08"`; `None` starts at the beginning
- `WRAP_AROUND` - after the end, come back for the episodes before `START_AT`
- `OUTPUT_SUFFIX` - `.en.srt` writes `Episode.en.srt`. Keep the language code: Plex reads a
  bare `Episode.srt` as unknown-language and will not auto-select it
- `DELETE_EXISTING_SRT` - delete an episode's `.srt` just before regenerating it, and only
  once an English PGS track is confirmed present to replace it with
- `DRY_RUN` - print every action without touching the filesystem
- `MAX_OCR_WORKERS` / `TESSERACT_OMP_THREADS` - parallelism; leave OMP at 1, since
  letting each tesseract go multithreaded measured ~46x slower on a 4-core box

**Usage:**
```bash
python3 extract-pgs-subtitles.py "/mnt/media/tv/Some Show"
```

Extracting a subtitle track means reading the whole container, so expect several minutes
per episode on large files. Run it against one show first and check the result.

Plex will not show new sidecars until the library is rescanned - the files appearing on disk
is not enough on its own.

**Why track choice is decided by content, not by the track flags.** A disc often carries two
English subtitle tracks: the full one, and a forced one holding only the foreign-language
dialogue. On Blu-ray rips the *forced* track is frequently the one marked `default`, because a
player is meant to show it during English audio - and neither track need carry the `forced`
flag or a title saying so. Preferring `default` therefore picks the near-empty track, and the
failure is silent: you get a valid-looking `.srt` with ~20 subtitles instead of ~800. Counting
decoded subtitles is the only reliable discriminator, which is why all candidates are pulled in
one pass and compared. If an episode's `.srt` looks suspiciously short, that is the thing to
check first.

**OCR is not perfect and is not auto-corrected.** Only one substitution ships - a pipe character
back to a capital `I`, verified against the source bitmap - because a pipe never legitimately
appears in dialogue. Genuinely ambiguous confusions (`l` vs `I`, `rn` vs `m`) are deliberately
left alone: guessing at them corrupts more text than it repairs. Add your own pairs to
`OCR_REPLACEMENTS` only where the mapping is unambiguous.

## `claude_ping.sh`

A heartbeat that keeps the Claude Code subscription session warm by sending one cheap prompt on a
schedule. Unlike the other scripts here, this one is **cron-driven**, not run by hand.

**How it works:**
- Runs `claude -p "Hi"` headless on the cheapest model (`claude-haiku-4-5-...`) so it barely touches
  the 5-hour quota, with stdin from `/dev/null` so the CLI doesn't hang waiting for input.
- Exports a common `PATH` so cron's minimal environment can find the `claude` binary.
- Logs to `~/claude_cron.log`, capped at the last 100 lines (atomic temp + rename).

**Cron (3× per day):**
```
0 7 * * * /home/simon/scripts/tools/claude_ping.sh
1 12 * * * /home/simon/scripts/tools/claude_ping.sh
2 17 * * * /home/simon/scripts/tools/claude_ping.sh
```

## `claude-tmux-watchdog.sh`

Keeps a single interactive Claude Code session alive in a detached `tmux` session so this machine can
be driven from the Claude iPhone / web app via [Remote Control](https://code.claude.com/docs/en/remote-control).
Also **cron-driven**.

**How it works:**
- If the `tmux` session named `claude` isn't running, it starts `claude --remote-control Beelink` with
  working directory `~/homelab`. Claude is the pane's own process (via `exec`), so the tmux session ends
  when Claude exits and the next run restarts it.
- `claude-tmux-watchdog.sh --restart` **recycles** the session (kill + recreate). A daily cron runs
  this because `tmux has-session` only tells you the process is alive — not that Remote Control still
  works. An interactive RC session does **not** reliably reconnect after a network drop: it can sit
  alive at a prompt with every connection gone, unreachable from the app, which the 15-min check can't
  detect. The daily recycle clears that and also picks up the `claude` binary auto-update (the
  long-lived process otherwise keeps running a stale version).
- `flock` stops two cron ticks from racing. The `tmux` launch closes the lock fd (`9>&-`) so the
  detached tmux server doesn't inherit it and hold the lock for the life of the session — otherwise
  every later run, including `--restart`, would find the lock held and do nothing.
- It exports `PATH` for cron and errors clearly if `claude` or `tmux` is missing.
- Attach locally with `tmux attach -t claude`; find it in the app's **Code** tab as **Beelink**.

**Requirements:** a claude.ai Pro/Max subscription and Remote Control enabled
(`remoteControlAtStartup: true` in `~/.claude/settings.json`).

**Cron — 15-min recreate-if-dead + daily recycle:**
```
*/15 * * * * /home/simon/scripts/tools/claude-tmux-watchdog.sh >> /home/simon/scripts/tools/claude-tmux-watchdog.log 2>&1
0 4 * * *    /home/simon/scripts/tools/claude-tmux-watchdog.sh --restart >> /home/simon/scripts/tools/claude-tmux-watchdog.log 2>&1
```

## What's missing? 

Made it this far? Submit an idea to the [Github issues page](https://github.com/swxxii/media-scripts/issues).
