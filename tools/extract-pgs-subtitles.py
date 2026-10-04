#!/usr/bin/env python3
"""OCR the English PGS (bitmap) subtitles of a TV library into .srt sidecars.

Walks ROOT_DIR recursively, probes every video with ffprobe (container-agnostic),
extracts the English HDMV PGS track with ffmpeg, decodes the PGS bitstream in
process, OCRs each subtitle image with tesseract and writes an .srt next to the
video.

Requires: ffmpeg, ffprobe, tesseract (+ the eng language data), Pillow, numpy.
Usage:    ./extract-pgs-subtitles.py [ROOT_DIR]      (argv overrides the ROOT_DIR constant)
"""

from __future__ import annotations

import io
import os
import re
import struct
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

# ===========================================================================
# Configuration
# ===========================================================================

# --- What to process -------------------------------------------------------

ROOT_DIR = Path("/mnt/media/tv/Game of Thrones")

# Files considered for probing. Anything not in this list is ignored outright.
# The container is still detected by ffprobe, not by the extension.
VIDEO_EXTENSIONS = (
    ".mkv", ".mp4", ".m4v", ".ts", ".m2ts", ".mts",
    ".avi", ".mov", ".webm", ".wmv", ".mpg", ".mpeg", ".vob",
)

# Probe every file regardless of extension. Slower, catches oddly-named files.
PROBE_ALL_FILES = False

# Directories skipped entirely (matched on the directory name, case-insensitive).
SKIP_DIR_NAMES = ("extras", "featurettes", "behind the scenes", "#recycle", "@eaDir")

# Which episode to do first. The first video whose path contains this string
# (case-insensitive) is processed first, e.g. "S02E08" or "Season 2/Show - S02E08".
# None starts at the beginning.
START_AT = "S03E01"

# After reaching the end, come back round and process the episodes that came
# before START_AT, so a run started mid-series still covers the whole tree.
# False stops at the end instead, leaving earlier episodes untouched.
WRAP_AROUND = True

# --- Subtitle track selection ---------------------------------------------

# ISO language tags accepted from the stream's `language` tag.
SUBTITLE_LANGUAGES = ("eng", "en")

# Accept a PGS track tagged `und` / untagged when no tagged English track exists.
ACCEPT_UNTAGGED = False

# Skip tracks flagged forced, and tracks whose title matches this pattern.
SKIP_FORCED_TRACKS = True
TITLE_EXCLUDE_PATTERN = r"forced|signs|songs|commentary"

# When several English tracks qualify, prefer one whose title matches this
# (e.g. "sdh" for hearing-impaired tracks). Set to None for no preference.
TITLE_PREFER_PATTERN = None

# --- Output ----------------------------------------------------------------

# Appended to the video's stem: "Episode.mkv" -> "Episode.en.srt".
# The language code is what tells Plex the subtitle is English; a bare ".srt" is
# still detected but tagged as unknown language, so it loses auto-selection.
# The video itself is only ever read - the .srt sidecar is the sole file written.
OUTPUT_SUFFIX = ".en.srt"

# Delete an episode's existing .srt sidecars immediately before regenerating that
# episode, one episode at a time rather than a whole folder up front, so an
# interrupted run leaves at most one episode without subtitles. The delete only
# happens once the episode is known to have an English PGS track to replace it
# with. Set False to keep existing sidecars.
DELETE_EXISTING_SRT = True

# Only meaningful when DELETE_EXISTING_SRT is False: leave finished episodes alone.
SKIP_IF_OUTPUT_EXISTS = True

# Print every action without touching the filesystem.
DRY_RUN = False

# Keep the intermediate .sup for debugging. It is always written to TEMP_DIR,
# never into the library folder.
KEEP_SUP = False

# Where the extracted .sup is staged. None uses the system temp directory.
TEMP_DIR = None

# --- OCR -------------------------------------------------------------------

TESSERACT_LANG = "eng"

# 1 = LSTM only (best quality on subtitle bitmaps), 3 = legacy + LSTM.
TESSERACT_OEM = 1

# 6 = assume a single uniform block of text. 7 = single line.
TESSERACT_PSM = 6

# Directory holding <lang>.traineddata. The tessdata_best models OCR subtitles
# noticeably better than the ones Ubuntu's tesseract-ocr-eng package ships:
#   mkdir -p ~/.local/share/tessdata && curl -L -o ~/.local/share/tessdata/eng.traineddata \
#     https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/main/eng.traineddata
# Set to None to use whatever tesseract finds by default. A path that does not
# hold the language file falls back to the system data with a warning.
TESSDATA_DIR = Path.home() / ".local/share/tessdata"

