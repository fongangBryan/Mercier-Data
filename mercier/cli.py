"""Ligne de commande de la plateforme.

    python -m mercier.cli config
    python -m mercier.cli ingerer
    python -m mercier.cli controler [lot]
    python -m mercier.cli chaine
    python -m mercier.cli rejouer <lot>
    python -m mercier.cli creer-admin <identifiant> "<nom complet>"
"""

import argparse
import getpass
import json
import sys

from mercier import config, entrepot, ingestion, qualite, securite, tarif_java


def _chemin_lot(nom=None):
    """Le dossier d'un lot donné, ou du plus récent."""
    if nom:
        lot = config.ZONE_BRUTE / nom
        if not lot.is_dir():
            raise SystemExit(f"Lot introuvable : {lot}")
        return lot
    lot = ingestion.dernier_lot()
    if lot is None:
        raise SystemExit("Aucun lot dans la zone brute : lancez d'abord 'ingerer'.")
    return lot


def _controler(lot):
    """Lit et contrôle un lot. Renvoie tout ce qu'il faut pour le charger."""
    catalogue = qualite.lire_articles(lot)
    configuration = qualite.lire_boutiques(lot)
    codes = {b["code"] for b in configuration["boutiques"]}
    valides, rejets = qualite.controler_ventes(lot, catalogue, codes)
    return catalogue, configuration, valides, rejets


def _charger(lot):
    """Contrôle puis charge un lot déjà présent dans la zone brute."""
    catalogue, configuration, valides, rejets = _controler(lot)
    bilan = qualite.rapport(valides, rejets)
    print(f"Contrôle : {bilan['acceptees']} acceptées, {bilan['rejetees']} "
          f"rejetées ({bilan['taux_acceptation']} pour cent)")
    print(f"Moteur tarifaire : {tarif_java.moteur_disponible()}")
    resultat = entrepot.charger(lot.name, catalogue, configuration, valides,
                                rejets, tarif_java.montant_ligne)
    print(f"Chargement : {resultat['inserees']} nouvelles lignes de faits")
    return resultat


def commande_config(_args):
    print(json.dumps(config.resume(), ensure_ascii=False, indent=2))


def commande_ingerer(_args):
    manifeste = ingestion.ingerer()
    print(f"Lot {manifeste['lot']} : {len(manifeste['recus'])} fichiers reçus")
    for fichier in manifeste["manquants"]:
        print(f"  manquant : {fichier}")
    return manifeste


def commande_controler(args):
    lot = _chemin_lot(args.lot)
    _, _, valides, rejets = _controler(lot)
    print(json.dumps(qualite.rapport(valides, rejets), ensure_ascii=False,
                     indent=2))
    for rejet in rejets:
        print(rejet)


def commande_chaine(_args):
    manifeste = commande_ingerer(_args)
    if manifeste["manquants"]:
        raise SystemExit("Chargement annulé : des fichiers sont manquants.")
    _charger(config.ZONE_BRUTE / manifeste["lot"])


def commande_rejouer(args):
    lot = _chemin_lot(args.lot)
    print(f"Lot {lot.name} : rechargement sans nouvelle ingestion")
    _charger(lot)


def commande_creer_admin(args):
    motdepasse = args.motdepasse or getpass.getpass("Mot de passe : ")
    entrepot.creer_schema()
    con = entrepot.connexion()
    try:
        with con:
            securite.creer_utilisateur(con, args.identifiant, args.nom,
                                       motdepasse, "administrateur")
    except ValueError as erreur:
        raise SystemExit(str(erreur))
    except Exception as erreur:
        if "UNIQUE" in str(erreur):
            raise SystemExit(f"L'identifiant {args.identifiant} est déjà pris.")
        raise
    finally:
        con.close()
    print(f"Administrateur {args.identifiant} créé.")


def analyseur():
    parseur = argparse.ArgumentParser(prog="python -m mercier.cli",
                                      description="Plateforme Mercier Data")
    sous = parseur.add_subparsers(dest="commande", required=True)

    sous.add_parser("config", help="affiche la configuration effective") \
        .set_defaults(fonction=commande_config)
    sous.add_parser("ingerer", help="copie les fichiers reçus dans un lot") \
        .set_defaults(fonction=commande_ingerer)

    p = sous.add_parser("controler", help="contrôle un lot sans le charger")
    p.add_argument("lot", nargs="?", help="nom du lot (le plus récent par défaut)")
    p.set_defaults(fonction=commande_controler)

    sous.add_parser("chaine", help="ingestion, contrôle et chargement") \
        .set_defaults(fonction=commande_chaine)

    p = sous.add_parser("rejouer", help="recharge un lot déjà ingéré")
    p.add_argument("lot", help="nom du lot, par exemple 20261118_200000")
    p.set_defaults(fonction=commande_rejouer)

    p = sous.add_parser("creer-admin", help="crée un compte administrateur")
    p.add_argument("identifiant")
    p.add_argument("nom")
    p.add_argument("--motdepasse", help="sinon demandé au clavier")
    p.set_defaults(fonction=commande_creer_admin)
    return parseur


def main(argv=None):
    args = analyseur().parse_args(argv)
    args.fonction(args)


if __name__ == "__main__":
    # La console Windows n'affiche pas toujours les accents sans cela.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
