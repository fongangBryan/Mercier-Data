"""Requêtes de restitution, toutes cloisonnées par une liste de boutiques.

Le filtre est appliqué dans la requête SQL et jamais à l'affichage :
les données d'une boutique non autorisée ne sortent pas de la base.
"""

import json
from datetime import date

MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août",
        "sept.", "oct.", "nov.", "déc."]


def _filtre(boutiques):
    """Fabrique la clause IN et ses paramètres : la forme, jamais les données."""
    marques = ", ".join("?" for _ in boutiques)
    return f"b.code in ({marques})", list(boutiques)


def synthese(con, boutiques):
    """Ventes, pièces, chiffre d'affaires, panier moyen et remises."""
    if not boutiques:
        return {"ventes": 0, "pieces": 0, "chiffre_affaires": 0.0,
                "panier_moyen": 0.0, "remises": 0.0, "semaines": 0}
    clause, params = _filtre(boutiques)
    ligne = con.execute(f"""
        select count(*) as ventes,
            coalesce(sum(v.quantite), 0) as pieces,
            coalesce(round(sum(v.montant_net), 2), 0) as chiffre_affaires,
            coalesce(round(avg(v.montant_net), 2), 0) as panier_moyen,
            coalesce(round(sum(v.montant_brut - v.montant_net), 2), 0) as remises,
            count(distinct d.semaine) as semaines
        from fait_vente as v
        join dim_boutique as b on b.id_dim_boutique = v.id_dim_boutique
        join dim_date as d on d.id_dim_date = v.id_dim_date
        where {clause}
    """, params).fetchone()
    return dict(ligne)


def par_boutique(con, boutiques):
    """CA par boutique confronté à l'objectif, y compris sans vente."""
    if not boutiques:
        return []
    clause, params = _filtre(boutiques)
    lignes = [dict(ligne) for ligne in con.execute(f"""
        select
            b.code as boutique,
            b.ville,
            count(v.id) as ventes,
            coalesce(round(sum(v.montant_net), 2), 0) as chiffre_affaires,
            b.objectif_mensuel as objectif,
            round(100.0 * coalesce(sum(v.montant_net), 0)
                  / nullif(b.objectif_mensuel, 0), 1) as taux
        from dim_boutique as b
        left join fait_vente as v on v.id_dim_boutique = b.id_dim_boutique
        where {clause}
        group by b.id_dim_boutique
        order by taux desc, chiffre_affaires desc
    """, params)]
    for b in lignes:
        b["libelle"] = b["ville"] or "Vente en ligne"
        b["ecart"] = round(b["chiffre_affaires"] - (b["objectif"] or 0), 2)
    return lignes


def par_categorie(con, boutiques):
    """CA et marge par catégorie d'article."""
    if not boutiques:
        return []
    clause, params = _filtre(boutiques)
    return [dict(ligne) for ligne in con.execute(f"""
        select
            a.categorie as categorie,
            sum(v.quantite) as pieces,
            round(sum(v.montant_net), 2) as chiffre_affaires,
            round(sum(v.montant_net - a.prix_achat * v.quantite), 2) as marge
        from fait_vente as v
        join dim_article as a on a.id_dim_article = v.id_dim_article
        join dim_boutique as b on b.id_dim_boutique = v.id_dim_boutique
        where {clause}
        group by categorie
        order by chiffre_affaires desc
    """, params)]


def meilleures_ventes(con, boutiques, limite=5):
    """Les références qui rapportent le plus."""
    if not boutiques:
        return []
    clause, params = _filtre(boutiques)
    return [dict(ligne) for ligne in con.execute(f"""
        select
            a.reference, a.nom, a.taille,
            sum(v.quantite) as pieces,
            round(sum(v.montant_net), 2) as chiffre_affaires
        from fait_vente as v
        join dim_article as a on a.id_dim_article = v.id_dim_article
        join dim_boutique as b on b.id_dim_boutique = v.id_dim_boutique
        where {clause}
        group by a.id_dim_article
        order by chiffre_affaires desc
        limit ?
    """, params + [limite])]


def _periode(debut, fin):
    """'2026-10-05', '2026-10-11' devient '5 au 11 oct.'"""
    d, f = date.fromisoformat(debut), date.fromisoformat(fin)
    if d.month == f.month:
        return f"{d.day} au {f.day} {MOIS[f.month - 1]}"
    return f"{d.day} {MOIS[d.month - 1]} au {f.day} {MOIS[f.month - 1]}"


def evolution(con, boutiques):
    """CA par semaine, avec la variation par rapport à la semaine précédente."""
    if not boutiques:
        return []
    clause, params = _filtre(boutiques)
    semaines = [dict(ligne) for ligne in con.execute(f"""
        select d.annee, d.semaine,
               min(d.jour) as debut, max(d.jour) as fin,
               round(sum(v.montant_net), 2) as chiffre_affaires
        from fait_vente as v
        join dim_date as d on d.id_dim_date = v.id_dim_date
        join dim_boutique as b on b.id_dim_boutique = v.id_dim_boutique
        where {clause}
        group by d.annee, d.semaine
        order by d.annee, d.semaine
    """, params)]

    maximum = max((s["chiffre_affaires"] for s in semaines), default=0) or 1
    precedent = None
    for s in semaines:
        s["periode"] = _periode(s["debut"], s["fin"])
        s["hauteur"] = round(100 * s["chiffre_affaires"] / maximum)
        s["variation"] = (round(100 * (s["chiffre_affaires"] - precedent)
                                / precedent) if precedent else None)
        precedent = s["chiffre_affaires"]
    return semaines


def qualite_dernier_lot(con):
    """Le dernier chargement et ses rejets, ou None si rien n'a été chargé."""
    lot = con.execute("""
        select lot, execute_le, acceptees, rejetees, inserees
        from chargement order by execute_le desc, lot desc limit 1
    """).fetchone()
    if lot is None:
        return None
    resultat = dict(lot)
    resultat["rejets"] = rejets_lot(con, lot["lot"])
    motifs = {}
    for rejet in resultat["rejets"]:
        motifs[rejet["motif"]] = motifs.get(rejet["motif"], 0) + 1
    resultat["motifs"] = motifs
    return resultat


def rejets_lot(con, lot):
    """Les lignes écartées d'un lot, avec leur contenu d'origine."""
    lignes = []
    for ligne in con.execute(
            "select numero, motif, contenu from rejet where lot = ? "
            "order by numero", (lot,)):
        rejet = dict(ligne)
        rejet["contenu"] = json.loads(rejet["contenu"])
        lignes.append(rejet)
    return lignes