# Stretch each bitmap to the full black-to-white range before OCR. Subtitles are
# often authored in a dim grey rather than pure white, which OCRs worse.
OCR_AUTOCONTRAST = True

# Scale the bitmap before OCR. Small text OCRs better upscaled; 1.0 disables.
OCR_UPSCALE = 2.0

# White margin added around the bitmap. Tesseract misreads text touching the edge.
OCR_PADDING_PX = 20

# Threshold grayscale to pure black/white before OCR (0-255), or None to keep
# the antialiased grayscale, which the LSTM engine generally handles better.
BINARIZE_THRESHOLD = None

# (pattern, replacement) regex pairs applied to each OCR'd cue. Kept minimal on
# purpose - guessing at ambiguous glyphs corrupts more than it fixes. The pipe
# rule is safe because a pipe never appears in subtitle dialogue but is a common
# misread of a capital I (verified against the source bitmap).
OCR_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"\|", "I"),
)

# --- Cue post-processing ---------------------------------------------------

# Drop cues shorter than this (seconds) - usually decoder artefacts.
MIN_CUE_DURATION = 0.10

# Fallback length for a cue the stream never explicitly closed (no following
# display set). Cues closed by the stream keep their exact PGS timing.
UNCLOSED_CUE_DURATION = 12.0

# Merge back-to-back cues that OCR to the same text and are within this gap.
MERGE_IDENTICAL_GAP = 0.30

# --- Performance -----------------------------------------------------------

# Parallel tesseract processes per episode. Each cue is independent.
MAX_OCR_WORKERS = os.cpu_count() or 4

# Tesseract uses OpenMP internally, so without this each of the MAX_OCR_WORKERS
# processes spawns one thread per core and they thrash each other - measured at
# roughly 10x slower on a 4-core box. One thread per process is the documented
# way to batch tesseract; the parallelism comes from running several processes.
TESSERACT_OMP_THREADS = 1

# --- Binaries --------------------------------------------------------------

FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"
TESSERACT = "tesseract"

# ===========================================================================
# PGS bitstream parsing
#
# Segment header: "PG" | PTS u32 | DTS u32 | type u8 | size u16
# Timestamps are in a 90 kHz clock.
# ===========================================================================

PGS_CLOCK = 90000.0

SEG_PDS = 0x14  # palette definition
SEG_ODS = 0x15  # object definition (the bitmap)
SEG_PCS = 0x16  # presentation composition (what to show, and where)
SEG_WDS = 0x17  # window definition
SEG_END = 0x80  # end of display set


@dataclass
class CompositionObject:
    object_id: int
    x: int
    y: int


@dataclass
class PgsObject:
    width: int = 0
    height: int = 0
    data: bytearray = field(default_factory=bytearray)


@dataclass
class Cue:
    start: float
    end: float
    image: Image.Image | None = None
    text: str = ""
    # False until a following display set closes it, which is what gives the cue
    # its true end time. Only unclosed cues fall back to UNCLOSED_CUE_DURATION.
    closed: bool = False


def iter_segments(data: bytes):
    """Yield (pts_seconds, segment_type, payload) over a raw .sup stream."""
    offset, size = 0, len(data)
    while offset + 13 <= size:
        if data[offset:offset + 2] != b"PG":
            # Corrupt or truncated segment - resync on the next magic number.
            nxt = data.find(b"PG", offset + 1)
            if nxt < 0:
                return
            offset = nxt
            continue
        pts = struct.unpack_from(">I", data, offset + 2)[0]
        seg_type = data[offset + 10]
        seg_size = struct.unpack_from(">H", data, offset + 11)[0]
        payload = data[offset + 13:offset + 13 + seg_size]
        if len(payload) < seg_size:
            return
        yield pts / PGS_CLOCK, seg_type, payload
        offset += 13 + seg_size


def parse_pcs(payload: bytes) -> tuple[int, list[CompositionObject]]:
    """Return (palette_id, composition objects). Zero objects means clear screen."""
    palette_id = payload[9]
    count = payload[10]
    offset = 11
    objects: list[CompositionObject] = []
    for _ in range(count):
        if offset + 8 > len(payload):
            break
        object_id = struct.unpack_from(">H", payload, offset)[0]
        cropped = payload[offset + 3]
        x, y = struct.unpack_from(">HH", payload, offset + 4)
        offset += 8
        if cropped & 0x40:
            offset += 8  # crop rectangle, unused
        objects.append(CompositionObject(object_id, x, y))
    return palette_id, objects


