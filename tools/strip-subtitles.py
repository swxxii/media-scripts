#!/usr/bin/env python3
"""Remove unwanted subtitle tracks from video files, keeping chosen languages.

Rewrites each file with only the subtitle tracks you want to keep. MKV files go
through mkvmerge, which preserves chapters, attachments, tags and track metadata;
other containers fall back to ffmpeg. Language matching uses the container's own
tags via mkvmerge/ffprobe rather than a normalising tool, because a Matroska file
stores ISO 639-2/B codes ("fre", "ger", "chi") that do not match the two-letter
codes some tools report.

A file that already contains only wanted subtitle tracks is skipped, so a re-run
costs nothing. Nothing is written in place: each file is rebuilt beside itself and
atomically swapped in only after it verifies.

Usage:  ./strip-subtitles.py [PATH]
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from tqdm import tqdm

# ===========================================================================
# Configuration
# ===========================================================================

# Subtitle languages to KEEP. Everything else is removed. Accepts two- or
# three-letter codes in any variant - "en", "eng" and "fra"/"fre" all resolve to
# the same language. An empty tuple removes every subtitle track.
KEEP_LANGUAGES: tuple[str, ...] = ("eng",)

# Also keep subtitle tracks that carry no language tag at all.
KEEP_UNTAGGED = False

# Only process files whose name contains this string. "" processes everything.
# Defaults to the 4K files, which is what the original script was pointed at.
FILENAME_FILTER = "[4K]"

VIDEO_EXTENSIONS = (".mkv", ".mp4", ".m4v", ".avi", ".mov")

# Print what would happen without rewriting anything.
DRY_RUN = False

# Refuse to rebuild a file unless the filesystem has this much free space beyond
# the size of the file itself, since the rebuild lands beside the original.
FREE_SPACE_MARGIN_BYTES = 2 * 1024**3

# Run the remux at low CPU priority so it stays out of the way.
NICE_LEVEL = 19

MKVMERGE = "mkvmerge"
FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"

# ===========================================================================
# Language codes
#
# Matroska stores ISO 639-2/B. The bibliographic and terminological forms differ
# for a handful of languages, and users type the two-letter form, so every known
# spelling of one language is collapsed to a single key.
# ===========================================================================

LANGUAGE_ALIASES = (
    ("eng", "en"), ("fre", "fra", "fr"), ("ger", "deu", "de"), ("chi", "zho", "zh"),
    ("cze", "ces", "cs"), ("dut", "nld", "nl"), ("gre", "ell", "el"), ("rum", "ron", "ro"),
    ("slo", "slk", "sk"), ("per", "fas", "fa"), ("ice", "isl", "is"), ("may", "msa", "ms"),
    ("arm", "hye", "hy"), ("geo", "kat", "ka"), ("baq", "eus", "eu"), ("wel", "cym", "cy"),
    ("alb", "sqi", "sq"), ("bur", "mya", "my"), ("mac", "mkd", "mk"), ("tib", "bod", "bo"),
    ("spa", "es"), ("ita", "it"), ("por", "pt"), ("rus", "ru"), ("pol", "pl"),
    ("dan", "da"), ("swe", "sv"), ("nor", "no"), ("fin", "fi"), ("hun", "hu"),
    ("tur", "tr"), ("heb", "he"), ("hrv", "hr"), ("srp", "sr"), ("slv", "sl"),
    ("kor", "ko"), ("jpn", "ja"), ("tha", "th"), ("ara", "ar"), ("hin", "hi"),
    ("vie", "vi"), ("ind", "id"), ("ukr", "uk"), ("bul", "bg"), ("cat", "ca"),
    ("est", "et"), ("lav", "lv"), ("lit", "lt"), ("ron", "ro"),
)

_CANONICAL = {code: group[0] for group in LANGUAGE_ALIASES for code in group}

# Codes a container uses when it means "unknown".
UNTAGGED = {"", "und", "undetermined", "mis", "zxx", None}


def canonical_language(code: str | None) -> str | None:
    """Collapse any spelling of a language to one key; None when untagged."""
    if code is None:
        return None
    code = code.strip().lower()
    # "en-GB" and "pt-BR" carry a region; the base language is what we match on.
    base = code.split("-")[0]
    if base in UNTAGGED or not base:
        return None
    return _CANONICAL.get(base, base)


KEEP_SET = {canonical_language(code) for code in KEEP_LANGUAGES} - {None}


def is_wanted(code: str | None) -> bool:
    language = canonical_language(code)
    if language is None:
        return KEEP_UNTAGGED
    return language in KEEP_SET


# ===========================================================================
# Inspecting a file
# ===========================================================================

@dataclass
class SubtitleTrack:
    track_id: int          # the id understood by the backend that found it
    language: str | None
    title: str


@dataclass
class Inspection:
    subtitles: list[SubtitleTrack]

    @property
    def keep(self) -> list[SubtitleTrack]:
        return [t for t in self.subtitles if is_wanted(t.language)]

    @property
    def drop(self) -> list[SubtitleTrack]:
        return [t for t in self.subtitles if not is_wanted(t.language)]


def inspect_mkv(path: Path) -> Inspection:
    """Track ids here are mkvmerge's own, which is what --subtitle-tracks wants."""
    result = subprocess.run([MKVMERGE, "-J", str(path)],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
    data = json.loads(result.stdout)
    return Inspection([
        SubtitleTrack(track["id"],
                      track["properties"].get("language"),
                      track["properties"].get("track_name") or "")
        for track in data.get("tracks", []) if track["type"] == "subtitles"
    ])


def inspect_other(path: Path) -> Inspection:
    """Track ids here are absolute ffmpeg stream indices, for -map 0:<index>."""
    result = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "s",
         "-show_entries", "stream=index:stream_tags=language,title",
         "-of", "json", str(path)],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
    streams = json.loads(result.stdout or "{}").get("streams", [])
    return Inspection([
        SubtitleTrack(stream["index"],
                      (stream.get("tags") or {}).get("language"),
                      (stream.get("tags") or {}).get("title") or "")
        for stream in streams
    ])


