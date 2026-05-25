#!/usr/bin/env python3
import sys, os, json, subprocess, logging
from datetime import datetime

LOG_FILE = os.path.expanduser("~/transcode.log")
logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format="%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

def mediainfo(path):
    result = subprocess.run(
        ["mediainfo", "--Output=JSON", path],
        capture_output=True, text=True
    )
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

def transcode(src, reasons):
    base, ext = os.path.splitext(src)
    dst = f"{base} [transcoded]{ext}"
    if os.path.exists(dst):
        logging.info(f"SKIP {src} (output exists)")
        return
    logging.info(f"START {src} [{', '.join(reasons)}]")
    subprocess.Popen([
        "nice", "-n", "19",
        "ffmpeg", "-loglevel", "error", "-i", src,
        "-map", "0:v", "-map", "0:a", "-map", "0:s?",
        "-c:v", "copy", "-c:a", "ac3", "-b:a", "640k", "-c:s", "copy",
        dst
    ], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

folder = sys.argv[1] if len(sys.argv) > 1 else "."
exts = {".mkv", ".mp4", ".m4v", ".avi", ".mov"}
logging.info(f"SCAN {folder}")

for root, dirs, files in os.walk(folder):
    dirs.sort()
    for fname in sorted(files):
        if os.path.splitext(fname)[1].lower() not in exts:
            continue
        path = os.path.join(root, fname)
        try:
            reasons = needs_transcode(mediainfo(path))
            if reasons:
                transcode(path, reasons)
        except Exception as e:
            logging.error(f"ERROR {path}: {e}")

logging.info("SCAN done")
