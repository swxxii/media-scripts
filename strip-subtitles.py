#!/usr/bin/env python3
import os, sys, json, subprocess, logging, argparse
from tqdm import tqdm

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "strip-subtitles.log")
EXTS = {".mkv", ".mp4", ".m4v", ".avi", ".mov"}

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S",
                    filename=LOG_FILE)

def mediainfo(path):
    result = subprocess.run(["mediainfo", "--Output=JSON", path], capture_output=True, text=True)
    return json.loads(result.stdout)["media"]["track"]

def count_subs(tracks):
    return sum(1 for t in tracks if t["@type"] == "Text")

def get_duration(tracks):
    for t in tracks:
        if t["@type"] == "General":
            try:
                return float(t["Duration"])
            except (KeyError, ValueError):
                return None
    return None

def strip(src, duration, test=False):
    tmp = src + ".tmp"
    logging.info(f"START {src}")
    total = min(duration, 600) if (test and duration) else duration
    cmd = ["nice", "-n", "19",
           "ffmpeg", "-loglevel", "error", "-progress", "pipe:1", "-i", src,
           "-map", "0:v", "-map", "0:a",
           "-c", "copy"]
    if test:
        cmd += ["-t", "600"]
    cmd.append(tmp)
    try:
        with tqdm(total=int(total) if total else None, unit="s", unit_scale=True,
                  ncols=80, desc=os.path.basename(src), file=sys.stdout) as bar:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            current = 0
            for line in proc.stdout:
                if line.startswith("out_time_ms="):
                    val = line.strip().split("=")[1]
                    if val.lstrip("-").isdigit():
                        secs = int(val) / 1_000_000
                        if secs > current:
                            bar.update(secs - current)
                            current = secs
            proc.wait()
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, cmd)
        os.replace(tmp, src)
        logging.info(f"DONE {src}")
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise

def process(path, test=False):
    try:
        tracks = mediainfo(path)
        n = count_subs(tracks)
        if not n:
            logging.info(f"NO SUBS {path}")
        else:
            logging.info(f"STRIP {path} ({n} sub tracks)")
            strip(path, get_duration(tracks), test=test)
    except Exception as e:
        logging.error(f"ERROR {path}: {e}")

def scan(target, test=False):
    if os.path.isfile(target):
        if "[4K]" in os.path.basename(target):
            process(target, test=test)
        return
    for root, dirs, files_in_dir in os.walk(target):
        dirs.sort()
        for fname in sorted(files_in_dir):
            if os.path.splitext(fname)[1].lower() in EXTS and "[4K]" in fname:
                process(os.path.join(root, fname), test=test)

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
