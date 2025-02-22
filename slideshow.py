import gurobipy as gp
from gurobipy import GRB
import sys, itertools


def read_file(fichier):
    try:
        with open(fichier, 'r') as f:
            nb_images = int(f.readline().strip())
            images = {}
            horizontales = []
            verticales = []
            for i in range(nb_images):
                ligne = f.readline().strip().split()
                orientation = ligne[0]
                tags = set(ligne[2:])
                images[i] = {'orientation': orientation, 'tags': tags}
                if orientation == 'H':
                    horizontales.append(i)
                else:
                    verticales.append(i)
            return nb_images, images, horizontales, verticales
    except FileNotFoundError:
        print(f"Erreur: le fichier {fichier} est introuvable.")
        sys.exit(1)


def score_transition(tags1, tags2):
    """Calcule le score d’une transition entre deux slides."""
    commun = len(tags1 & tags2)
    diff1 = len(tags1 - tags2)
    diff2 = len(tags2 - tags1)
    return min(commun, diff1, diff2)


def build_candidate_slides(images, horizontales, verticales):
    """
    Crée la liste des slides candidates en générant toutes les associations de slides verticales possibles.
      - Pour les photos horizontales, la slide est (i,) avec ses tags.
      - Pour les photos verticales, pour chaque paire (i,j) (i<j) on crée une slide candidate (i,j)
        avec l’union des tags.
    Chaque candidate est un dictionnaire avec :
      'type'   : 'H' ou 'V'
      'photos' : tuple d’indices de photo
      'tags'   : ensemble de tags
    """
    candidates = []
    # Slides horizontales (toujours sélectionnées)
    for i in horizontales:
        candidates.append({
            'type': 'H',
            'photos': (i,),
            'tags': images[i]['tags']
        })
    # Slides candidates verticales (sélectionné ou non)
    for i, j in itertools.combinations(verticales, 2):
        tags_union = images[i]['tags'] | images[j]['tags']
        candidates.append({
            'type': 'V',
            'photos': (i, j),
            'tags': tags_union
        })
    return candidates


