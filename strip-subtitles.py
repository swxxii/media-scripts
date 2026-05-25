#!/usr/bin/env python3
import os, json, subprocess, logging, argparse
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, MofNCompleteColumn, TextColumn, TimeElapsedColumn

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "strip-subtitles.log")
STRIPPED_SUFFIX = "[cleaned-subs]"
EXTS = {".mkv", ".mp4", ".m4v", ".avi", ".mov"}

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S",
                    filename=LOG_FILE)

def mediainfo(path):
    result = subprocess.run(["mediainfo", "--Output=JSON", path], capture_output=True, text=True)
    return json.loads(result.stdout)["media"]["track"]

def get_subtitle_langs(tracks):
    langs = []
    for t in tracks:
        if t["@type"] == "Text":
            langs.append(t.get("Language", "").lower())
    return langs

def needs_strip(langs):
    non_english = [l for l in langs if l not in ("en", "eng", "")]
    return len(non_english) > 0

def strip(src, test=False):
    base, ext = os.path.splitext(src)
    dst = f"{base} {STRIPPED_SUFFIX}{ext}"
    if os.path.exists(dst):
        logging.info(f"SKIP {src} (already stripped)")
        return
    logging.info(f"START {src}")
    cmd = ["nice", "-n", "19",
           "ffmpeg", "-loglevel", "error", "-i", src,
           "-map", "0:v", "-map", "0:a", "-map", "0:s:m:language:eng?",
           "-c", "copy"]
    if test:
        cmd += ["-t", "600"]
    cmd.append(dst)
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    logging.info(f"DONE {src}")

def process(path, test=False):
    if STRIPPED_SUFFIX in os.path.basename(path):
        return
    try:
        tracks = mediainfo(path)
        langs = get_subtitle_langs(tracks)
        if not langs:
            logging.info(f"NO SUBS {path}")
        elif needs_strip(langs):
            logging.info(f"STRIP {path} ({len(langs)} sub tracks, keeping English only)")
            strip(path, test=test)
        else:
            logging.info(f"OK {path} (English only)")
    except Exception as e:
        logging.error(f"ERROR {path}: {e}")

def scan(target, test=False):
    if os.path.isfile(target):
        process(target, test=test)
        return
    files = []
    for root, dirs, files_in_dir in os.walk(target):
        dirs.sort()
        for fname in sorted(files_in_dir):
            if os.path.splitext(fname)[1].lower() in EXTS:
                files.append(os.path.join(root, fname))
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=Console(force_terminal=True, force_interactive=True),
    ) as progress:
        task = progress.add_task("scanning", total=len(files))
        for path in files:
            progress.update(task, description=os.path.basename(path))
            process(path, test=test)
            progress.advance(task)

parser = argparse.ArgumentParser()
parser.add_argument("path", nargs="?", default=".")
parser.add_argument("--test", action="store_true", help="process first 10 minutes only")
args = parser.parse_args()

if not os.path.exists(args.path):
    print(f"Error: path not found: {args.path}")
else:
    logging.info(f"SCAN {args.path}")
    scan(args.path, test=args.test)
    logging.info("SCAN done")
