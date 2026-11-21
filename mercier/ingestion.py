"""Ingestion de donnees recues dans la zone brute"""
import hashlib
from pathlib import Path
import json
import shutil
from datetime import datetime

from mercier import config

FICHIERS_ATTENDUS = [
    "articles.csv",
    "ventes_octobre.csv",
    "boutiques.json",
    "journal_boutique.log"
]

def empreinte(chemin):
    """Detecte les doublons en renvoyant l'empreinte sha-256 d'un fichier"""
    calcul = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(65536), b""):
            calcul.update(bloc)
    return calcul.hexdigest()

def ingerer(sources=None, zone_brute=None, horodatage=None) :
    """Copie les fichiers attendus dans un lot horodaté."""
    sources= Path(sources or config.SOURCES)
    zone_brute =Path(zone_brute or config.ZONE_BRUTE)
    horodatage =horodatage or datetime.now().strftime("%Y%m%d_%H%M%S")

    lot= zone_brute /horodatage
    lot.mkdir(parents=True,exist_ok=True)

    recus, manquants =[], []
    for nom in FICHIERS_ATTENDUS:
        origine =sources/nom
        if not origine.exists():
            manquants.append(nom)
            continue
        destination = lot/nom
        shutil.copy2(origine,destination)
        recus.append({"fichier":nom,
                      "octets":destination.stat().st_size,
                      "empreinte":empreinte(destination)[:16]})

    manifeste ={"lot":horodatage, "source": str(sources),
                "recus":recus, "manquants": manquants}
    (lot/ "_manifeste.json").write_text(
        json.dumps(manifeste,ensure_ascii=False,indent=2),encoding="utf-8")
    return manifeste

def dernier_lot(zone_brute=None):
    """Renvoie le chemin du lot de fichiers le plus recents"""
    zone_brute = Path(zone_brute or config.ZONE_BRUTE)
    if not zone_brute.exists():
        return None
    lots = sorted(d for d in zone_brute.iterdir() if d.is_dir())
    return lots[-1] if lots else None