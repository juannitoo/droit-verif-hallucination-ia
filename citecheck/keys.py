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
    value = os.environ.get(name, "").strip()
    if value:
        return value
    if keyring:
        try:
            return (keyring.get_password(NAME, name) or "").strip() or None
        except Exception:
            return None
    return None


def looks_like_key(value):
    """Une clé d'accès est d'un seul tenant : ni espace ni retour à la ligne, des caractères
    ASCII visibles. Une phrase collée par erreur dans le champ (c'est arrivé) est refusée,
    au lieu d'être enregistrée puis envoyée à la base, qui répondrait « requête invalide »
    sans dire pourquoi."""
    return 8 <= len(value) <= 256 and all("!" <= ch <= "~" for ch in value)


def save(name, value):
    """Store the key in the keyring. Returns False if the system has none."""
    if not keyring:
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
