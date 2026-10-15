#!/usr/bin/env python3
"""
Convertisseur .ann (biotoFlow) -> .json (format de sortie softcite).

Chaque annotation de type 'T' du fichier .ann est convertie en une "mention"
du format softcite. L'étiquette biotoFlow (Tool, Database, ManagementSystem,
WorkflowName, ...) est conservée dans le champ "software-type".

Usage :
    python3 ann_to_softcite.py --ann chemin/vers/fichier.ann \
                               --txt chemin/vers/fichier.txt \
                               -o sortie.json
"""

import argparse
import json
from pathlib import Path


# ---------------------------------------------------------------------------
# Parsing du fichier .ann
# ---------------------------------------------------------------------------
def parse_ann(ann_text):
    """Parse le contenu d'un fichier .ann (brat) et renvoie deux listes :
    - annotations : chaque entrée = {id, label, offsets, text, attributes}
    - relations   : lignes 'R' (non gérées ici, renvoyées telles quelles)
    """
    annotations = []
    attributes = {}
    for line in ann_text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split('\t')
        ann_id = parts[0]

        if ann_id.startswith('T'):
            # Format : T1  Label start end;start2 end2  texte
            label, span = parts[1].split(' ', 1)
            text = parts[2] if len(parts) > 2 else ''
            # Une annotation peut couvrir plusieurs plages (séparées par ';')
            offsets = [
                tuple(int(x) for x in chunk.split(' '))
                for chunk in span.split(';')
            ]
            annotations.append({
                'id': ann_id,
                'label': label,
                'offsets': offsets,
                'text': text,
                'attributes': [],
            })
        elif ann_id.startswith('A'):
            # Format : A1  Attribut T-ref
            attr, ref = parts[1].split(' ', 1)
            attributes[ann_id] = {'attr': attr, 'ref': ref}

    # Associe les attributs (lignes 'A') aux annotations (lignes 'T')
    for ann in annotations:
        for attr in attributes.values():
            if attr['ref'] == ann['id']:
                ann['attributes'].append(attr['attr'])

    return annotations


# ---------------------------------------------------------------------------
# Construction des mentions (format softcite)
# ---------------------------------------------------------------------------
def default_attributes():
    """Attributs used/created/shared par défaut : false partout, score 0.0."""
    return {
        'used':    {'value': False, 'score': 0.0},
        'created': {'value': False, 'score': 0.0},
        'shared':  {'value': False, 'score': 0.0},
    }


def split_sentences(text):
    """Découpe le texte en phrases et renvoie une liste de (start, end, phrase).

    Une phrase est délimitée par les fins de phrase (`.`, `!`, `?`, `;`) ou
    un saut de ligne, suivis d'un espace ou d'une majuscule.
    """
    sentences = []
    start = 0
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in '.!?;' or ch == '\n':
            # Étend la fin sur d'éventuels espaces / fins de phrase répétés
            end = i + 1
            while end < n and (text[end] == '\n' or text[end].isspace()):
                end += 1
            sentences.append((start, end, text[start:end].strip()))
            start = end
            i = end
        else:
            i += 1
    if start < n:
        sentences.append((start, n, text[start:n].strip()))
    return sentences


def get_context(text, offsets):
    """Renvoie la phrase entière qui contient l'entité annotée (contexte)."""
    target = offsets[0][0]
    for start, end, sentence in split_sentences(text):
        if start <= target < end:
            return sentence
    return text[max(0, target):].strip()


def annotation_to_mention(ann, text):
    """Convertit une annotation .ann en dictionnaire 'mention' au format softcite.

    - La clé 'software' prend l'étiquette biotoFlow (Tool, Database, ...).
    - La clé 'software-type' vaut null partout, sauf pour 'Tool' où elle prend
      la valeur de l'attribut associé (BioInfo, General, ...).
    - Le 'context' est la phrase entière contenant l'entité.
    """
    start = ann['offsets'][0][0]
    end = ann['offsets'][0][1]

    # software-type = attribut pour 'Tool', sinon null
    if ann['label'] == 'Tool' and ann['attributes']:
        software_type = ann['attributes'][0]
    else:
        software_type = None

    mention = {
        'type': 'software',
        'software': ann['label'],
        'software-type': software_type,
        'software-name': {
            'rawForm': ann['text'],
            'normalizedForm': ann['text'],
            'offsetStart': start,
            'offsetEnd': end,
        },
        'context': get_context(text, ann['offsets']),
        'mentionContextAttributes': default_attributes(),
        'documentContextAttributes': default_attributes(),
    }

    return mention


# ---------------------------------------------------------------------------
# Assemblage du document de sortie
# ---------------------------------------------------------------------------
def build_output(annotations, text, source_path, file_name):
    """Construit le document JSON complet au format softcite."""
    mentions = [annotation_to_mention(ann, text) for ann in annotations]
    doc_id = str(abs(hash(source_path)))  # identifiant déterministe simple

    return {
        'application': 'software-mentions',
        'source': 'BioToFlow',
        'version': '0.9.0-SNAPSHOT',
        'revision': 'ann-to-softcite',
        'date': None,  # à remplir si besoin
        'mentions': mentions,
        'runtime': len(mentions),
        'id': doc_id,
        'metadata': {'id': doc_id},
        'original_file_path': str(source_path),
        'file_name': file_name,
    }


# ---------------------------------------------------------------------------
# Fonction principale
# ---------------------------------------------------------------------------
def convert(ann_path, txt_path, output_path=None):
    """Convertit un fichier .ann (+ .txt associé) en JSON softcite."""
    ann_text = Path(ann_path).read_text(encoding='utf-8')
    text = Path(txt_path).read_text(encoding='utf-8')

    annotations = parse_ann(ann_text)
    output = build_output(
        annotations,
        text,
        source_path=txt_path,
        file_name=Path(txt_path).name,
    )

    if output_path:
        Path(output_path).write_text(
            json.dumps(output, indent=2, ensure_ascii=False),
            encoding='utf-8',
        )
    return output


def main():
    parser = argparse.ArgumentParser(
        description='Convertit un fichier .ann (biotoFlow) en JSON softcite.'
    )
    parser.add_argument('--ann', required=True, help='Fichier d\'annotations .ann')
    parser.add_argument('--txt', required=True, help='Fichier texte source .txt')
    parser.add_argument('-o', '--output', help='Fichier JSON de sortie '
                                               '(sinon affiché sur stdout)')
    args = parser.parse_args()

    output = convert(args.ann, args.txt, args.output)

    if not args.output:
        print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
