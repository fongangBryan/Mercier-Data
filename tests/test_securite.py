"""Étapes 6 et 7 : administration, mots de passe et cloisonnement."""

import pytest

from mercier import administration, securite


def test_deux_comptes_meme_mot_de_passe_ont_des_empreintes_differentes(base):
    with base:
        securite.creer_utilisateur(base, "a", "A", "motdepasse1", "administrateur")
        securite.creer_utilisateur(base, "b", "B", "motdepasse1", "administrateur")
    empreintes = [ligne["empreinte"]
                  for ligne in base.execute("select empreinte from utilisateur")]
    assert empreintes[0] != empreintes[1]


def test_le_mot_de_passe_n_est_jamais_stocke(base):
    with base:
        securite.creer_utilisateur(base, "a", "A", "motdepasse1", "administrateur")
    ligne = base.execute("select * from utilisateur").fetchone()
    assert "motdepasse1" not in tuple(str(v) for v in ligne)


def test_authentification(base):
    with base:
        securite.creer_utilisateur(base, "claire", "Claire", "motdepasse1",
                                   "administrateur")
    assert securite.authentifier(base, "claire", "motdepasse1")["role"] == "administrateur"
    assert securite.authentifier(base, "claire", "mauvais") is None
    assert securite.authentifier(base, "inconnu", "motdepasse1") is None


def test_cloisonnement(base):
    with base:
        administration.creer_boutique(base, "nantes-graslin", "Nantes", 70, 2600)
        administration.creer_boutique(base, "brest-siam", "Brest", 50, 1800)
        administration.nommer_gerant(base, "nantes-graslin", "sophie",
                                     "Sophie Garnier", "motdepasse1")
        securite.creer_utilisateur(base, "claire", "Claire", "motdepasse1",
                                   "administrateur")
    gerante = securite.authentifier(base, "sophie", "motdepasse1")
    admin = securite.authentifier(base, "claire", "motdepasse1")
    assert securite.boutiques_visibles(base, gerante) == ["nantes-graslin"]
    assert len(securite.boutiques_visibles(base, admin)) == 2


@pytest.mark.parametrize("code", ["Paris", "ab", "1paris", "paris marais", "a" * 31])
def test_code_de_boutique_invalide(base, code):
    with pytest.raises(ValueError):
        administration.creer_boutique(base, code, "X", 10, 100)


def test_boutique_en_double_refusee(base):
    with base:
        administration.creer_boutique(base, "nantes-graslin", "Nantes", 70, 2600)
    with pytest.raises(ValueError, match="existe déjà"):
        administration.creer_boutique(base, "nantes-graslin", "Nantes", 70, 2600)


def test_desactiver_conserve_l_historique(base):
    with base:
        administration.creer_boutique(base, "nantes-graslin", "Nantes", 70, 2600)
        administration.desactiver_boutique(base, "nantes-graslin")
    admin = {"role": "administrateur", "boutique": None}
    assert securite.boutiques_visibles(base, admin) == []
    assert base.execute("select count(*) from dim_boutique").fetchone()[0] == 1
