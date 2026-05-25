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

def strip(src, duration):
    base, ext = os.path.splitext(src)
    tmp = base + ".tmp" + ext
    logging.info(f"START {src}")
    cmd = ["nice", "-n", "19",
           "ffmpeg", "-loglevel", "error", "-progress", "pipe:1", "-i", src,
           "-map", "0:v", "-map", "0:a",
           "-c", "copy", tmp]
    try:
        with tqdm(total=int(duration) if duration else None, unit="s", unit_scale=True,
                  ncols=80, desc=os.path.basename(src), file=sys.stdout) as bar:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
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
            err = proc.stderr.read().strip()
            raise subprocess.CalledProcessError(proc.returncode, cmd, stderr=err)
        os.replace(tmp, src)
        remaining = count_subs(mediainfo(src))
        if remaining:
            print(f"VERIFY FAIL {os.path.basename(src)} ({remaining} sub tracks remain)")
            logging.warning(f"VERIFY FAILED {src} ({remaining} sub tracks remain)")
        else:
            logging.info(f"DONE {src}")
    except subprocess.CalledProcessError as e:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise RuntimeError(e.stderr or f"ffmpeg exited {e.returncode}")
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise

def process(path):
    try:
        tracks = mediainfo(path)
        n = count_subs(tracks)
        if not n:
            print(f"NO SUBS  {os.path.basename(path)}")
            logging.info(f"NO SUBS {path}")
        else:
            print(f"STRIP    {os.path.basename(path)} ({n} sub tracks)")
            logging.info(f"STRIP {path} ({n} sub tracks)")
            strip(path, get_duration(tracks))
            print(f"DONE     {os.path.basename(path)}")
    except Exception as e:
        print(f"ERROR    {os.path.basename(path)}: {e}")
        logging.error(f"ERROR {path}: {e}")

def scan(target):
    if os.path.isfile(target):
        if "[4K]" in os.path.basename(target):
            process(target)
        return
    for root, dirs, files_in_dir in os.walk(target):
        dirs.sort()
        for fname in sorted(files_in_dir):
            if os.path.splitext(fname)[1].lower() in EXTS and "[4K]" in fname:
                process(os.path.join(root, fname))

parser = argparse.ArgumentParser()
parser.add_argument("path", nargs="?", default=".")
args = parser.parse_args()

if not os.path.exists(args.path):
    print(f"Error: path not found: {args.path}")
else:
    print(f"Scanning {args.path}")
    logging.info(f"SCAN {args.path}")
    scan(args.path)
    logging.info("SCAN done")
    print("Done")
