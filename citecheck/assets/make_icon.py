"""
Génère assets/icon.ico et assets/icon.png.

Deux sources :
  - icon-16.png, icon-24.png, icon-32.png : dessinées au pixel près, pour la barre de titre
    (16 px à 100 %, 24 à 150 %, 32 à 200 %). À ces tailles, un vecteur réduit est flou :
    chaque trait y tombe sur des pixels entiers. Se retouchent pixel par pixel (Paint.NET,
    Photoshop, crayon 1 px). Le 20 px (écrans à 125 %) est tiré du 24.
  - icon.svg : toutes les autres tailles (40 à 256 px), dessinées par Edge directement
    depuis le vecteur. Se retouche dans Illustrator ou Inkscape.
Après une retouche de l'une ou l'autre, relancer ce script.

Le programme n'a besoin ni de Pillow ni d'Edge ; ce script, si. Le relancer avec un Python qui
a Pillow, par exemple celui de l'assistant vocal :
    C:\\code\\assistant-vocal\\_env\\Scripts\\python.exe citecheck\\assets\\make_icon.py

Dans Illustrator : garder le plan de travail carré, 1024 × 1024, et enregistrer en SVG
(« Enregistrer sous » > SVG) par-dessus icon.svg.
"""
import os
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
SVG = HERE / "icon.svg"
SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]
PIXEL = [16, 24, 32]          # tailles lues dans icon-<taille>.png quand le fichier existe
EDGE = [Path(os.environ.get(v, "")) / "Microsoft/Edge/Application/msedge.exe"
        for v in ("ProgramFiles(x86)", "ProgramFiles")]


def _render(edge, size, work):
    """icon.svg dessiné par Edge à size × size, fond transparent."""
    page = work / "page.html"
    page.write_text('<!doctype html><body style="margin:0;background:transparent">'
                    f'<img src="{SVG.as_uri()}" style="display:block;width:100vw;'
                    'height:100vh"></body>', encoding="utf-8")
    out = work / f"{size}.png"
    subprocess.run([str(edge), "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--allow-file-access-from-files", "--default-background-color=00000000",
                    "--force-device-scale-factor=1", f"--window-size={size},{size}",
                    f"--screenshot={out}", page.as_uri()],
                   check=True, capture_output=True, timeout=60)
    return Image.open(out).convert("RGBA")


def main():
    edge = next((e for e in EDGE if e.is_file()), None)
    if not edge:
        raise SystemExit("Edge introuvable : il sert à dessiner le SVG à chaque taille.")
    pixel = {s: Image.open(HERE / f"icon-{s}.png").convert("RGBA")
             for s in PIXEL if (HERE / f"icon-{s}.png").is_file()}
    if 24 in pixel:
        pixel.setdefault(20, pixel[24].resize((20, 20), Image.LANCZOS))
    with tempfile.TemporaryDirectory() as tmp:
        images = [pixel[s] if s in pixel else _render(edge, s, Path(tmp)) for s in SIZES]
    print("au pixel près :", sorted(pixel), "- depuis le SVG :",
          [s for s in SIZES if s not in pixel])
    big = images[-1]
    big.save(HERE / "icon.ico", sizes=[(s, s) for s in SIZES], append_images=images[:-1])
    big.save(HERE / "icon.png")
    print("icon.ico et icon.png écrits dans", HERE)


if __name__ == "__main__":
    main()