def inspect(path: Path) -> Inspection:
    return inspect_mkv(path) if path.suffix.lower() == ".mkv" else inspect_other(path)


# ===========================================================================
# Rebuilding a file
# ===========================================================================

def run_with_progress(command: list[str], pattern: re.Pattern, label: str,
                      tool: str, ok_returncodes: tuple[int, ...] = (0,)) -> None:
    """Run a remux, driving a progress bar off percentages in its stdout.

    ok_returncodes exists because mkvmerge reports warnings with exit code 1 and
    only genuine failures with 2. Treating 1 as failure throws away a perfectly
    good rebuild. Progress is parsed from stdout, which is also where these tools
    print their diagnostics, so the tail is kept to explain a real failure.
    """
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, bufsize=1)
    tail: deque[str] = deque(maxlen=20)
    with tqdm(total=100, unit="%", ncols=80, desc=label, file=sys.stdout,
              leave=False) as bar:
        for line in process.stdout:
            line = line.rstrip()
            match = pattern.search(line)
            if match:
                percent = min(100, int(match.group(1)))
                if percent > bar.n:
                    bar.update(percent - bar.n)
            elif line:
                tail.append(line)
        process.wait()

    errors = (process.stderr.read() or "").strip()
    if process.returncode not in ok_returncodes:
        detail = errors or "; ".join(tail) or f"exited {process.returncode}"
        raise RuntimeError(f"{tool} exited {process.returncode}: {detail}")
    if process.returncode != 0:
        for line in tail:
            if re.search(r"warning", line, re.I):
                print(f"         {tool} warning: {line}")


MKVMERGE_PROGRESS = re.compile(r"Progress:\s*(\d+)%")
FFMPEG_PROGRESS = re.compile(r"out_time_ms=(\d+)")


def rebuild_mkv(source: Path, destination: Path, keep: list[SubtitleTrack]) -> None:
    selection = (["--subtitle-tracks", ",".join(str(t.track_id) for t in keep)]
                 if keep else ["--no-subtitles"])
    run_with_progress(
        # No --quiet: it suppresses the "Progress: N%" lines the bar reads, and
        # the warning text needed to explain a non-zero exit.
        ["nice", "-n", str(NICE_LEVEL), MKVMERGE, "-o", str(destination)]
        + selection + [str(source)],
        MKVMERGE_PROGRESS, source.name[:40],
        tool="mkvmerge", ok_returncodes=(0, 1))  # 1 = completed with warnings