def parse_pds(payload: bytes) -> tuple[int, dict[int, tuple[int, int, int, int]]]:
    """Return (palette_id, {entry: (Y, Cr, Cb, alpha)}). May be a partial update."""
    palette_id = payload[0]
    entries: dict[int, tuple[int, int, int, int]] = {}
    offset = 2
    while offset + 5 <= len(payload):
        entry, y, cr, cb, alpha = payload[offset:offset + 5]
        entries[entry] = (y, cr, cb, alpha)
        offset += 5
    return palette_id, entries


def rle_decode(data: bytes, width: int, height: int) -> np.ndarray:
    """Decode PGS run-length data into a height x width array of palette indices.

    00                -> escape; the next byte selects the run:
      00              -> end of line
      00LLLLLL        -> L pixels of colour 0
      01LLLLLL LLLLLLLL       -> L pixels of colour 0
      10LLLLLL CCCCCCCC       -> L pixels of colour C
      11LLLLLL LLLLLLLL CCCCCCCC -> L pixels of colour C
    Any other byte is a single pixel of that colour.
    """
    out = np.zeros((height, width), dtype=np.uint8)
    x = y = 0
    i, n = 0, len(data)
    while i < n and y < height:
        byte = data[i]
        i += 1
        if byte:
            if x < width:
                out[y, x] = byte
            x += 1
            continue
        if i >= n:
            break
        code = data[i]
        i += 1
        if code == 0:
            y += 1
            x = 0
            continue
        kind = code & 0xC0
        if kind == 0x00:
            run, colour = code & 0x3F, 0
        elif kind == 0x40:
            if i >= n:
                break
            run, colour = ((code & 0x3F) << 8) | data[i], 0
            i += 1
        elif kind == 0x80:
            if i >= n:
                break
            run, colour = code & 0x3F, data[i]
            i += 1
        else:
            if i + 1 >= n:
                break
            run = ((code & 0x3F) << 8) | data[i]
            colour = data[i + 1]
            i += 2
        if run and x < width:
            out[y, x:min(x + run, width)] = colour
        x += run
    return out


def render_display_set(
    composition: list[CompositionObject],
    objects: dict[int, PgsObject],
    palette: dict[int, tuple[int, int, int, int]],
) -> Image.Image | None:
    """Compose the display set into a grayscale bitmap cropped to its content.

    PGS draws light text with a dark outline, so the composite is taken over
    black and then inverted, giving tesseract dark text on a light ground.
    """
    placed: list[tuple[CompositionObject, PgsObject, np.ndarray]] = []
    for comp in composition:
        obj = objects.get(comp.object_id)
        if not obj or not obj.width or not obj.height:
            continue
        placed.append((comp, obj, rle_decode(bytes(obj.data), obj.width, obj.height)))
    if not placed:
        return None

    x0 = min(c.x for c, _, _ in placed)
    y0 = min(c.y for c, _, _ in placed)
    x1 = max(c.x + o.width for c, o, _ in placed)
    y1 = max(c.y + o.height for c, o, _ in placed)
    canvas = np.zeros((y1 - y0, x1 - x0), dtype=np.uint8)
    for comp, obj, indices in placed:
        top, left = comp.y - y0, comp.x - x0
        canvas[top:top + obj.height, left:left + obj.width] = indices

    luma_lut = np.zeros(256, dtype=np.uint8)
    alpha_lut = np.zeros(256, dtype=np.uint8)
    for entry, (y, _cr, _cb, alpha) in palette.items():
        luma_lut[entry] = y
        alpha_lut[entry] = alpha

    alpha = alpha_lut[canvas]
    if not alpha.any():
        return None

    # Y is studio-swing (16-235); expand to full range, composite over black.
    luma = (luma_lut[canvas].astype(np.float32) - 16.0) * (255.0 / 219.0)
    composite = np.clip(luma, 0, 255) * (alpha.astype(np.float32) / 255.0)
    return Image.fromarray((255.0 - composite).astype(np.uint8), mode="L")


