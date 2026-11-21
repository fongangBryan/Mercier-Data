"""L'entrepot de données : une modélisation en étoile de notre base"""

import sqlite3
from datetime import date

from mercier import config

SCHEMA = """
pragma foreign_keys = on;

create table if not exists dim_article(
    id_dim_article integer primary key autoincrement,
    reference text not null unique,
    nom text not null,
    categorie text not null,
    taille text not null,
    couleur text not null,
    prix_achat real not null,
    prix_vente real not null
);

create table if not exists dim_boutique(
    id_dim_boutique integer primary key autoincrement,
    code text not null unique,
    ville text,
    surface_m2 integer not null default 0,
    objectif_mensuel real not null default 0,
    ouverture text,
    active integer not null default 1
);

create table if not exists dim_date(
    id_dim_date integer primary key autoincrement,
    jour text not null unique,
    semaine integer not null,
    jour_semaine integer not null,
    mois integer not null,
    annee integer not null
);

create table if not exists fait_vente(
    id integer primary key autoincrement,
    id_dim_date integer not null references dim_date(id_dim_date),
    id_dim_boutique integer not null references dim_boutique(id_dim_boutique),
    id_dim_article integer not null references dim_article(id_dim_article),
    quantite integer not null,
    remise_pourcent integer not null,
    montant_brut real not null,
    montant_net real not null,
    unique(id_dim_date, id_dim_boutique, id_dim_article,
           quantite, remise_pourcent)
);

create table if not exists rejet(
    id integer primary key autoincrement,
    lot text not null,
    numero integer not null,
    motif text not null,
    contenu text not null
);

create table if not exists chargement(
    lot text primary key,
    execute_le text not null,
    acceptees integer not null,
    rejetees integer not null,
    inserees integer not null
);

create table if not exists utilisateur(
    id integer primary key autoincrement,
    identifiant text not null unique,
    nom text not null,
    role text not null check (role in ('administrateur', 'gerant')),
    boutique text references dim_boutique(code),
    sel text not null,
    empreinte text not null,
    cree_le text not null
);

create index if not exists idx_vente_boutique on fait_vente (id_dim_boutique);
create index if not exists idx_vente_date on fait_vente (id_dim_date);
"""


def connexion(chemin=None):
    """permet d'avoir accès à notre entrepôt"""
    con = sqlite3.connect(chemin or config.ENTREPOT)
    con.row_factory = sqlite3.Row
    con.execute("pragma foreign_keys = on")
    return con


def creer_schema(chemin=None):
    """permet de creer les tables si elles n'existent pas"""
    con = connexion(chemin)
    try:
        with con:
            con.executescript(SCHEMA)
            migrer(con)
    finally:
        con.close()


def migrer(con):
    """ajoute les colonnes apparues après la création d'une base existante"""
    colonnes = {ligne["name"] for ligne in
                con.execute("pragma table_info(dim_boutique)")}
    if "surface_m2" not in colonnes:
        con.execute("alter table dim_boutique "
                    "add column surface_m2 integer not null default 0")


# ----------------------------------------------------------------------
# Correspondances entre valeur métier et identifiant technique
# ----------------------------------------------------------------------

def index_articles(con):
    """fait correspondre chaque référence à son id_dim_article"""
    return {ligne["reference"]: ligne["id_dim_article"] for ligne in
            con.execute("select id_dim_article, reference from dim_article")}


def index_boutiques(con):
    """fait correspondre chaque code de boutique à son id_dim_boutique"""
    return {ligne["code"]: ligne["id_dim_boutique"] for ligne in
            con.execute("select id_dim_boutique, code from dim_boutique")}


def index_dates(con):
    """fait correspondre chaque jour à son id_dim_date"""
    return {ligne["jour"]: ligne["id_dim_date"] for ligne in
            con.execute("select id_dim_date, jour from dim_date")}


# ----------------------------------------------------------------------
# Chargement
# ----------------------------------------------------------------------