def build_model(images, horizontales, verticales):
    # Construction des slides candidates
    candidates = build_candidate_slides(images, horizontales, verticales)
    num_candidates = len(candidates)

    model = gp.Model("Diaporama")

    # --- Variables de décision de slide candidates ---
    # Pour une slide candidate s, z[s] = 1 si elle est utilisée.
    # Pour une slide horizontale, z est fixé à 1.
    z = {}
    for s in range(num_candidates):
        if candidates[s]['type'] == 'H':
            z[s] = model.addVar(vtype=GRB.BINARY, lb=1, ub=1, name=f"z_{s}")
        else:
            z[s] = model.addVar(vtype=GRB.BINARY, name=f"z_{s}")
    model.update()

    # Contrainte de couplage pour les verticales :
    # Chaque photo verticale peut apparaître dans au plus une slide verticale choisie.
    for photo in verticales:
        candidates_lies = [s for s in range(num_candidates)
                        if candidates[s]['type'] == 'V' and photo in candidates[s]['photos']]
        if candidates_lies:
            model.addConstr(gp.quicksum(z[s] for s in candidates_lies) <= 1, name=f"unicite_{photo}")

    # --- Ordonnancement des slides sélectionnées ---
    # On définit les noeuds réels correspondant aux slides candidates et des noeuds fictifs start et end
    # On va créer un chemin de start -> noeuds réels -> end
    n = num_candidates
    nodes = list(range(0, n + 2))  # 0: start, 1..n: slides, n+1: end

    # Variables d'arc x[i,j] pour i,j dans nodes avec (i != j)
    x = {}
    for i in nodes:
        for j in nodes:
            if i != j:
                x[i, j] = model.addVar(vtype=GRB.BINARY, name=f"x_{i}_{j}")
    model.update()

    # Variables de position des slides dans le diaporama (seulement pour les noeuds réels 1..n)
    pos = {}
    for i in range(1, n + 1):
        pos[i] = model.addVar(vtype=GRB.INTEGER, lb=1, ub=n, name=f"pos_{i}")
    model.update()

    # --- Coûts de transition ---
    # Pour deux slides candidates s et t (indices 0..n-1), le coût est pré-calculé à partir de leurs tags.
    cost = {}
    for s in range(n):
        for t in range(n):
            if s != t:
                cost[s, t] = score_transition(candidates[s]['tags'], candidates[t]['tags'])

    # --- Fonction objectif ---
    # L’objectif est de maximiser la somme des scores sur les arcs entre noeuds réels.
    # (Les arcs partant du start et allant vers le end ont un coût nul.)
    model.setObjective(
        gp.quicksum(cost[i - 1, j - 1] * x[i, j] for i in range(1, n + 1) for j in range(1, n + 1) if i != j),
        GRB.MAXIMIZE
    )

    # --- Contraintes d’ordonnancement ---
    # start (0) : exactement un arc sortant vers un noeud réel.
    model.addConstr(gp.quicksum(x[0, j] for j in range(1, n + 1)) == 1, name="sortie_start")
    # end (n+1) : exactement un arc entrant depuis un noeud réel.
    model.addConstr(gp.quicksum(x[i, n + 1] for i in range(1, n + 1)) == 1, name="entree_end")

    # Pour chaque noeud réel i (correspondant à la slide candidate d’indice i-1) :
    # Le degré entrant et sortant doit être égal à z[i-1] (si la slide est sélectionnée, alors 1, sinon 0).
    for i in range(1, n + 1):
        model.addConstr(gp.quicksum(x[j, i] for j in nodes if j != i) == z[i - 1], name=f"noeud_{i}_entrant")
        model.addConstr(gp.quicksum(x[i, j] for j in nodes if j != i) == z[i - 1], name=f"noeud_{i}_sortant")

    # On interdit tout arc entrant au start et sortant du end.
    model.addConstr(gp.quicksum(x[i, 0] for i in nodes if i != 0) == 0, name="prec_start")
    model.addConstr(gp.quicksum(x[n + 1, j] for j in nodes if j != n + 1) == 0, name="succ_end")

    # --- Contraintes MTZ pour éliminer les sous-tournées (sur les noeuds réels uniquement) ---
    for i in range(1, n + 1):
        for j in range(1, n + 1):
            if i != j:
                model.addConstr(pos[i] - pos[j] + n * x[i, j] <= n - 1, name=f"MTZ_{i}_{j}")

    model.update()
    return model, x, pos, z, candidates, n


def get_solution(x, n):
    """
    Extrait l'ordre des noeuds réels (indices de slides candidates, de 0 à n-1)
    en partant du start jusqu'au noeud end
    """
    order = []
    current = 0
    while current != n + 1:
        for j in range(n + 2):
            if current != j and x[current, j].X == 1:
                order.append(j)
                current = j
                break
        else:
            break
    # On retire les noeuds fictifs s’ils apparaissent
    if order and order[0] == 0:
        order = order[1:]
    if order and order[-1] == n + 1:
        order = order[:-1]
    # Les noeuds réels sont dans 1..n, on convertit en indice de candidate (en soustrayant 1)
    candidate_order = [node - 1 for node in order]
    return candidate_order


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(1)

    dataset = sys.argv[1]
    nb_photos, images, horizontales, verticales = read_file(dataset)

    model, x, pos, z, candidates, n = build_model(images, horizontales, verticales)
    model.optimize()

    # Extraction de l’ordre d’ordonnancement parmi les slides sélectionnées
    slide_order = get_solution(x, n)

    # Calcul du score total sur la partie ordonnancement (transitions entre slides sélectionnées)
    total_score = 0
    for i in range(len(slide_order) - 1):
        s = slide_order[i]
        t = slide_order[i + 1]
        total_score += score_transition(candidates[s]['tags'], candidates[t]['tags'])

    # Construction du diaporama final à partir de l'ordre extrait
    # Seules les slides dont z[s] est activé (pour les slides verticales, cela respecte la contrainte de couplage)
    final_slideshow = []
    for i in slide_order:
        if z[i].X == 1:
            final_slideshow.append(candidates[i]['photos'])

    # Écriture dans un fichier .sol
    with open("slideshow.sol", "w") as f:
        f.write(f"{len(final_slideshow)}\n")
        for slide in final_slideshow:
            f.write(" ".join(map(str, slide)) + "\n")