def parse_sup(data: bytes) -> list[Cue]:
    """Decode a .sup stream into timed subtitle bitmaps."""
    palettes: dict[int, dict[int, tuple[int, int, int, int]]] = {}
    objects: dict[int, PgsObject] = {}
    composition: list[CompositionObject] = []
    palette_id = 0
    set_start = 0.0
    have_composition = False

    cues: list[Cue] = []
    open_cue: Cue | None = None

    for pts, seg_type, payload in iter_segments(data):
        if seg_type == SEG_PCS:
            set_start = pts
            palette_id, composition = parse_pcs(payload)
            have_composition = True

        elif seg_type == SEG_PDS:
            pid, entries = parse_pds(payload)
            palettes.setdefault(pid, {}).update(entries)

        elif seg_type == SEG_ODS:
            if len(payload) < 4:
                continue
            object_id = struct.unpack_from(">H", payload, 0)[0]
            sequence = payload[3]
            if sequence & 0x80:  # first fragment carries the dimensions
                if len(payload) < 11:
                    continue
                width, height = struct.unpack_from(">HH", payload, 7)
                objects[object_id] = PgsObject(width, height, bytearray(payload[11:]))
            elif object_id in objects:
                objects[object_id].data.extend(payload[4:])

        elif seg_type == SEG_END:
            if not have_composition:
                continue
            have_composition = False
            if open_cue is not None:
                open_cue.end = set_start
                open_cue.closed = True
                open_cue = None
            if not composition:
                continue  # clear-screen display set
            image = render_display_set(composition, objects, palettes.get(palette_id, {}))
            if image is None:
                continue
            open_cue = Cue(start=set_start, end=set_start + UNCLOSED_CUE_DURATION, image=image)
            cues.append(open_cue)

    return cues


# ===========================================================================
# OCR
# ===========================================================================

def prepare_for_ocr(image: Image.Image) -> bytes:
    if OCR_AUTOCONTRAST:
        image = ImageOps.autocontrast(image)
    if OCR_UPSCALE != 1.0:
        image = image.resize(
            (max(1, round(image.width * OCR_UPSCALE)), max(1, round(image.height * OCR_UPSCALE))),
            Image.LANCZOS,
        )
    if BINARIZE_THRESHOLD is not None:
        image = image.point(lambda v: 255 if v >= BINARIZE_THRESHOLD else 0, mode="L")
    if OCR_PADDING_PX:
        padded = Image.new("L", (image.width + 2 * OCR_PADDING_PX,
                                 image.height + 2 * OCR_PADDING_PX), 255)
        padded.paste(image, (OCR_PADDING_PX, OCR_PADDING_PX))
        image = padded
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def ocr_image(image: Image.Image) -> str:
    command = [
        TESSERACT, "stdin", "stdout",
        "-l", TESSERACT_LANG,
        "--oem", str(TESSERACT_OEM),
        "--psm", str(TESSERACT_PSM),
    ]
    if TESSDATA_DIR:
        command[1:1] = ["--tessdata-dir", str(TESSDATA_DIR)]
    environment = dict(os.environ)
    if TESSERACT_OMP_THREADS:
        environment["OMP_THREAD_LIMIT"] = str(TESSERACT_OMP_THREADS)
        environment["OMP_NUM_THREADS"] = str(TESSERACT_OMP_THREADS)
    result = subprocess.run(
        command, input=prepare_for_ocr(image), env=environment,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    )
    text = result.stdout.decode("utf-8", "replace")
    for pattern, replacement in OCR_REPLACEMENTS:
        text = re.sub(pattern, replacement, text)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def ocr_cues(cues: list[Cue]) -> None:
    with ThreadPoolExecutor(max_workers=MAX_OCR_WORKERS) as pool:
        texts = pool.map(lambda cue: ocr_image(cue.image), cues)
    for cue, text in zip(cues, texts):
        cue.text = text
        cue.image = None  # release the bitmap once it has been read


# ===========================================================================
# SRT
# ===========================================================================

def clean_cues(cues: list[Cue]) -> list[Cue]:
    kept: list[Cue] = []
    for cue in cues:
        if not cue.text:
            continue
        if not cue.closed:
            cue.end = cue.start + UNCLOSED_CUE_DURATION
        if cue.end - cue.start < MIN_CUE_DURATION:
            continue
        previous = kept[-1] if kept else None
        if (previous and previous.text == cue.text
                and cue.start - previous.end <= MERGE_IDENTICAL_GAP):
            previous.end = cue.end
            continue
        kept.append(cue)
    return kept


def format_timestamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def render_srt(cues: list[Cue]) -> str:
    blocks = [
        f"{number}\n{format_timestamp(cue.start)} --> {format_timestamp(cue.end)}\n{cue.text}"
        for number, cue in enumerate(cues, start=1)
    ]
    return "\n\n".join(blocks) + "\n"


