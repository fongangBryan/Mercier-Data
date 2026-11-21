"""Étape 5 : interfaçage web avec FastAPI (pages HTML et API JSON)."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from mercier import (__version__, administration, config, entrepot,
                     indicateurs, securite)

DOSSIER = Path(__file__).resolve().parent
journal = logging.getLogger("mercier")


@asynccontextmanager
async def cycle_de_vie(_app):
    """Au démarrage : vérifier la configuration et créer le schéma."""
    resume = config.resume()
    journal.warning("Configuration : %s", resume)
    if resume["cle_par_defaut"] and config.ENVIRONNEMENT == "production":
        raise SystemExit("Refus de démarrer : la clé secrète n'a pas été changée.")
    entrepot.creer_schema()
    yield


app = FastAPI(title="Mercier Data", version=__version__, lifespan=cycle_de_vie)
app.add_middleware(SessionMiddleware, secret_key=config.CLE_SECRETE,
                   session_cookie="mercier",
                   https_only=config.ENVIRONNEMENT == "production")
app.mount("/static", StaticFiles(directory=DOSSIER / "static"), name="static")
templates = Jinja2Templates(directory=DOSSIER / "templates")


# ----------------------------------------------------------------------
# Filtres de mise en forme
# ----------------------------------------------------------------------

def euros(montant, decimales=0):
    """12345.6 devient 12 346 : séparateur de milliers, virgule décimale."""
    return (f"{montant or 0:,.{decimales}f}"
            .replace(",", " ").replace(".", ","))


def nombre(valeur, decimales=1):
    """Met un nombre en forme à la française."""
    return f"{valeur or 0:.{decimales}f}".replace(".", ",")


templates.env.filters["euros"] = euros
templates.env.filters["nombre"] = nombre


# ----------------------------------------------------------------------
# Dépendances
# ----------------------------------------------------------------------

def base():
    """Ouvre une connexion par requête, et la referme à la fin."""
    con = entrepot.connexion()
    try:
        yield con
    finally:
        con.close()


def compte_courant(requete: Request):
    """Le compte en session, ou None."""
    return requete.session.get("compte")


def exige_connexion(requete: Request):
    """Dépendance des routes protégées."""
    compte = compte_courant(requete)
    if compte is None:
        raise HTTPException(status_code=401, detail="Connexion requise")
    return compte


def exige_administrateur(compte=Depends(exige_connexion)):
    """Dépendance des routes réservées à l'administrateur."""
    if compte["role"] != "administrateur":
        raise HTTPException(status_code=403, detail="Réservé à l'administrateur")
    return compte


def redirection(chemin, **parametres):
    """Redirection 303 (envoyer, rediriger, afficher), paramètres encodés."""
    if parametres:
        chemin = f"{chemin}?{urlencode(parametres)}"
    return RedirectResponse(chemin, status_code=303)


def page(requete, nom, contexte, statut=200):
    """Rend un template en y ajoutant le compte et la page active."""
    contexte.setdefault("compte", compte_courant(requete))
    return templates.TemplateResponse(requete, nom, contexte,
                                      status_code=statut)


# ----------------------------------------------------------------------
# Connexion
# ----------------------------------------------------------------------

@app.get("/connexion", response_class=HTMLResponse, tags=["pages"])
def formulaire_connexion(requete: Request, erreur: str = ""):
    if compte_courant(requete):
        return redirection("/")
    return page(requete, "connexion.html", {"erreur": bool(erreur)})


@app.post("/connexion", tags=["pages"])
def valider_connexion(requete: Request, identifiant: str = Form(...),
                      motdepasse: str = Form(...), con=Depends(base)):
    compte = securite.authentifier(con, identifiant.strip().lower(), motdepasse)
    if compte is None:
        journal.warning("Échec de connexion pour %r", identifiant)
        return redirection("/connexion", erreur=1)
    requete.session.clear()
    requete.session["compte"] = compte
    return redirection("/")


@app.get("/deconnexion", tags=["pages"])
def deconnexion(requete: Request):
    requete.session.clear()
    return redirection("/connexion")


# ----------------------------------------------------------------------
# Tableau de bord
# ----------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse, tags=["pages"])
def tableau_de_bord(requete: Request, boutique: str = "", con=Depends(base)):
    """Le tableau de bord, limité aux boutiques que le compte peut voir."""
    compte = compte_courant(requete)
    if compte is None:
        return redirection("/connexion")

    visibles = securite.boutiques_visibles(con, compte)

    # Le filtre ne peut jamais élargir le périmètre autorisé.
    perimetre = [boutique] if boutique in visibles else visibles
    if boutique not in visibles:
        boutique = ""

    synthese = indicateurs.synthese(con, perimetre)
    par_boutique = indicateurs.par_boutique(con, perimetre)
    objectif = sum(b["objectif"] or 0 for b in par_boutique)
    taux = (round(100 * synthese["chiffre_affaires"] / objectif)
            if objectif else 0)

    return page(requete, "tableau.html", {
        "actif": "tableau",
        "synthese": synthese,
        "boutiques": par_boutique,
        "categories": indicateurs.par_categorie(con, perimetre),
        "meilleures": indicateurs.meilleures_ventes(con, perimetre),
        "semaines": indicateurs.evolution(con, perimetre),
        "objectif": objectif,
        "taux_objectif": taux,
        "visibles": visibles,
        "filtre": boutique,
        "lot": indicateurs.qualite_dernier_lot(con),
    })