def charger_articles(con, catalogue):
    """met à jour la dimension article sans perdre les lignes existantes"""
    con.executemany("""
        insert into dim_article
            (reference, nom, categorie, taille, couleur, prix_achat, prix_vente)
        values (?, ?, ?, ?, ?, ?, ?)
        on conflict (reference) do update set
            nom = excluded.nom,
            prix_achat = excluded.prix_achat,
            prix_vente = excluded.prix_vente
    """, [(a["reference"], a["nom"], a["categorie"], a["taille"],
           a["couleur"], a["prix_achat"], a["prix_vente"])
          for a in catalogue.values()])


def charger_boutiques(con, configuration):
    """met à jour la dimension boutique depuis le fichier de configuration"""
    con.executemany("""
        insert into dim_boutique
            (code, ville, surface_m2, objectif_mensuel, ouverture)
        values (?, ?, ?, ?, ?)
        on conflict (code) do update set
            ville = excluded.ville,
            surface_m2 = excluded.surface_m2,
            objectif_mensuel = excluded.objectif_mensuel
    """, [(b["code"], b["ville"], b.get("surface_m2", 0),
           b["objectif_mensuel"], b["ouverture"])
          for b in configuration["boutiques"]])


def charger_dates(con, ventes):
    """alimente la dimension date à partir des jours rencontrés"""
    jours = sorted({v["date"] for v in ventes})
    lignes = []
    for jour in jours:
        d = date.fromisoformat(jour)
        lignes.append((jour, d.isocalendar().week, d.isoweekday(),
                       d.month, d.year))
    con.executemany("""
        insert or ignore into dim_date
            (jour, semaine, jour_semaine, mois, annee)
        values (?, ?, ?, ?, ?)
    """, lignes)


def charger_ventes(con, ventes, catalogue, calcul_montant):
    """insère les faits et renvoie le nombre de lignes ajoutées"""
    avant = con.execute("select count(*) from fait_vente").fetchone()[0]
    articles = index_articles(con)
    boutiques = index_boutiques(con)
    dates = index_dates(con)

    lignes = []
    for vente in ventes:
        prix = catalogue[vente["reference"]]["prix_vente"]
        brut = round(prix * vente["quantite"], 2)
        net = calcul_montant(prix, vente["quantite"], vente["remise_pourcent"])
        lignes.append((dates[vente["date"]],
                       boutiques[vente["boutique"]],
                       articles[vente["reference"]],
                       vente["quantite"], vente["remise_pourcent"], brut, net))

    con.executemany("""
        insert into fait_vente
            (id_dim_date, id_dim_boutique, id_dim_article,
             quantite, remise_pourcent, montant_brut, montant_net)
        values (?, ?, ?, ?, ?, ?, ?)
        on conflict do nothing
    """, lignes)
    apres = con.execute("select count(*) from fait_vente").fetchone()[0]
    return apres - avant


def charger_rejets(con, lot, rejets):
    """trace les lignes écartées pour pouvoir les corriger à la source"""
    con.execute("delete from rejet where lot = ?", (lot,))
    con.executemany(
        "insert into rejet (lot, numero, motif, contenu) values (?, ?, ?, ?)",
        [(lot, r.numero, r.motif, r.en_dictionnaire()["contenu"])
         for r in rejets])


def charger(lot, catalogue, configuration, ventes, rejets, calcul_montant,
            chemin=None):
    """charge un lot complet dans l'entrepôt, en une seule transaction"""
    creer_schema(chemin)
    con = connexion(chemin)
    try:
        with con:                       # valide a la sortie, annule si erreur
            charger_articles(con, catalogue)
            charger_boutiques(con, configuration)
            charger_dates(con, ventes)
            inserees = charger_ventes(con, ventes, catalogue, calcul_montant)
            charger_rejets(con, lot, rejets)
            con.execute("""
                insert into chargement
                    (lot, execute_le, acceptees, rejetees, inserees)
                values (?, datetime('now'), ?, ?, ?)
                on conflict (lot) do update set
                    execute_le = excluded.execute_le,
                    inserees = excluded.inserees
            """, (lot, len(ventes), len(rejets), inserees))
        return {"lot": lot, "acceptees": len(ventes), "rejetees": len(rejets),
                "inserees": inserees}
    finally:
        con.close()