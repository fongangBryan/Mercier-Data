"""Étape 7 : comptes, mots de passe, rôles et cloisonnement."""

import hashlib
import hmac
import secrets
from datetime import datetime

ITERATIONS = 200_000
ROLES = ("administrateur", "gerant")
LONGUEUR_MINIMALE = 8


def hacher(motdepasse, sel=None):
    """Renvoie le couple (sel, empreinte) d'un mot de passe."""
    sel = sel or secrets.token_hex(16)
    empreinte = hashlib.pbkdf2_hmac("sha256", motdepasse.encode("utf-8"),
                                    bytes.fromhex(sel), ITERATIONS)
    return sel, empreinte.hex()


def verifier(motdepasse, sel, empreinte_attendue):
    """Vérifie un mot de passe en temps constant."""
    _, empreinte = hacher(motdepasse, sel)
    return hmac.compare_digest(empreinte, empreinte_attendue)


def creer_utilisateur(con, identifiant, nom, motdepasse, role, boutique=None):
    """Crée un compte. Le mot de passe n'est jamais stocké, seule son empreinte."""
    if role not in ROLES:
        raise ValueError(f"Rôle inconnu : {role}")
    if len(motdepasse) < LONGUEUR_MINIMALE:
        raise ValueError(f"Le mot de passe doit faire au moins "
                         f"{LONGUEUR_MINIMALE} caractères.")
    if role == "gerant" and not boutique:
        raise ValueError("Un gérant doit être rattaché à une boutique.")
    sel, empreinte = hacher(motdepasse)
    curseur = con.execute("""
        insert into utilisateur
            (identifiant, nom, role, boutique, sel, empreinte, cree_le)
        values (?, ?, ?, ?, ?, ?, ?)
    """, (identifiant, nom, role, boutique if role == "gerant" else None,
          sel, empreinte, datetime.now().date().isoformat()))
    return curseur.lastrowid


def authentifier(con, identifiant, motdepasse):
    """Renvoie le compte si les identifiants sont bons, sinon None."""
    ligne = con.execute(
        "select * from utilisateur where identifiant = ?",
        (identifiant,)).fetchone()

    if ligne is None:
        # On hache quand même, pour que la durée de réponse ne révèle pas
        # si l'identifiant existe.
        hacher(motdepasse, secrets.token_hex(16))
        return None

    if not verifier(motdepasse, ligne["sel"], ligne["empreinte"]):
        return None

    return {"id": ligne["id"], "identifiant": ligne["identifiant"],
            "nom": ligne["nom"], "role": ligne["role"],
            "boutique": ligne["boutique"]}


def boutiques_visibles(con, compte):
    """Les boutiques que ce compte a le droit de consulter.

    C'est ici que se joue le cloisonnement : un gérant ne voit que la sienne.
    """
    if compte["role"] == "administrateur":
        return [ligne["code"] for ligne in con.execute(
            "select code from dim_boutique where active = 1 order by code")]
    return [compte["boutique"]] if compte["boutique"] else []
