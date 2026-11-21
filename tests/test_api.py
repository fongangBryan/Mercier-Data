"""Étape 5 et section 8.6 : l'application web, vue de l'extérieur.

Le dernier test répond à l'exercice 12.5.4 : un gérant ne peut obtenir les
données d'une autre boutique par aucun chemin.
"""

import pytest
from fastapi.testclient import TestClient

from mercier import administration, entrepot, securite
from mercier.api import app


@pytest.fixture
def client(entrepot_charge):
    con = entrepot.connexion()
    with con:
        securite.creer_utilisateur(con, "claire", "Claire Dubois",
                                   "motdepasse1", "administrateur")
        administration.nommer_gerant(con, "lyon-presquile", "julie",
                                     "Julie Leroy", "motdepasse1")
    con.close()
    with TestClient(app) as client:
        yield client


def connecter(client, identifiant):
    return client.post("/connexion", follow_redirects=False,
                       data={"identifiant": identifiant,
                             "motdepasse": "motdepasse1"})


def test_sante_sans_compte(client):
    reponse = client.get("/sante")
    assert reponse.status_code == 200
    assert reponse.json()["faits"] == 122


def test_pages_protegees_sans_compte(client):
    accueil = client.get("/", follow_redirects=False)
    assert accueil.status_code == 303
    assert accueil.headers["location"] == "/connexion"
    assert client.get("/api/synthese").status_code == 401


def test_mauvais_mot_de_passe(client):
    reponse = client.post("/connexion", follow_redirects=False,
                          data={"identifiant": "julie", "motdepasse": "faux"})
    assert reponse.headers["location"] == "/connexion?erreur=1"


def test_administratrice(client):
    assert connecter(client, "claire").headers["location"] == "/"
    assert client.get("/").status_code == 200
    synthese = client.get("/api/synthese").json()
    assert synthese["ventes"] == 122
    assert synthese["chiffre_affaires"] == pytest.approx(11727.69)
    assert client.get("/administration").status_code == 200
    assert client.get("/api/qualite").json()["rejetees"] == 7


def test_creation_boutique_par_formulaire(client):
    connecter(client, "claire")
    reponse = client.post("/administration/boutique", follow_redirects=False,
                          data={"code": "nantes-graslin", "ville": "Nantes",
                                "surface_m2": 60, "objectif_mensuel": 2500})
    assert "message=Boutique+nantes-graslin" in reponse.headers["location"]
    reponse = client.post("/administration/boutique", follow_redirects=False,
                          data={"code": "Code Invalide"})
    assert "erreur=Code+invalide" in reponse.headers["location"]


def test_gerante_cloisonnee_par_tous_les_chemins(client):
    connecter(client, "julie")

    # l'API ne renvoie que Lyon
    synthese = client.get("/api/synthese").json()
    assert synthese["ventes"] == 31
    boutiques = [b["boutique"] for b in client.get("/api/boutiques").json()]
    assert boutiques == ["lyon-presquile"]

    # le paramètre d'adresse ne peut pas élargir le périmètre
    page = client.get("/?boutique=paris-marais").text
    assert "Boutique lyon-presquile" in page
    assert "paris-marais" not in page

    # l'administration et la qualité lui sont fermées
    assert client.get("/administration").status_code == 403
    assert client.get("/api/qualite").status_code == 403
    assert client.post("/administration/boutique",
                       data={"code": "pirate-1"}).status_code == 403
