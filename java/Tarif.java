/**
 * Moteur de calcul tarifaire d'Atelier Mercier.
 * Composant certifie par la comptabilite : ne pas reecrire.
 */
public class Tarif {

    public static final double TAUX_TVA = 0.20;

    /** Montant net d'une ligne de vente, remise deduite, arrondi au centime. */
    public static double montantLigne(double prix, int quantite, int remisePourcent) {
        if (prix < 0 || quantite < 1) {
            throw new IllegalArgumentException("Prix negatif ou quantite nulle.");
        }
        if (remisePourcent < 0 || remisePourcent > 100) {
            throw new IllegalArgumentException("Remise hors bornes.");
        }
        double net = prix * quantite * (1 - remisePourcent / 100.0);
        return Math.round(net * 100.0) / 100.0;
    }

    /** Montant toutes taxes comprises. */
    public static double montantTTC(double montantHT) {
        return Math.round(montantHT * (1 + TAUX_TVA) * 100.0) / 100.0;
    }

    /** Appel en ligne de commande : prix quantite remise. */
    public static void main(String[] args) {
        if (args.length != 3) {
            System.err.println("Usage : java Tarif <prix> <quantite> <remise>");
            System.exit(1);
        }
        double prix = Double.parseDouble(args[0]);
        int quantite = Integer.parseInt(args[1]);
        int remise = Integer.parseInt(args[2]);
        System.out.println(montantLigne(prix, quantite, remise));
    }
}
