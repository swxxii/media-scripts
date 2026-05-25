#!/usr/bin/env python3
import os, json, subprocess, logging, time, argparse, glob

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "transcode.log")
TRANSCODED_SUFFIX = "[transcoded]"
EXTS = {".mkv", ".mp4", ".m4v", ".avi", ".mov"}

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

def mediainfo(path):
    result = subprocess.run(["mediainfo", "--Output=JSON", path], capture_output=True, text=True)
    return json.loads(result.stdout)["media"]["track"]

def needs_transcode(tracks):
    reasons = []
    for t in tracks:
        if t["@type"] == "Audio":
            fmt = t.get("Format", "")
            extra = t.get("Format_AdditionalFeatures", "")
            name = t.get("CommercialName", "")
            if fmt == "MLP FBA":
                reasons.append("TrueHD")
            elif fmt == "DTS":
                reasons.append("DTS-HD MA" if "XLL" in extra else "DTS")
            elif "JOC" in extra or "Atmos" in name:
                reasons.append("Dolby Atmos")
    return reasons

def transcode(src, reasons, test=False):
    base, ext = os.path.splitext(src)
    dst = f"{base} {TRANSCODED_SUFFIX}{ext}"
    if os.path.exists(dst):
        return
    logging.info(f"START {src} [{', '.join(reasons)}]" + (" [test]" if test else ""))
    cmd = ["nice", "-n", "19", "ffmpeg", "-loglevel", "error", "-i", src]
    if test:
        cmd += ["-t", "600"]
    cmd += ["-map", "0:v", "-map", "0:a", "-map", "0:s?",
            "-c:v", "copy", "-c:a", "ac3", "-b:a", "640k", "-c:s", "copy", dst]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    logging.info(f"DONE {src}")

def process(path, test=False):
    if TRANSCODED_SUFFIX in os.path.basename(path):
        return
    try:
        tracks = mediainfo(path)
        reasons = needs_transcode(tracks)
        if reasons:
            logging.info(f"TRANSCODE {path} [{', '.join(reasons)}]")
            transcode(path, reasons, test=test)
        else:
            logging.info(f"OK {path}")
    except Exception as e:
        logging.error(f"ERROR {path}: {e}")

def scan(target, test=False):
    if os.path.isfile(target):
        process(target, test=test)
        return
    for root, dirs, files in os.walk(target):
        dirs.sort()
        for fname in sorted(files):
            if os.path.splitext(fname)[1].lower() in EXTS:
                process(os.path.join(root, fname), test=test)

def watch():
    while True:
        os.system("clear")
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
        jobs = [l for l in result.stdout.splitlines() if "ffmpeg" in l and "grep" not in l]
        if jobs:
            for job in jobs:
                print(job)
        else:
            print("No active transcodes.")
        time.sleep(2)

parser = argparse.ArgumentParser()
parser.add_argument("path", nargs="?", default=".")
parser.add_argument("--watch", action="store_true")
parser.add_argument("--test", action="store_true")
args = parser.parse_args()

if args.watch:
    watch()
else:
    logging.info(f"SCAN {args.path}")
    scan(args.path, test=args.test)
    logging.info("SCAN done")
