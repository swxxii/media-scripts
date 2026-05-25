#!/usr/bin/env python3
import sys, os, json, subprocess, logging, time, argparse, glob

LOG_FILE = os.path.expanduser("~/transcode.log")
PROGRESS_DIR = "/tmp/transcode_progress"
logging.basicConfig(filename=LOG_FILE, filemode="w", level=logging.INFO,
                    format="%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

def mediainfo(path):
    result = subprocess.run(
        ["mediainfo", "--Output=JSON", path],
        capture_output=True, text=True
    )
    return json.loads(result.stdout)["media"]["track"]

def get_duration(tracks):
    for t in tracks:
        if t["@type"] == "General":
            return float(t.get("Duration", 0)) / 1000  # ms → seconds
    return 0

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

def transcode(src, reasons, tracks):
    base, ext = os.path.splitext(src)
    dst = f"{base} [transcoded]{ext}"
    if os.path.exists(dst):
        return

    os.makedirs(PROGRESS_DIR, exist_ok=True)
    job_id = str(abs(hash(src)))[:10]
    progress_file = f"{PROGRESS_DIR}/{job_id}.progress"
    info_file = f"{PROGRESS_DIR}/{job_id}.info"

    with open(info_file, "w") as f:
        json.dump({"src": src, "duration": get_duration(tracks), "reasons": reasons}, f)

    logging.info(f"START {src} [{', '.join(reasons)}]")
    subprocess.Popen([
        "nice", "-n", "19",
        "ffmpeg", "-loglevel", "error", "-progress", progress_file, "-i", src,
        "-map", "0:v", "-map", "0:a", "-map", "0:s?",
        "-c:v", "copy", "-c:a", "ac3", "-b:a", "640k", "-c:s", "copy",
        dst
    ], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def scan(folder, seen):
    exts = {".mkv", ".mp4", ".m4v", ".avi", ".mov"}
    for root, dirs, files in os.walk(folder):
        dirs.sort()
        for fname in sorted(files):
            if os.path.splitext(fname)[1].lower() not in exts:
                continue
            path = os.path.join(root, fname)
            if path in seen:
                continue
            seen.add(path)
            try:
                tracks = mediainfo(path)
                reasons = needs_transcode(tracks)
                if reasons:
                    transcode(path, reasons, tracks)
            except Exception as e:
                logging.error(f"ERROR {path}: {e}")

def fmt_time(seconds):
    h, m, s = int(seconds // 3600), int(seconds % 3600 // 60), int(seconds % 60)
    return f"{h}:{m:02d}:{s:02d}"

def watch():
    while True:
        os.system("clear")
        jobs = glob.glob(f"{PROGRESS_DIR}/*.progress")
        if not jobs:
            print("No active transcodes.")
        for pf in sorted(jobs):
            job_id = os.path.basename(pf).replace(".progress", "")
            info_file = f"{PROGRESS_DIR}/{job_id}.info"
            try:
                with open(info_file) as f:
                    info = json.load(f)
                progress = {}
                with open(pf) as f:
                    for line in f:
                        if "=" in line:
                            k, v = line.strip().split("=", 1)
                            progress[k] = v
                current = float(progress.get("out_time_us", 0)) / 1_000_000
                duration = info["duration"]
                pct = min(100.0, current / duration * 100) if duration else 0
                name = os.path.basename(info["src"])
                status = progress.get("progress", "")
                if status == "end":
                    print(f"  done  {name}")
                    os.unlink(pf)
                    os.unlink(info_file)
                else:
                    print(f"  {pct:5.1f}%  {fmt_time(current)} / {fmt_time(duration)}  {name}")
            except Exception:
                pass
        time.sleep(2)

parser = argparse.ArgumentParser()
parser.add_argument("folder", nargs="?", default=".")
parser.add_argument("--watch", action="store_true", help="monitor active transcodes")
args = parser.parse_args()

if args.watch:
    watch()
else:
    seen = set()
    logging.info(f"SCAN {args.folder}")
    scan(args.folder, seen)
    logging.info("SCAN done")