# ===========================================================================
# Container probing and PGS extraction
# ===========================================================================

def probe_pgs_streams(video: Path) -> list[dict]:
    """Return the file's HDMV PGS subtitle streams, whatever the container."""
    result = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "s",
         "-show_entries", "stream=index,codec_name:stream_disposition=default,forced"
                          ":stream_tags=language,title",
         "-of", "json", str(video)],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    )
    if result.returncode != 0:
        return []
    import json
    try:
        streams = json.loads(result.stdout or b"{}").get("streams", [])
    except json.JSONDecodeError:
        return []
    return [s for s in streams if s.get("codec_name") == "hdmv_pgs_subtitle"]


def select_english_streams(streams: list[dict]) -> list[dict]:
    """Every plausible English PGS track, not just one.

    Track metadata cannot identify the full track on its own. On these discs both
    English tracks are often unflagged, and the one marked `default` is the forced
    subset - a Blu-ray shows forced subtitles by default during English audio - so
    preferring `default` reliably picks the near-empty track. The caller decides by
    content instead, keeping whichever yields the most cues.
    """
    wanted = {code.lower() for code in SUBTITLE_LANGUAGES}
    exclude = re.compile(TITLE_EXCLUDE_PATTERN, re.I) if TITLE_EXCLUDE_PATTERN else None

    candidates = []
    for stream in streams:
        tags = stream.get("tags") or {}
        disposition = stream.get("disposition") or {}
        language = (tags.get("language") or "").lower()
        title = tags.get("title") or ""
        if language in wanted:
            rank = 0
        elif ACCEPT_UNTAGGED and language in ("", "und"):
            rank = 1
        else:
            continue
        # An explicit forced flag or title is still worth honouring as a cheap
        # prefilter; it is simply not sufficient on its own.
        if SKIP_FORCED_TRACKS:
            if disposition.get("forced"):
                continue
            if exclude and exclude.search(title):
                continue
        candidates.append((rank, stream["index"], stream))
    return [stream for _, _, stream in sorted(candidates, key=lambda c: c[:2])]


