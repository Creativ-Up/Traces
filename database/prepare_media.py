#!/usr/bin/env python3
"""
Prepares the media files delivered by a museum for the TRACES kiosk.

What the script does:
  - TIF / PNG  -> JPG, quality 88, resized to 2000 px max on the long side
  - JPG / JPEG -> copied as .jpg (re-encoded only if larger than 2000 px)
  - MP4        -> copied as is, plus a thumbnail "<name>-thumb.jpg" taken at
                  1 second (ffmpeg) and a check of the H.264 codec (ffprobe)
  - MOV / RAW (NEF, CR2…) / documents -> skipped: export them to MP4 (H.264)
    or JPG/TIF first
  - renames files to the TRACES convention: lower case, separators -> '-',
    extension kept (IMadeYou_01_053.JPG -> imadeyou-01-053.jpg).
    import_collection.py applies the same rule to the names in the spreadsheet.
  - writes _media_mapping.csv in the output folder: original name -> final name

The output folder is a working folder: then copy the media files (not the CSV)
into assets/ at the root of the repository. Videos must be smaller than 100 MB
(GitHub limit): re-encode larger ones.

Requirements:  pip install pillow  (+ ffmpeg for video thumbnails)
Usage:
    python prepare_media.py <folder of your media> <output folder> --assets ../assets

  --assets   warns when a prepared file has the same name as a file already in
             assets/ (copying it would overwrite another artwork's file)
"""
from __future__ import annotations

import csv
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None  # scanned TIFs exceed Pillow's default limit

CONVERT_EXTS = {'.tif', '.tiff', '.png'}
COPY_IMAGE_EXTS = {'.jpg', '.jpeg'}
COPY_VIDEO_EXTS = {'.mp4'}
SKIP_EXTS = {'.mov', '.nef', '.cr2', '.arw', '.dng', '.xlsx', '.xls', '.csv', '.txt', '.pdf'}

MAX_SIDE = 2000
JPEG_QUALITY = 88


def normalize_name(stem: str) -> str:
    """SAME rule as import_collection.normalize_media_name (stem only)."""
    s = unicodedata.normalize('NFKD', stem.strip().lower()).encode('ascii', 'ignore').decode()  # é -> e
    s = re.sub(r'[_.\s]+', '-', s)
    s = re.sub(r'[^a-z0-9-]', '', s)
    return re.sub(r'-{2,}', '-', s).strip('-')


def check_video(path: Path) -> str:
    """Video codec name via ffprobe if available, otherwise ''."""
    try:
        out = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
             '-show_entries', 'stream=codec_name', '-of', 'csv=p=0', str(path)],
            capture_output=True, text=True, timeout=30)
        return out.stdout.strip()
    except Exception:
        return ''


def main(src_dir: str, out_dir: str, assets_dir: str | None = None) -> None:
    src, out = Path(src_dir), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    mapping, skipped, warnings = [], [], []

    for f in sorted(src.iterdir()):
        if not f.is_file():
            continue
        ext = f.suffix.lower()
        if ext in SKIP_EXTS:
            skipped.append(f.name)
            continue

        if ext in CONVERT_EXTS:
            target = out / (normalize_name(f.stem) + '.jpg')
            with Image.open(f) as im:
                im = im.convert('RGB')
                if max(im.size) > MAX_SIDE:
                    ratio = MAX_SIDE / max(im.size)
                    im = im.resize((round(im.width * ratio), round(im.height * ratio)),
                                   Image.LANCZOS)
                im.save(target, 'JPEG', quality=JPEG_QUALITY, optimize=True)

        elif ext in COPY_IMAGE_EXTS:
            target = out / (normalize_name(f.stem) + '.jpg')
            with Image.open(f) as im:
                if max(im.size) > MAX_SIDE:
                    im = im.convert('RGB')
                    ratio = MAX_SIDE / max(im.size)
                    im = im.resize((round(im.width * ratio), round(im.height * ratio)),
                                   Image.LANCZOS)
                    im.save(target, 'JPEG', quality=JPEG_QUALITY, optimize=True)
                else:
                    shutil.copy2(f, target)

        elif ext in COPY_VIDEO_EXTS:
            target = out / (normalize_name(f.stem) + '.mp4')
            shutil.copy2(f, target)
            # thumbnail: a frame of the video (the kiosk shows it in the grid)
            thumb = out / (normalize_name(f.stem) + '-thumb.jpg')
            try:
                subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', '1', '-i', str(f),
                                '-frames:v', '1', '-vf', f'scale={MAX_SIDE}:-1', str(thumb)],
                               capture_output=True, timeout=60)
                if thumb.exists():
                    mapping.append((f.name + ' (thumbnail)', thumb.name,
                                    round(thumb.stat().st_size / 1024)))
                else:
                    warnings.append(f'{f.name}: thumbnail not created (is ffmpeg installed?)')
            except Exception:
                warnings.append(f'{f.name}: thumbnail not created (is ffmpeg installed?)')
            codec = check_video(f)
            if codec and codec not in ('h264', 'avc1'):
                warnings.append(f'{f.name}: codec {codec} (the kiosk expects H.264, re-encode it)')
            elif not codec:
                warnings.append(f'{f.name}: codec not checked (is ffprobe installed?)')

        else:
            skipped.append(f.name)
            continue

        mapping.append((f.name, target.name, round(target.stat().st_size / 1024)))

    with open(out / '_media_mapping.csv', 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['original_file', 'final_file', 'size_kb'])
        w.writerows(mapping)

    for name, final, size_kb in mapping:
        if size_kb > 95 * 1024:
            warnings.append(f'{final}: {size_kb / 1024:.0f} MB, GitHub refuses files over 100 MB (re-encode it)')
    # name collisions: two of your files, or one of yours and a file already in assets/
    finals = [final for _name, final, _size in mapping]
    for final in sorted({f for f in finals if finals.count(f) > 1}):
        sources = [name for name, f, _size in mapping if f == final]
        warnings.append(f'{final}: produced by several files {sources}: rename them so they differ')
    if assets_dir:
        existing = {p.name for p in Path(assets_dir).iterdir() if p.is_file()}
        clash = sorted(set(finals) & existing)
        for final in clash:
            warnings.append(f'{final} already exists in {assets_dir}: copying would overwrite another '
                            "artwork's file. Rename yours (e.g. add your museum's name) and prepare it again")
    print(f'{len(mapping)} files prepared in {out.resolve()}')
    print(f'{len(skipped)} skipped (MOV, RAW, documents): {", ".join(skipped[:6])}'
          + (' ...' if len(skipped) > 6 else ''))
    total = sum(m[2] for m in mapping) / 1024
    print(f'total size: {total:.1f} MB')
    for w_ in warnings:
        print('  ⚠', w_)
    print(f'file name mapping written to {out / "_media_mapping.csv"}')
    print('  → next step: copy the images and videos (not the CSV) into assets/, '
          'then run import_collection.py')


if __name__ == '__main__':
    args = sys.argv[1:]
    assets = None
    if '--assets' in args:
        i = args.index('--assets')
        assets = args[i + 1] if i + 1 < len(args) else None
        del args[i:i + 2]
        if not assets or not Path(assets).is_dir():
            sys.exit('--assets: folder not found')
    if len(args) != 2:
        sys.exit(__doc__)
    main(args[0], args[1], assets)
