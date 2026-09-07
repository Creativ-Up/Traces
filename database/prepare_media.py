#!/usr/bin/env python3
"""
Préparation des médias des nouveaux musées (Huis van Alijn, MuMons) pour le kiosk.

À LANCER SUR LA MACHINE D'AURÉLIEN (les masters font ~2,5 Go, ils ne transitent pas).

Ce que fait le script :
  - TIF / PNG  -> JPG qualité 88, redimensionné à 2000 px max sur le grand côté
  - JPG / JPEG -> recopiés (re-encodés seulement si > 2000 px)
  - MP4        -> recopiés tels quels (+ contrôle de l'encodage si ffprobe est là)
  - MOV / NEF  -> IGNORÉS (masters de montage / RAW : doublons des MP4 et des JPG)
  - renommage à la convention du projet : minuscules, séparateurs -> '-',
    extension préservée (imadeyou-01-053.jpg)
  - écrit un CSV de correspondance : nom d'origine -> nom final (sert au matching)

Prérequis :  pip install pillow
Usage :
    python prepare_media.py "C:\\Users\\539288\\Downloads\\transfer-01a00fb8" assets_hva
    python prepare_media.py "C:\\Users\\539288\\Downloads\\MuMons_DB_TRACES"   assets_mumons
"""
import csv
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None  # les TIF de numérisation dépassent la limite par défaut

CONVERT_EXTS = {'.tif', '.tiff', '.png'}
COPY_IMAGE_EXTS = {'.jpg', '.jpeg'}
COPY_VIDEO_EXTS = {'.mp4'}
SKIP_EXTS = {'.mov', '.nef', '.cr2', '.arw', '.dng', '.xlsx', '.xls', '.csv', '.txt', '.pdf'}

MAX_SIDE = 2000
JPEG_QUALITY = 88


def normalize_name(stem: str) -> str:
    """MÊME algorithme que migrate_v3.normalize_media_name (stem uniquement)."""
    s = stem.strip().lower()
    s = re.sub(r'[_.\s]+', '-', s)
    s = re.sub(r'[^a-z0-9-]', '', s)
    return re.sub(r'-{2,}', '-', s).strip('-')


def check_video(path: Path) -> str:
    """Retourne le codec via ffprobe si disponible, sinon ''."""
    try:
        out = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
             '-show_entries', 'stream=codec_name', '-of', 'csv=p=0', str(path)],
            capture_output=True, text=True, timeout=30)
        return out.stdout.strip()
    except Exception:
        return ''


def main(src_dir: str, out_dir: str) -> None:
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
            # vignette : première image nette de la vidéo (le front l'affiche en grille)
            thumb = out / (normalize_name(f.stem) + '-thumb.jpg')
            try:
                subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', '1', '-i', str(f),
                                '-frames:v', '1', '-vf', f'scale={MAX_SIDE}:-1', str(thumb)],
                               capture_output=True, timeout=60)
                if thumb.exists():
                    mapping.append((f.name + ' (vignette)', thumb.name,
                                    round(thumb.stat().st_size / 1024)))
                else:
                    warnings.append(f'{f.name} : vignette non générée (ffmpeg absent ?)')
            except Exception:
                warnings.append(f'{f.name} : vignette non générée (ffmpeg absent ?)')
            codec = check_video(f)
            if codec and codec not in ('h264', 'avc1'):
                warnings.append(f'{f.name} : codec {codec} (le kiosk attend du H.264 — à ré-encoder)')
            elif not codec:
                warnings.append(f'{f.name} : codec non vérifié (ffprobe absent)')

        else:
            skipped.append(f.name)
            continue

        mapping.append((f.name, target.name, round(target.stat().st_size / 1024)))

    with open(out / '_media_mapping.csv', 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['fichier_origine', 'fichier_final', 'taille_ko'])
        w.writerows(mapping)

    print(f'{len(mapping)} fichiers préparés dans {out.resolve()}')
    print(f'{len(skipped)} ignorés (MOV, NEF, documents) : {", ".join(skipped[:6])}'
          + (' ...' if len(skipped) > 6 else ''))
    total = sum(m[2] for m in mapping) / 1024
    print(f'poids total : {total:.1f} Mo')
    for w_ in warnings:
        print('  ⚠', w_)
    print(f'correspondance écrite dans {out / "_media_mapping.csv"}')


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
