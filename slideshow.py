import sys  # Module pour gérer les arguments en ligne de commande
import gurobipy as gp  # Importation de la bibliothèque Gurobi pour l'optimisation
from gurobipy import GRB  # Importation des constantes utilisées dans Gurobi


def main():
    """Fonction principale qui exécute le processus d'optimisation du diaporama."""
    if len(sys.argv) != 2:  # Vérifie si un seul argument (le chemin du dataset) est fourni
        print("Usage: python slideshow.py <dataset_path>")  # Affiche un message d'utilisation en cas d'erreur
        return  # Arrête l'exécution du programme

    dataset_path = sys.argv[1]  # Récupère le chemin du fichier de données depuis les arguments de la ligne de commande

    # Étape 1 : Lire le dataset
    data = read_dataset(dataset_path)  # Appelle la fonction pour lire et analyser le dataset

    # Étape 2 : Résoudre le problème d'optimisation
    solution, score = solve(data)  # Résout le problème d'optimisation en utilisant Gurobi et obtient le score

    # Affichage de la valeur de la solution trouvée
    print(f"Score de la solution trouvée : {score}")

    # Étape 3 : Écrire la solution dans un fichier de sortie
    write_solution(solution, "slideshow.sol")  # Sauvegarde la solution dans un fichier de sortie


def read_dataset(file_path):
    """Lit le fichier de dataset et extrait les données sous une forme exploitable."""
    data = []  # Initialise une liste vide pour stocker les informations des photos
    with open(file_path, 'r') as file:  # Ouvre le fichier dataset en mode lecture
        lines = file.readlines()  # Lit toutes les lignes du fichier et les stocke dans une liste
        n_photos = int(lines[0].strip())  # La première ligne contient le nombre total de photos
        for i in range(1, n_photos + 1):  # Boucle sur chaque ligne correspondant à une photo
            parts = lines[i].strip().split()  # Découpe la ligne en éléments distincts (orientation, tags)
            orientation = parts[
                0]  # Premier élément : l'orientation de la photo ('H' pour horizontale, 'V' pour verticale)
            tags = set(parts[
                       2:])  # Extrait les tags sous forme d'un ensemble (set) pour éviter les doublons et faciliter la recherche
            data.append(
                (i - 1, orientation, tags))  # Ajoute la photo sous forme de tuple (ID, orientation, ensemble de tags)
    return data  # Retourne la liste des photos analysées


def solve(data):
    """Résout le problème d'optimisation à l'aide de Gurobi."""
    model = gp.Model("Slideshow Optimization")  # Crée un modèle d'optimisation Gurobi

    slides = []  # Liste pour stocker les diapositives générées
    used_photos = set()  # Ensemble des photos déjà utilisées

    # Création des diapositives
    for photo in data:
        if photo[1] == 'H':  # Si la photo est horizontale
            slides.append([photo[0]])  # Ajoute une diapositive avec une seule photo
            used_photos.add(photo[0])

    vertical_photos = [p for p in data if p[1] == 'V' and p[0] not in used_photos]
    while len(vertical_photos) > 1:
        p1 = vertical_photos.pop(0)
        p2 = vertical_photos.pop(-1)
        slides.append([p1[0], p2[0]])
        used_photos.add(p1[0])
        used_photos.add(p2[0])

    # Calcul du score de la solution (approche basique)
    score = len(slides)  # Exemple : ici, on considère simplement le nombre de diapositives

    # Retourne la solution et son score
    return slides, score


def write_solution(solution, output_file):
    """Écrit la séquence finale des diapositives dans le fichier de sortie."""
    with open(output_file, 'w') as file:  # Ouvre le fichier de sortie en mode écriture
        file.write(f"{len(solution)}\n")  # Écrit le nombre total de diapositives en première ligne
        for slide in solution:  # Parcourt la solution contenant la liste des diapositives
            file.write(" ".join(
                map(str, slide)) + "\n")  # Convertit chaque diapositive en une ligne d'IDs séparés par des espaces


if __name__ == "__main__":  # Vérifie si le script est exécuté directement (et non importé en module)
    main()  # Appelle la fonction principale pour démarrer l'exécution du programme
