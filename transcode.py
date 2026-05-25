#!/usr/bin/env python3
import sys, os, json, subprocess

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
        print(f"  ! skipped: output already exists")
        return
    print(f"  → {', '.join(reasons)} — transcoding...")
    subprocess.run([
        "ffmpeg", "-i", src,
        "-map", "0:v", "-map", "0:a", "-map", "0:s?",
        "-c:v", "copy", "-c:a", "ac3", "-b:a", "640k", "-c:s", "copy",
        dst
    ], check=True)
    print(f"  ✓ saved: {os.path.basename(dst)}")

folder = sys.argv[1] if len(sys.argv) > 1 else "."
exts = {".mkv", ".mp4", ".m4v", ".avi", ".mov"}

for root, dirs, files in os.walk(folder):
    dirs.sort()
    for fname in sorted(files):
        if os.path.splitext(fname)[1].lower() not in exts:
            continue
        path = os.path.join(root, fname)
        print(path)
        try:
            reasons = needs_transcode(mediainfo(path))
            if reasons:
                transcode(path, reasons)
            else:
                print("  ✓ ok")
        except Exception as e:
            print(f"  ! error: {e}")
