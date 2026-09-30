"""Le débit vers PISTE, le portail de l'État qui délivre les clés de Légifrance et de
Judilibre : c'est lui qui freinerait, ou bloquerait, un utilisateur trop pressé.

LE PLAFOND
  PER_MINUTE requêtes par minute au plus, Légifrance et Judilibre ensemble (mêmes clés,
  même portail). Réglage provisoire, dans le code seulement, en attendant l'avis du support
  de PISTE (01/10/2026). Ordres de grandeur, pour un document de 15 citations (environ 30
  requêtes de contrôle des bases, puis 2 à 3 par citation) :
      10 par minute   environ 8 minutes
      30 par minute   environ 3 minutes
      60 par minute   environ 1 min 30
     100 par minute   moins d'une minute
  ArianeWeb (Conseil d'État) et CELLAR (Union européenne) ne passent pas par PISTE : ils
  gardent leur propre pause.

TROP DE REQUÊTES (HTTP 429)
  Au premier refus, on s'arrête net, pour Légifrance comme pour Judilibre : on ne sait pas
  quand PISTE débloquera, et insister aggraverait. Les citations restantes sortent « non
  vérifiées », avec la raison. La vérification suivante réessaie (reset).
"""
import threading
import time

PER_MINUTE = 100          # 10 | 30 | 60 | 100 : 100 tant que Jean teste seul
LIMITED = "PISTE a limité les requêtes : relancez la vérification plus tard"


class Limited(Exception):
    """PISTE a répondu « trop de requêtes » : plus aucune requête d'ici la fin."""

    def __init__(self):
        super().__init__(LIMITED)


_lock = threading.Lock()
_next = 0.0             # l'heure (time.monotonic) avant laquelle aucune requête ne part
_limited = False


def reset():
    """Au début de chaque vérification : un refus d'hier ne vaut pas pour aujourd'hui."""
    global _limited
    _limited = False


def limited():
    return _limited


def wait():
    """Avant chaque requête vers PISTE : attend son tour, ou refuse si PISTE a déjà dit
    « trop de requêtes »."""
    global _next
    if _limited:
        raise Limited()
    with _lock:
        now = time.monotonic()
        if _next > now:
            time.sleep(_next - now)
        _next = max(now, _next) + 60 / PER_MINUTE


def refused(status):
    """Après une réponse d'erreur de PISTE. Un 429 arrête tout ; renvoie True dans ce cas."""
    global _limited
    if status == 429:
        _limited = True
    return _limited
