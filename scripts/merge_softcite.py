#!/usr/bin/env python3
"""
Fusion des sorties softcite (natif, baguette, bio2flow) en une sortie unique
par papier, en prenant le fichier softcite natif comme référence.

Principe :
  - Le fichier softcite natif est la référence : on conserve toutes ses
    mentions et sa structure racine.
  - On ajoute ensuite les mentions de baguette et de bio2flow qui ne sont pas
    déjà présentes dans la référence.
  - Une mention est considérée comme "déjà présente" si son nom de logiciel
    (software-name.rawForm) correspond à un nom déjà présent, en ignorant la
    casse et après un nettoyage léger (apostrophes, espaces superflus).
  - Les mentions de type 'software' ET 'dataset' sont toutes conservées.
  - Chaque mention se voit ajouter un champ 'origins' (liste des outils qui
    l'ont détectée) pour la traçabilité.

Usage :
    python3 merge_softcite.py --softcite dossier_softcite_natif \
                              --baguette dossier_softcite_from_baguette \
                              --bio2flow dossier_softcite_from_bio2flow \
                              -o dossier_sortie
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path


# ---------------------------------------------------------------------------
# Normalisation des noms de logiciel (pour la correspondance 2B)
# ---------------------------------------------------------------------------
def normalize_name(name):
    """Normalise un nom de logiciel pour la comparaison :
    - minuscules
    - suppression des apostrophes, guillemets, accents, ponctuation superflue
    - réduction des espaces multiples
    """
    if not name:
        return ''
    name = name.lower()
    name = name.replace("'", '').replace('’', '').replace('"', '').replace('`', '')
    name = re.sub(r'[^\w\s.-]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def mention_name(mention):
    """Renvoie le nom normalisé d'une mention."""
    return normalize_name((mention.get('software-name') or {}).get('rawForm'))


# ---------------------------------------------------------------------------
# Chargement des fichiers et correspondance des papiers
# ---------------------------------------------------------------------------
def list_papers(directory):
    """Renvoie {clé_normalisée: chemin_fichier} pour un dossier donné.

    La clé est le nom de fichier débarrassé des suffixes
    '.software.json' / '.grobid.tei.xml.software.json'.
    """
    result = {}
    directory = Path(directory)
    if not directory.is_dir():
        return result
    for path in directory.glob('*.json'):
        name = path.name
        if name.endswith('.grobid.tei.xml.software.json'):
            key = name[:-len('.grobid.tei.xml.software.json')]
        elif name.endswith('.software.json'):
            key = name[:-len('.software.json')]
        elif name.endswith('.json'):
            key = name[:-len('.json')]
        else:
            continue
        result[key] = path
    return result


def load_mentions(path):
    """Charge les mentions d'un fichier softcite."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    return data, (data.get('mentions') or [])


# ---------------------------------------------------------------------------
# Fusion
# ---------------------------------------------------------------------------
def tag(mention, source):
    """Ajoute l'origine à une mention (crée le champ si absent)."""
    origins = mention.setdefault('origins', [])
    if source not in origins:
        origins.append(source)


def add_non_duplicate(current, candidates, source):
    """Ajoute les mentions de 'candidates' absentes de 'current' (par nom
    normalisé), les tague avec 'source', et renvoie la nouvelle liste."""
    seen = {mention_name(m) for m in current}
    result = list(current)
    added = []
    for mention in candidates:
        if mention_name(mention) in seen:
            continue
        mention = dict(mention)  # copie pour ne pas muter la source
        tag(mention, source)
        result.append(mention)
        added.append(mention)
        seen.add(mention_name(mention))
    return result, added


# ---------------------------------------------------------------------------
# Fusion d'un papier
# ---------------------------------------------------------------------------
def merge_paper(softcite_path, baguette_path, bio2flow_path):
    """Fusionne les 3 fichiers d'un même papier et renvoie le document JSON."""
    ref_data, ref_mentions = load_mentions(softcite_path)

    # La référence garde toutes ses mentions, taguées 'softcite'
    ref_mentions = [dict(m) for m in ref_mentions]
    for mention in ref_mentions:
        tag(mention, 'softcite')

    # Ajout des mentions baguette non dupliquées
    if baguette_path:
        _, bag_mentions = load_mentions(baguette_path)
        ref_mentions, added_bag = add_non_duplicate(
            ref_mentions, bag_mentions, 'baguette')
    else:
        added_bag = []

    # Ajout des mentions bio2flow non dupliquées
    if bio2flow_path:
        _, bio_mentions = load_mentions(bio2flow_path)
        ref_mentions, added_bio = add_non_duplicate(
            ref_mentions, bio_mentions, 'bio2flow')
    else:
        added_bio = []

    document = dict(ref_data)
    document['mentions'] = ref_mentions
    document['runtime'] = len(ref_mentions)
    document['merged_from'] = {
        'softcite': sum(1 for m in ref_mentions if 'softcite' in m.get('origins', [])),
        'baguette': len(added_bag),
        'bio2flow': len(added_bio),
    }
    return document


# ---------------------------------------------------------------------------
# Fonction principale
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description='Fusionne les sorties softcite (natif/baguette/bio2flow) '
                    'en une sortie unique par papier (softcite = référence).'
    )
    parser.add_argument('--softcite', required=True,
                        help='Dossier des sorties softcite natives')
    parser.add_argument('--baguette', required=True,
                        help='Dossier des sorties softcite_from_baguette')
    parser.add_argument('--bio2flow', required=True,
                        help='Dossier des sorties softcite_from_bio2flow')
    parser.add_argument('-o', '--output', required=True,
                        help='Dossier de sortie (fichiers fusionnés)')
    args = parser.parse_args()

    softcite_papers = list_papers(args.softcite)
    baguette_papers = list_papers(args.baguette)
    bio2flow_papers = list_papers(args.bio2flow)

    all_keys = set(softcite_papers) | set(baguette_papers) | set(bio2flow_papers)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    processed = 0
    total = Counter()
    absent_other = []
    absent_softcite = []

    for key in sorted(all_keys):
        softcite_path = softcite_papers.get(key)
        baguette_path = baguette_papers.get(key)
        bio2flow_path = bio2flow_papers.get(key)

        if softcite_path is None:
            absent_softcite.append(key)
            continue

        document = merge_paper(softcite_path, baguette_path, bio2flow_path)

        out_path = output_dir / f'{key}.software.json'
        out_path.write_text(
            json.dumps(document, indent=2, ensure_ascii=False),
            encoding='utf-8',
        )
        processed += 1
        for source in ('softcite', 'baguette', 'bio2flow'):
            total[source] += document['merged_from'].get(source, 0)

        if baguette_path is None or bio2flow_path is None:
            absent_other.append(key)

    print(f"==> Papiers fusionnés : {processed}")
    print(f"==> Mentions totales par source : {dict(total)}")

    if absent_other:
        print(f"==> Papiers fusionnés mais absents d'une autre source "
              f"({len(absent_other)}) :")
        for k in absent_other:
            print(f"    - {k}")
    if absent_softcite:
        print(f"==> Papiers absents de softcite (non fusionnés, "
              f"{len(absent_softcite)}) :")
        for k in absent_softcite:
            print(f"    - {k}")


if __name__ == '__main__':
    main()
