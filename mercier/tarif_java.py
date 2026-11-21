"""le moteur de remises, ecrit en Java."""

import subprocess
from functools import lru_cache

from mercier import config

_JVM = None


# --------------------------
# Voie 1 : le sous-processus
# --------------------------

def montant_par_sous_processus(prix, quantite, remise):
    """Appelle la classe Java en lancant une JVM, via la ligne de commande."""
    resultat = subprocess.run(
        ["java", "-cp", str(config.CLASSES_JAVA), "Tarif",
         str(prix), str(quantite), str(remise)],
        capture_output=True, text=True, check=True)
    return float(resultat.stdout.strip().splitlines()[-1])


# ----------------------------------------------------------------------
# Voie 2 : JPype. Une seule JVM, partagee par tout le programme.
# ----------------------------------------------------------------------

def demarrer_jvm():
    """Demarre la JVM une fois et renvoie la classe Tarif."""
    global _JVM
    if _JVM is None:
        import jpype
        if not jpype.isJVMStarted():
            jpype.startJVM(classpath=[str(config.CLASSES_JAVA)])
        _JVM = jpype.JClass("Tarif")
    return _JVM


def montant_par_jpype(prix, quantite, remise):
    """Appelle la methode Java directement, sans quitter le processus."""
    return float(demarrer_jvm().montantLigne(prix, quantite, remise))


# ----------------------------------------------------------------------
# Voie 3 : le repli en Python, si aucune JVM n'est disponible.
# ----------------------------------------------------------------------

def montant_en_python(prix, quantite, remise):
    """Reimplementation de secours lorsque java n'est pas installé"""
    return round(prix * quantite * (1 - remise / 100), 2)


@lru_cache(maxsize=1)
def moteur_disponible():
    """Choisit la meilleure voie disponible sur cette machine."""
    try:
        import jpype
        demarrer_jvm()
        return "jpype"
    except Exception:
        pass
    try:
        subprocess.run(["java", "-version"], capture_output=True, check=True)
        return "sous-processus"
    except Exception:
        return "python"


def montant_ligne(prix, quantite, remise=0):
    """Point d'entree unique du reste de la plateforme."""
    voie = moteur_disponible()
    if voie == "jpype":
        return montant_par_jpype(prix, quantite, remise)
    if voie == "sous-processus":
        return montant_par_sous_processus(prix, quantite, remise)
    return montant_en_python(prix, quantite, remise)