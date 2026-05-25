#!/usr/bin/env python3
import os, sys, json, subprocess, argparse
from tqdm import tqdm

TRANSCODED_SUFFIX = "[transcoded]"
EXTS = {".mkv", ".mp4", ".m4v", ".avi", ".mov"}

def mediainfo(path):
    result = subprocess.run(["mediainfo", "--Output=JSON", path], capture_output=True, text=True)
    return json.loads(result.stdout)["media"]["track"]

def get_duration(tracks):
    for t in tracks:
        if t["@type"] == "General":
            try:
                return float(t["Duration"])
            except (KeyError, ValueError):
                return None
    return None

def needs_transcode(tracks):
    video_reasons = []
    audio_reasons = []
    for t in tracks:
        if t["@type"] == "Video":
            fmt = t.get("Format", "")
            depth = t.get("BitDepth", "8")
            if depth == "10":
                video_reasons.append(f"{fmt} 10-bit")
            elif fmt in ("AV1", "VP9"):
                video_reasons.append(fmt)
        if t["@type"] == "Audio":
            fmt = t.get("Format", "")
            extra = t.get("Format_AdditionalFeatures", "")
            name = t.get("CommercialName", "")
            if fmt == "MLP FBA":
                audio_reasons.append("TrueHD")
            elif fmt == "DTS":
                audio_reasons.append("DTS-HD MA" if "XLL" in extra else "DTS")
            elif "JOC" in extra or "Atmos" in name:
                audio_reasons.append("Dolby Atmos")
    return video_reasons, audio_reasons

def transcode(src, duration, video_reasons, audio_reasons, test=False):
    base, ext = os.path.splitext(src)
    suffix = "[transcode-test]" if test else TRANSCODED_SUFFIX
    dst = f"{base} {suffix}{ext}"
    if not test and os.path.exists(dst):
        tqdm.write(f"SKIP {os.path.basename(src)}")
        return
    reasons = ", ".join(video_reasons + audio_reasons)
    label = "TEST" if test else "TRANSCODE"
    tqdm.write(f"{label} {os.path.basename(src)} [{reasons}]")
    total = min(duration, 600) if (test and duration) else duration
    cmd = ["nice", "-n", "19", "ffmpeg", "-loglevel", "error", "-progress", "pipe:1", "-y", "-i", src]
    if test:
        cmd += ["-t", "600"]
    preset = "ultrafast" if test else "slow"
    video_codec = ["libx264", "-crf", "18", "-preset", preset, "-pix_fmt", "yuv420p"] if video_reasons else ["copy"]
    audio_codec = ["ac3", "-b:a", "640k"] if audio_reasons else ["copy"]
    cmd += ["-map", "0:v", "-map", "0:a", "-map", "0:s?",
            "-c:v"] + video_codec + ["-c:a"] + audio_codec + ["-c:s", "copy", dst]
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

def process(path, test=False):
    if TRANSCODED_SUFFIX in os.path.basename(path) or "[transcode-test]" in os.path.basename(path):
        return
    try:
        tracks = mediainfo(path)
        video_reasons, audio_reasons = needs_transcode(tracks)
        if video_reasons or audio_reasons:
            transcode(path, get_duration(tracks), video_reasons, audio_reasons, test=test)
    except Exception as e:
        tqdm.write(f"ERROR {path}: {e}")

def scan(target, test=False):
    if os.path.isfile(target):
        process(target, test=test)
        return
    for root, dirs, files in os.walk(target):
        dirs.sort()
        for fname in sorted(files):
            if os.path.splitext(fname)[1].lower() in EXTS:
                process(os.path.join(root, fname), test=test)

parser = argparse.ArgumentParser()
parser.add_argument("path", nargs="?", default=".")
parser.add_argument("--test", action="store_true", help="transcode first 10 minutes only")
args = parser.parse_args()

if not os.path.exists(args.path):
    print(f"Error: path not found: {args.path}")
else:
    scan(args.path, test=args.test)