def rebuild_other(source: Path, destination: Path, keep: list[SubtitleTrack]) -> None:
    mapping = ["-map", "0:v", "-map", "0:a"]
    for track in keep:
        mapping += ["-map", f"0:{track.track_id}"]
    run_with_progress(
        ["nice", "-n", str(NICE_LEVEL), FFMPEG, "-loglevel", "error",
         "-progress", "pipe:1", "-nostdin", "-i", str(source)]
        + mapping + ["-c", "copy", str(destination)],
        FFMPEG_PROGRESS, source.name[:40], tool="ffmpeg")


# ===========================================================================
# Processing
# ===========================================================================

def describe(tracks: list[SubtitleTrack]) -> str:
    languages = sorted({canonical_language(t.language) or "und" for t in tracks})
    return ",".join(languages) if languages else "none"


def process(path: Path) -> bool:
    """Rebuild one file if it holds unwanted subtitles. True if it was rewritten."""
    try:
        found = inspect(path)
    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as error:
        print(f"ERROR    {path.name}: could not inspect ({error})")
        return False

    if not found.drop:
        print(f"SKIP     {path.name} ({len(found.subtitles)} subs, all wanted)")
        return False

    print(f"STRIP    {path.name}: keep {len(found.keep)} [{describe(found.keep)}] "
          f"drop {len(found.drop)} [{describe(found.drop)}]")
    if DRY_RUN:
        return False

    if not found.keep and KEEP_SET:
        # Every subtitle would go despite wanting a language: worth saying, since
        # it usually means the file simply has no track in that language.
        print(f"         note: no {'/'.join(sorted(KEEP_SET))} track present")

    size = path.stat().st_size
    free = shutil.disk_usage(path.parent).free
    if free < size + FREE_SPACE_MARGIN_BYTES:
        print(f"ERROR    {path.name}: not enough free space "
              f"({free / 1024**3:.1f}G free, needs {(size + FREE_SPACE_MARGIN_BYTES) / 1024**3:.1f}G)")
        return False

    temporary = path.with_name(path.stem + ".stripping" + path.suffix)
    try:
        if path.suffix.lower() == ".mkv":
            rebuild_mkv(path, temporary, found.keep)
        else:
            rebuild_other(path, temporary, found.keep)

        # Verify the rebuilt file before it replaces anything.
        rebuilt = inspect(temporary)
        if rebuilt.drop:
            raise RuntimeError(f"{len(rebuilt.drop)} unwanted track(s) survived")
        if len(rebuilt.subtitles) != len(found.keep):
            raise RuntimeError(f"expected {len(found.keep)} subtitle track(s), "
                               f"got {len(rebuilt.subtitles)}")

        os.replace(temporary, path)
        saved = (size - path.stat().st_size) / 1024**2
        print(f"DONE     {path.name} ({saved:.0f} MB smaller)")
        return True
    except Exception as error:
        print(f"ERROR    {path.name}: {error}")
        return False
    finally:
        if temporary.exists():
            temporary.unlink()


def natural_key(name: str) -> list:
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", name)]


def find_videos(target: Path) -> list[Path]:
    extensions = {extension.lower() for extension in VIDEO_EXTENSIONS}
    if target.is_file():
        return [target] if target.suffix.lower() in extensions else []
    found: list[Path] = []
    for directory, subdirectories, filenames in os.walk(target):
        subdirectories.sort(key=natural_key)
        for name in sorted(filenames, key=natural_key):
            if Path(name).suffix.lower() in extensions and FILENAME_FILTER in name:
                found.append(Path(directory) / name)
    return found


def main() -> int:
    target = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else Path(".")
    if not target.exists():
        print(f"Error: path not found: {target}", file=sys.stderr)
        return 1
    for binary in ({MKVMERGE, FFPROBE} | ({FFMPEG} if FFMPEG else set())):
        if shutil.which(binary) is None:
            print(f"Missing required binary: {binary}", file=sys.stderr)
            return 1

    sys.stdout.reconfigure(line_buffering=True)
    videos = find_videos(target)
    print(f"Scanning {target}{'  (DRY RUN)' if DRY_RUN else ''}")
    print(f"Keeping subtitle languages: {'/'.join(sorted(KEEP_SET)) or 'none'}"
          f"{' + untagged' if KEEP_UNTAGGED else ''}   |   {len(videos)} file(s)\n")

    rewritten = sum(process(video) for video in videos)
    print(f"\nDone. {rewritten} file(s) rewritten.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
