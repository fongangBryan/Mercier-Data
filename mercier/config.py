"""Configuration de la plateforme, lue dans l'environnement."""

import os
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

SOURCES = Path(os.environ.get("MERCIER_SOURCES", RACINE / "donnees_sources"))
ZONE_BRUTE = Path(os.environ.get("MERCIER_ZONE_BRUTE", RACINE / "zone_brute"))
ENTREPOT = Path(os.environ.get("MERCIER_ENTREPOT", RACINE / "entrepot.db"))
CLASSES_JAVA = Path(os.environ.get("MERCIER_JAVA", RACINE / "java"))

CLE_PAR_DEFAUT = "cle-de-developpement-a-changer"
CLE_SECRETE = os.environ.get("MERCIER_CLE_SECRETE", CLE_PAR_DEFAUT)

TAUX_TVA = float(os.environ.get("MERCIER_TVA", "0.20"))
REMISE_MAX = float(os.environ.get("MERCIER_REMISE_MAX", "20"))

ENVIRONNEMENT = os.environ.get("MERCIER_ENV", "developpement")


def resume():
    """Renvoie la configuration effective, pour journalisation au démarrage."""
    return {
        "environnement": ENVIRONNEMENT,
        "sources": str(SOURCES),
        "zone_brute": str(ZONE_BRUTE),
        "entrepot": str(ENTREPOT),
        "java": str(CLASSES_JAVA),
        "tva": TAUX_TVA,
        "remise_max": REMISE_MAX,
        "cle_par_defaut": CLE_SECRETE == CLE_PAR_DEFAUT,
    }
