#!/usr/bin/env python3
"""
Prépare les médias livrés par un musée pour le kiosque TRACES.

Ce que fait le script :
  - TIF / PNG  -> JPG qualité 88, redimensionné à 2000 px max sur le grand côté
  - JPG / JPEG -> recopiés en .jpg (ré-encodés seulement si > 2000 px)
  - MP4        -> recopiés tels quels, + vignette « <nom>-thumb.jpg » extraite à
                  1 seconde (ffmpeg) et contrôle du codec H.264 (ffprobe)
  - MOV / RAW (NEF, CR2…) / documents -> ignorés : demander au musée des MP4
    (H.264) et des JPG/TIF, ou les convertir avant
  - renommage à la convention TRACES : minuscules, séparateurs -> '-',
    extension préservée (IMadeYou_01_053.JPG -> imadeyou-01-053.jpg).
    import_collection.py applique la même règle aux noms cités dans le tableur.
  - écrit _media_mapping.csv dans le dossier de sortie : nom d'origine -> nom final

Le dossier de sortie est un dossier de travail : copier ensuite les médias
(pas le CSV) dans assets/ à la racine du repo. Les vidéos doivent peser moins
de 100 Mo (limite de GitHub) : ré-encoder les plus lourdes.

Prérequis :  pip install pillow  (+ ffmpeg pour les vignettes des vidéos)
Usage :
    python prepare_media.py <dossier livré par le musée> <dossier de sortie>
"""
import csv
import re
import shutil
import subprocess
import sys
import unicodedata
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
    """MÊME règle que import_collection.normalize_media_name (stem uniquement)."""
    s = unicodedata.normalize('NFKD', stem.strip().lower()).encode('ascii', 'ignore').decode()  # é -> e
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