# ----------------------------------------------------------------------
# Administration
# ----------------------------------------------------------------------

@app.get("/administration", response_class=HTMLResponse, tags=["administration"])
def page_administration(requete: Request, message: str = "", erreur: str = "",
                        con=Depends(base)):
    compte = compte_courant(requete)
    if compte is None:
        return redirection("/connexion")
    if compte["role"] != "administrateur":
        return page(requete, "erreur.html", {
            "code": 403, "message": "Cette page est réservée à l'administrateur."
        }, statut=403)
    return page(requete, "administration.html", {
        "actif": "administration",
        "boutiques": administration.liste_boutiques(con),
        "comptes": administration.liste_comptes(con),
        "lot": indicateurs.qualite_dernier_lot(con),
        "message": message,
        "erreur": erreur,
    })


@app.post("/administration/boutique", tags=["administration"])
def creation_boutique(code: str = Form(...), ville: str = Form(""),
                      surface_m2: int = Form(0),
                      objectif_mensuel: float = Form(0),
                      compte=Depends(exige_administrateur),
                      con=Depends(base)):
    code = code.strip().lower()
    try:
        with con:
            administration.creer_boutique(con, code, ville.strip(),
                                          surface_m2, objectif_mensuel)
    except ValueError as erreur:
        return redirection("/administration", erreur=str(erreur))
    return redirection("/administration", message=f"Boutique {code} créée.")


@app.post("/administration/gerant", tags=["administration"])
def nomination_gerant(boutique: str = Form(...), identifiant: str = Form(...),
                      nom: str = Form(...), motdepasse: str = Form(...),
                      compte=Depends(exige_administrateur),
                      con=Depends(base)):
    identifiant = identifiant.strip().lower()
    try:
        with con:
            administration.nommer_gerant(con, boutique, identifiant, nom,
                                         motdepasse)
    except ValueError as erreur:
        return redirection("/administration", erreur=str(erreur))
    return redirection("/administration",
                       message=f"{nom.strip()} est gérant de {boutique}.")


@app.post("/administration/boutique/{code}/etat", tags=["administration"])
def changer_etat_boutique(code: str, active: int = Form(...),
                          compte=Depends(exige_administrateur),
                          con=Depends(base)):
    with con:
        if active:
            administration.reactiver_boutique(con, code)
        else:
            administration.desactiver_boutique(con, code)
    etat = "réactivée" if active else "désactivée"
    return redirection("/administration", message=f"Boutique {code} {etat}.")


# ----------------------------------------------------------------------
# API JSON, documentée automatiquement sur /docs
# ----------------------------------------------------------------------

@app.get("/api/synthese", tags=["api"])
def api_synthese(compte=Depends(exige_connexion), con=Depends(base)):
    """Ventes, pièces, chiffre d'affaires, panier moyen et remises."""
    return indicateurs.synthese(con, securite.boutiques_visibles(con, compte))


@app.get("/api/boutiques", tags=["api"])
def api_boutiques(compte=Depends(exige_connexion), con=Depends(base)):
    """Chiffre d'affaires par boutique, confronté à l'objectif."""
    return indicateurs.par_boutique(con, securite.boutiques_visibles(con, compte))


@app.get("/api/categories", tags=["api"])
def api_categories(compte=Depends(exige_connexion), con=Depends(base)):
    """Chiffre d'affaires et marge par catégorie."""
    return indicateurs.par_categorie(con, securite.boutiques_visibles(con, compte))


@app.get("/api/meilleures", tags=["api"])
def api_meilleures(limite: int = 5, compte=Depends(exige_connexion),
                   con=Depends(base)):
    """Les références qui rapportent le plus."""
    return indicateurs.meilleures_ventes(
        con, securite.boutiques_visibles(con, compte), max(1, min(limite, 50)))


@app.get("/api/evolution", tags=["api"])
def api_evolution(compte=Depends(exige_connexion), con=Depends(base)):
    """Chiffre d'affaires semaine par semaine."""
    return indicateurs.evolution(con, securite.boutiques_visibles(con, compte))


@app.get("/api/qualite", tags=["api"])
def api_qualite(compte=Depends(exige_administrateur), con=Depends(base)):
    """État du dernier chargement. Réservé à l'administrateur."""
    return indicateurs.qualite_dernier_lot(con) or {}


@app.get("/sante", tags=["exploitation"])
def sante(con=Depends(base)):
    """Point de contrôle, appelé par la supervision. Sans authentification."""
    faits = con.execute("select count(*) from fait_vente").fetchone()[0]
    return {"etat": "ok", "version": __version__, "faits": faits}
