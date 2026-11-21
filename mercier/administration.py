"""Étape 6 : création des boutiques et nomination des gérants.

La validation est ici, dans le module métier, et non dans la page web :
une règle placée dans le formulaire serait contournée par un appel à l'API.
"""

import re
from datetime import date

from mercier import securite

MOTIF_CODE = re.compile(r"^[a-z][a-z0-9-]{2,29}$")
MOTIF_IDENTIFIANT = re.compile(r"^[a-z][a-z0-9._-]{1,29}$")


def valider_code(code):
    """Un code de boutique : minuscules, chiffres et traits d'union."""
    if not MOTIF_CODE.match(code):
        raise ValueError(
            "Code invalide : minuscules, chiffres et traits d'union, "
            "de 3 à 30 caractères, commençant par une lettre.")
    return code


def creer_boutique(con, code, ville, surface_m2, objectif_mensuel,
                   ouverture=None):
    """Crée une boutique dans la dimension. Renvoie son code."""
    valider_code(code)
    if int(surface_m2) < 0:
        raise ValueError("La surface ne peut pas être négative.")
    if float(objectif_mensuel) < 0:
        raise ValueError("L'objectif ne peut pas être négatif.")
    if con.execute("select 1 from dim_boutique where code = ?",
                   (code,)).fetchone():
        raise ValueError(f"La boutique {code} existe déjà.")

    con.execute("""
        insert into dim_boutique
            (code, ville, surface_m2, objectif_mensuel, ouverture, active)
        values (?, ?, ?, ?, ?, 1)
    """, (code, ville or None, int(surface_m2), float(objectif_mensuel),
          ouverture or date.today().isoformat()))
    return code


def nommer_gerant(con, boutique, identifiant, nom, motdepasse):
    """Crée un compte gérant rattaché à une boutique existante."""
    if not MOTIF_IDENTIFIANT.match(identifiant):
        raise ValueError("Identifiant invalide : minuscules, chiffres, "
                         "point, tiret ou soulignement, 2 à 30 caractères.")
    if not nom.strip():
        raise ValueError("Le nom complet est obligatoire.")
    if not con.execute("select 1 from dim_boutique where code = ?",
                       (boutique,)).fetchone():
        raise ValueError(f"Boutique inconnue : {boutique}")
    if con.execute("select 1 from utilisateur where identifiant = ?",
                   (identifiant,)).fetchone():
        raise ValueError(f"L'identifiant {identifiant} est déjà pris.")
    return securite.creer_utilisateur(con, identifiant, nom.strip(),
                                      motdepasse, "gerant", boutique)


def desactiver_boutique(con, code):
    """Rend une boutique inactive sans effacer son historique de ventes."""
    con.execute("update dim_boutique set active = 0 where code = ?", (code,))


def reactiver_boutique(con, code):
    """Remet une boutique désactivée dans le périmètre."""
    con.execute("update dim_boutique set active = 1 where code = ?", (code,))


def liste_boutiques(con):
    """Toutes les boutiques, actives ou non, avec leur CA et leur gérant."""
    return [dict(ligne) for ligne in con.execute("""
        select b.code, b.ville, b.surface_m2, b.objectif_mensuel, b.active,
               coalesce(round(sum(v.montant_net), 2), 0) as chiffre_affaires,
               (select group_concat(u.nom, ', ') from utilisateur as u
                 where u.boutique = b.code) as gerant
        from dim_boutique as b
        left join fait_vente as v on v.id_dim_boutique = b.id_dim_boutique
        group by b.id_dim_boutique
        order by b.active desc, chiffre_affaires desc
    """)]


def liste_comptes(con):
    """Les comptes, sans jamais renvoyer le sel ni l'empreinte."""
    return [dict(ligne) for ligne in con.execute("""
        select identifiant, nom, role, boutique, cree_le
        from utilisateur order by role, identifiant
    """)]
