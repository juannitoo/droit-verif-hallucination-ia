"""Access keys for the databases (the user's own accounts).

Lookup order: the environment variable of the same name, then the system keyring (Windows
Credential Manager, macOS Keychain). Keys are never written to a file by this program,
never displayed, and never sent anywhere but to the database they unlock.
"""
import os

from . import NAME

try:
    import keyring
except ImportError:          # no keyring: only environment variables work
    keyring = None


def get(name):
    """La clé, ou None si elle manque ou n'a pas la forme d'une clé : une valeur mal formée
    (variable d'environnement, ancien trousseau) ne part pas dans un en-tête, elle compte
    comme absente, et la fenêtre propose de la saisir à nouveau."""
    value = os.environ.get(name, "").strip()
    if not value and keyring:
        try:
            value = (keyring.get_password(NAME, name) or "").strip()
        except Exception:
            value = ""
    return value if value and looks_like_key(value) else None


def looks_like_key(value):
    """Une clé d'accès est d'un seul tenant : ni espace ni retour à la ligne, des caractères
    ASCII visibles. Une phrase collée par erreur dans le champ (c'est arrivé) est refusée,
    au lieu d'être enregistrée puis envoyée à la base, qui répondrait « requête invalide »
    sans dire pourquoi."""
    return 8 <= len(value) <= 256 and all("!" <= ch <= "~" for ch in value)


def save(name, value):
    """Store the key in the keyring. Returns False if the system has none, or if the value
    is not shaped like a key (looks_like_key)."""
    if not keyring or not looks_like_key(value.strip()):
        return False
    try:
        keyring.set_password(NAME, name, value.strip())
        return True
    except Exception:
        return False


def delete(name):
    if keyring:
        try:
            keyring.delete_password(NAME, name)
        except Exception:
            pass