def extract_sups(video: Path, indices: list[int], staging: Path) -> dict[int, Path]:
    """Extract several subtitle tracks in ONE pass over the container.

    Pulling a track means reading the whole file, so all candidates are written
    from a single ffmpeg invocation rather than one read per track.
    """
    outputs = {index: staging / f"extract-pgs_{os.getpid()}_{video.stem}.{index}.sup"
               for index in indices}
    command = [FFMPEG, "-v", "error", "-y", "-i", str(video)]
    for index in indices:
        command += ["-map", f"0:{index}", "-c:s", "copy", "-f", "sup", str(outputs[index])]
    result = subprocess.run(command, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        print(f"      ffmpeg: {result.stderr.decode('utf-8', 'replace').strip()[:200]}")
    return {index: path for index, path in outputs.items()
            if path.exists() and path.stat().st_size > 0}


# ===========================================================================
# Pipeline
# ===========================================================================

def natural_key(name: str) -> list:
    """Sort key that orders Season 2 before Season 10."""
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", name)]


def find_season_folders(root: Path) -> dict[Path, list[Path]]:
    """Group every video under root by its containing folder, in walk order."""
    skip = {name.lower() for name in SKIP_DIR_NAMES}
    extensions = {extension.lower() for extension in VIDEO_EXTENSIONS}
    folders: dict[Path, list[Path]] = {}
    for directory, subdirectories, filenames in os.walk(root):
        subdirectories[:] = sorted(
            (d for d in subdirectories if d.lower() not in skip), key=natural_key)
        videos = [
            Path(directory) / name
            for name in sorted(filenames, key=natural_key)
            if PROBE_ALL_FILES or Path(name).suffix.lower() in extensions
        ]
        if videos:
            folders[Path(directory)] = videos
    return folders


def build_work_plan(root: Path) -> list[tuple[Path, list[Path]]] | None:
    """Ordered (folder, videos) chunks to process.

    START_AT rotates the episode order so the named episode runs first. With
    WRAP_AROUND the episodes before it run last rather than being skipped, so a
    run started mid-series still covers everything. Returns None if START_AT
    matches no video, so the caller can fail loudly instead of doing nothing.
    """
    folders = find_season_folders(root)
    flat = [(folder, video) for folder, videos in folders.items() for video in videos]
    if not flat:
        return []

    start = 0
    if START_AT:
        needle = START_AT.lower()
        start = next((i for i, (_, v) in enumerate(flat) if needle in str(v).lower()), -1)
        if start < 0:
            return None

    ordered = flat[start:] + flat[:start] if WRAP_AROUND else flat[start:]

    # Group consecutive episodes sharing a folder, so logging and the .srt purge
    # stay per folder visit. A folder split by the wrap point appears twice.
    chunks: list[tuple[Path, list[Path]]] = []
    for folder, video in ordered:
        if chunks and chunks[-1][0] == folder:
            chunks[-1][1].append(video)
        else:
            chunks.append((folder, [video]))
    return chunks


def purge_episode_srt(video: Path) -> None:
    """Delete one episode's .srt sidecars, immediately before regenerating it."""
    stale = [p for p in video.parent.iterdir()
             if p.is_file() and p.suffix.lower() == ".srt"
             and p.name.startswith(video.stem)]
    for path in sorted(stale, key=lambda p: natural_key(p.name)):
        print(f"    {'would delete' if DRY_RUN else 'deleted'} {path.name}")
        if not DRY_RUN:
            path.unlink()


def process_episode(video: Path) -> bool:
    output = video.with_name(video.stem + OUTPUT_SUFFIX)
    if not DELETE_EXISTING_SRT and SKIP_IF_OUTPUT_EXISTS and output.exists():
        print(f"    skip (exists)  {video.name}")
        return False

    streams = select_english_streams(probe_pgs_streams(video))
    if not streams:
        print(f"    no English PGS {video.name}")
        return False

    indices = [stream["index"] for stream in streams]
    if DRY_RUN:
        print(f"    would OCR      {video.name} (streams {indices}) -> {output.name}")
        if DELETE_EXISTING_SRT:
            purge_episode_srt(video)
        return False

    if DELETE_EXISTING_SRT:
        purge_episode_srt(video)

    staging = Path(TEMP_DIR) if TEMP_DIR else Path(tempfile.gettempdir())
    sups = {}
    try:
        sups = extract_sups(video, indices, staging)
        if not sups:
            print(f"    extract failed {video.name}")
            return False

        # Decide by content: the full track is the one with the most cues. A
        # forced track carries only foreign dialogue, so it comes out tiny.
        decoded = {index: parse_sup(path.read_bytes()) for index, path in sups.items()}
        chosen = max(decoded, key=lambda index: len(decoded[index]))
        if len(decoded) > 1:
            counts = ", ".join(f"{i}:{len(c)}" for i, c in sorted(decoded.items()))
            print(f"    tracks {counts} -> using stream {chosen}")
        cues = clean_cues_after_ocr(decoded[chosen])
    finally:
        if not KEEP_SUP:
            for path in sups.values():
                if path.exists():
                    path.unlink()

    if not cues:
        print(f"    no text        {video.name}")
        return False

    output.write_text(render_srt(cues), encoding="utf-8")
    print(f"    {len(cues):4d} cues     {video.name} -> {output.name}")
    return True


def clean_cues_after_ocr(cues: list[Cue]) -> list[Cue]:
    ocr_cues(cues)
    return clean_cues(cues)


def main() -> int:
    # Progress must appear live even when stdout is redirected to a log file,
    # otherwise a multi-hour batch run shows nothing until it finishes.
    sys.stdout.reconfigure(line_buffering=True)

    root = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else ROOT_DIR
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        return 1

    for binary in (FFMPEG, FFPROBE, TESSERACT):
        if subprocess.run(["which", binary], stdout=subprocess.DEVNULL,
                          check=False).returncode != 0:
            print(f"Missing required binary: {binary}", file=sys.stderr)
            return 1

    if TESSDATA_DIR and not Path(TESSDATA_DIR, f"{TESSERACT_LANG}.traineddata").is_file():
        print(f"No {TESSERACT_LANG}.traineddata in {TESSDATA_DIR} - using system tessdata.")
        globals()["TESSDATA_DIR"] = None

    print(f"Root: {root}{'  (DRY RUN)' if DRY_RUN else ''}")
    if START_AT:
        print(f"Starting at: {START_AT}" + ("  (wrapping around afterwards)" if WRAP_AROUND else ""))
    plan = build_work_plan(root)
    if plan is None:
        print(f"\nNothing processed: no video matched START_AT ({START_AT!r}).")
        return 1

    written = 0
    for folder, videos in plan:
        print(f"\n{folder}")
        for video in videos:
            try:
                written += process_episode(video)
            except Exception as error:  # one bad episode must not stop the run
                print(f"    ERROR          {video.name}: {error}")

    print(f"\nDone. {written} subtitle file(s) written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
