"""Étapes 1 à 4 : ingestion, qualité, entrepôt et moteur tarifaire."""

from mercier import entrepot, ingestion, qualite, tarif_java
from tests.conftest import SOURCES


def test_ingestion_copie_les_quatre_fichiers(tmp_path):
    manifeste = ingestion.ingerer(SOURCES, tmp_path, "20261118_200000")
    assert manifeste["manquants"] == []
    assert len(manifeste["recus"]) == 4
    assert (tmp_path / "20261118_200000" / "_manifeste.json").exists()


def test_empreinte_identique_pour_un_fichier_identique(tmp_path):
    ingestion.ingerer(SOURCES, tmp_path, "a")
    ingestion.ingerer(SOURCES, tmp_path, "b")
    nom = "ventes_octobre.csv"
    assert (ingestion.empreinte(tmp_path / "a" / nom)
            == ingestion.empreinte(tmp_path / "b" / nom))


def test_les_sept_rejets_attendus(lot_controle):
    _, _, valides, rejets = lot_controle
    bilan = qualite.rapport(valides, rejets)
    assert (bilan["acceptees"], bilan["rejetees"]) == (122, 7)
    assert [r.numero for r in rejets] == [89, 125, 126, 127, 128, 129, 130]
    assert len(bilan["motifs"]) == 7       # un motif différent par ligne


def test_chargement_idempotent(tmp_path, lot_controle):
    catalogue, configuration, valides, rejets = lot_controle
    chemin = tmp_path / "entrepot.db"
    premier = entrepot.charger("lot1", catalogue, configuration, valides,
                               rejets, tarif_java.montant_en_python, chemin)
    second = entrepot.charger("lot2", catalogue, configuration, valides,
                              rejets, tarif_java.montant_en_python, chemin)
    assert premier["inserees"] == 122
    assert second["inserees"] == 0


def test_les_voies_tarifaires_concordent():
    attendu = tarif_java.montant_en_python(19.90, 2, 10)
    assert attendu == 35.82
    assert tarif_java.montant_ligne(19.90, 2, 10) == attendu
