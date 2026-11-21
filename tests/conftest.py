"""Fixtures partagées : chaque test a son propre entrepôt, jetable."""

import pytest

from mercier import config, entrepot, qualite, tarif_java

SOURCES = config.RACINE / "donnees_sources"


@pytest.fixture
def base(tmp_path):
    """Un entrepôt vide et jetable, propre à chaque test."""
    chemin = tmp_path / "test.db"
    entrepot.creer_schema(chemin)
    con = entrepot.connexion(chemin)
    yield con
    con.close()


@pytest.fixture
def lot_controle():
    """Les fichiers sources lus et contrôlés, prêts à charger."""
    catalogue = qualite.lire_articles(SOURCES)
    configuration = qualite.lire_boutiques(SOURCES)
    codes = {b["code"] for b in configuration["boutiques"]}
    valides, rejets = qualite.controler_ventes(SOURCES, catalogue, codes)
    return catalogue, configuration, valides, rejets


@pytest.fixture
def entrepot_charge(tmp_path, lot_controle, monkeypatch):
    """Un entrepôt rempli avec le jeu de données fourni.

    config.ENTREPOT est redirigé vers le fichier temporaire, si bien que
    l'application web elle-même travaille sur cette base et jamais sur la vraie.
    """
    chemin = tmp_path / "entrepot.db"
    monkeypatch.setattr(config, "ENTREPOT", chemin)
    catalogue, configuration, valides, rejets = lot_controle
    entrepot.charger("lot_test", catalogue, configuration, valides, rejets,
                     tarif_java.montant_en_python)
    return chemin
