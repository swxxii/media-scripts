# Tools

Utility scripts for file management and testing.

## Scripts

### `media-extensions.py`

Restores file extensions for photos and videos by analyzing magic bytes.

**Dependencies:** None (uses standard library)

**Features:**
- Detects file types from binary headers/magic bytes
- Supports images: JPEG, PNG, GIF, BMP, TIFF, HEIC, HEIF, AVIF
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
```

---

### `strip-subtitles.py`

Strips embedded subtitle tracks from video files with `[4K]` in their filename using ffmpeg.

**Dependencies:** `pip install tqdm` and `sudo apt install ffmpeg`

Useful for removing unwanted forced subtitle tracks from 4K remuxes.

**Features:**
- Scans a directory recursively or processes a single file
- Only processes files containing `[4K]` in the filename
- Copies video and audio streams unchanged (no re-encode)
- Progress bar per file
- Verifies subtitle removal after processing
- Logs to `strip-subtitles.log`

**Usage:**
```bash
# Scan a directory
python3 strip-subtitles.py /path/to/media

# Process a single file
python3 strip-subtitles.py /path/to/file.mkv
```

---

### `test-trackers.py`

Tests BitTorrent tracker URLs for validity and performance.

**Dependencies:** `pip install requests rich`

**Features:**
- Fetches tracker lists from multiple public sources
- Tests UDP and HTTP trackers concurrently
- Measures tracker response latency
- Filters out dead/slow trackers
- Saves valid trackers to `valid_trackers.txt`
- Progress bar and logging to `response_log.txt`

**Setup:**

Install dependencies:
```bash
pip install requests rich
```

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
