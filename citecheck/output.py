"""Écrire ce que produit le programme (rapports, PDF annoté) : jamais sur le document vérifié,
jamais à moitié.

Le document est une pièce du dossier. Un nom mal choisi dans une boîte de dialogue, ou
`-o conclusions.pdf` en ligne de commande, ne doit pas la remplacer par un rapport.
"""
import os
from pathlib import Path

from .locales import t


class OverDocument(Exception):
    """Le fichier choisi est le document vérifié : rien n'est écrit."""

    def __init__(self):
        super().__init__(t.NOT_OVER_DOCUMENT)


def same_file(a, b):
    """Les deux chemins désignent-ils le même fichier ? Un lien physique, un nom court
    (CONCLU~1.PDF), une autre casse ou un chemin réseau comptent comme le même."""
    try:
        if os.path.exists(a) and os.path.exists(b):
            return os.path.samefile(a, b)
        return Path(a).resolve() == Path(b).resolve()
    except (OSError, ValueError):
        return True             # dans le doute, on n'écrit pas


def write(target, data, document=None):
    """Écrit `data` (texte ou octets) dans `target`, d'abord à côté puis à sa place : un arrêt
    en cours (fenêtre fermée, disque plein) ne laisse pas un fichier tronqué sous le nom
    choisi. Refuse si `target` est le document vérifié."""
    if document and same_file(target, document):
        raise OverDocument()
    if isinstance(data, str):
        data = data.replace(chr(10), os.linesep).encode("utf-8")   # comme open(..., "w")
    partial = f"{target}.partiel"
    try:
        with open(partial, "wb") as f:
            f.write(data)
        os.replace(partial, target)
    finally:
        if os.path.exists(partial):
            os.remove(partial)
