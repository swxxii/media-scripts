#!/usr/bin/env python3
"""
File Extension Restorer - Restores correct extensions for photo/video files.
"""
import os, sys, re, shutil, argparse
from pathlib import Path

# Magic signatures: (bytes, offset, extension, description)
SIGNATURES = [
    # Images
    (b'\xFF\xD8\xFF', 0, '.jpg', 'JPEG'), (b'\x89PNG\r\n\x1a\n', 0, '.png', 'PNG'),
    (b'GIF87a', 0, '.gif', 'GIF'), (b'GIF89a', 0, '.gif', 'GIF'),
    (b'BM', 0, '.bmp', 'BMP'), (b'II*\x00', 0, '.tiff', 'TIFF'), (b'MM\x00*', 0, '.tiff', 'TIFF'),
    # HEIC/HEIF
    (b'ftypheic', 4, '.heic', 'HEIC'), (b'ftypheix', 4, '.heic', 'HEIC'),
    (b'ftypmif1', 4, '.heif', 'HEIF'), (b'ftypavif', 4, '.avif', 'AVIF'),
    # Videos
    (b'ftypisom', 4, '.mp4', 'MP4'), (b'ftypiso2', 4, '.mp4', 'MP4'),
    (b'ftypmp41', 4, '.mp4', 'MP4'), (b'ftypmp42', 4, '.mp4', 'MP4'),
    (b'ftypM4V ', 4, '.m4v', 'M4V'), (b'ftypqt  ', 4, '.mov', 'MOV'),
    (b'moov', 4, '.mov', 'MOV'), (b'ftyp3gp', 4, '.3gp', '3GP'),
    (b'\x00\x00\x00\x1cftyp', 0, '.mp4', 'MP4'), (b'\x00\x00\x00\x18ftyp', 0, '.mp4', 'MP4'),
    (b'\x00\x00\x00\x20ftyp', 0, '.mp4', 'MP4'),
    (b'\x1a\x45\xdf\xa3', 0, '.mkv', 'MKV'), (b'FLV\x01', 0, '.flv', 'FLV'),
    (b'\x00\x00\x01\xBA', 0, '.mpg', 'MPEG'), (b'\x00\x00\x01\xB3', 0, '.mpg', 'MPEG'),
    (b'OggS', 0, '.ogv', 'OGG'), (b'RIFF', 0, '.avi', 'RIFF'),  # Special handling below
]

EQUIV_EXT = [{'.jpg', '.jpeg'}, {'.tif', '.tiff'}, {'.mpg', '.mpeg'}]
SKIP = ['.DS_Store', '._.', '@Syno', '@eaDir', 'Thumbs.db', 'desktop.ini', '.Spotlight', '.Trashes']

def read_header(path, size=64):
    try:
        with open(path, 'rb') as f: return f.read(size)
    except: return b''

def detect_type(path):
    h = read_header(path)
    if not h: return None
    for magic, off, ext, desc in SIGNATURES:
        if len(h) > off + len(magic) and h[off:off+len(magic)] == magic:
            if magic == b'RIFF' and len(h) >= 12:
                if h[8:12] == b'WEBP': return ('.webp', 'WebP')
                elif h[8:12] == b'AVI ': return ('.avi', 'AVI')
                continue
            if magic == b'\x1a\x45\xdf\xa3':
                return ('.webm', 'WebM') if b'webm' in h.lower() else ('.mkv', 'MKV')
            return (ext, desc)
    return None

def ext_equiv(a, b):
    a, b = a.lower(), b.lower()
    return a == b or any(a in s and b in s for s in EQUIV_EXT)

def sanitize(name):
    name = ''.join(c if ord(c) < 128 else '_' for c in name)
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f\s]+', '_', name).strip(' ._')
    return name[:200] if name else 'unnamed'

def should_skip(name):
    return any(p in name for p in SKIP)

def unique_path(path):
    if not path.exists(): return path
    stem, ext, parent, i = path.stem, path.suffix, path.parent, 1
    while (parent / f"{stem}_{i}{ext}").exists(): i += 1
    return parent / f"{stem}_{i}{ext}"

def process(directory, dry_run=True, interactive=False, move_unknown=None, sanitize_names=False):
    dir_path = Path(directory)
    if not dir_path.is_dir():
        print(f"Error: '{directory}' is not a valid directory."); sys.exit(1)
    
    stats = {'files': 0, 'renamed': 0, 'skipped': 0, 'unknown': 0, 'errors': 0}
    unknown_dir = Path(move_unknown) if move_unknown else None
    if unknown_dir and not dry_run: unknown_dir.mkdir(parents=True, exist_ok=True)
    auto_all = False
    
    mode = "DRY RUN" if dry_run else ("INTERACTIVE" if interactive else "LIVE")
    print(f"\n{'='*50}\nScanning: {directory}\nMode: {mode}\n{'='*50}\n")
    
    for root, _, files in os.walk(dir_path):
        for fname in files:
            fpath = Path(root) / fname
            stats['files'] += 1
            
            if should_skip(fname): continue
            
            result = detect_type(fpath)
            if result is None:
                stats['unknown'] += 1
                if move_unknown:
                    dest = unique_path(unknown_dir / fname)
                    if dry_run: print(f"? {fname} -> would move to {dest}")
                    else:
                        try: shutil.move(str(fpath), str(dest)); print(f"? {fname} -> moved")
                        except Exception as e: print(f"? {fname} -> error: {e}"); stats['errors'] += 1
                continue
            
            ext, desc = result
            cur_ext = fpath.suffix.lower()
            if ext_equiv(cur_ext, ext): stats['skipped'] += 1; continue
            
            new_stem = sanitize(fpath.stem) if sanitize_names else fpath.stem
            new_path = unique_path(fpath.parent / (new_stem + ext))
            new_name = new_path.name
            
            if dry_run:
                print(f"-> {fname} => {new_name} ({desc})")
            elif interactive and not auto_all:
                r = input(f"-> {fname} => {new_name}? [y/n/a/q]: ").strip().lower()
                if r == 'q': break
                if r == 'a': auto_all = True
                if r not in ('y', 'a', ''): continue
                try: fpath.rename(new_path); stats['renamed'] += 1; print(f"   Done")
                except Exception as e: print(f"   Error: {e}"); stats['errors'] += 1
            else:
                try: fpath.rename(new_path); stats['renamed'] += 1; print(f"-> {fname} => {new_name}")
                except Exception as e: print(f"-> {fname} => Error: {e}"); stats['errors'] += 1
    
    print(f"\n{'='*50}\nFiles: {stats['files']} | Renamed: {stats['renamed']} | Skipped: {stats['skipped']} | Unknown: {stats['unknown']} | Errors: {stats['errors']}\n{'='*50}")

def main():
    p = argparse.ArgumentParser(description='Restore correct file extensions for photos/videos.')
    p.add_argument('directory', help='Directory to scan')
    p.add_argument('--dry-run', action='store_true', help='Preview changes without modifying files')
    p.add_argument('-i', '--interactive', action='store_true', help='Prompt for each file')
    p.add_argument('--move-unknown', metavar='DIR', help='Move unknown files to DIR')
    p.add_argument('--sanitize-names', action='store_true', help='Clean problematic chars from filenames')
    a = p.parse_args()
    
    dry_run = a.dry_run or a.interactive
    process(a.directory, dry_run=dry_run, interactive=a.interactive, 
            move_unknown=a.move_unknown, sanitize_names=a.sanitize_names)

if __name__ == '__main__': main()
