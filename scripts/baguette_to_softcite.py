#!/usr/bin/env python3
"""
Convertisseur de sortie 'baguette' -> JSON au format softcite.

La sortie baguette est un fichier .json contenant entre autres :
    {
      "num_paragraphs": ...,
      "paragraphs": [...],
      "mentions": {
        "datasets": [...],
        "software": [
          {
            "name": ...,
            "explicit_or_implicit": "explicit"|"implicit",
            "role": "reused"|"produced"|"mentioned",
            "artifact_type": "tool"|"library"|... (optionnel),
            "evidence": "phrase de preuve",
            "version": ... (optionnel),
            "programming_language": ... (optionnel),
            "repository_or_url": ... (optionnel)
          }, ...
        ]
      },
      "record": {...},
      ...
    }

    Chaque élément de `mentions.software` et `mentions.datasets` est converti
    en une "mention" softcite (type="software" ou type="dataset").

Mapping choisi :
  - software-name : name (offsets à null, non fournis par baguette)
  - software      : artifact_type (tool, library, framework, ...) sinon null
  - software-type : "software" si explicit, "implicit" si implicit
  - context       : evidence (phrase de preuve)
  - version       : version (si présent)
  - language      : programming_language (si présent)
  - url           : repository_or_url (si présent)
  - role -> ContextAttributes :
        reused   -> used    = true
        produced -> created = true
        mentioned-> tous false

Usage :
    python3 baguette_to_softcite.py --baguette entree.json -o sortie.json
"""

import argparse
import json
from pathlib import Path


# ---------------------------------------------------------------------------
# Mappage du rôle baguette vers les attributs used/created/shared
# ---------------------------------------------------------------------------
ROLE_TO_ATTRIBUTES = {
    'reused':   {'used': True,  'created': False, 'shared': False},
    'produced': {'used': False, 'created': True,  'shared': False},
    'mentioned': {'used': False, 'created': False, 'shared': False},
}
# Rôle inconnu -> tous false
DEFAULT_ATTRIBUTES = {'used': False, 'created': False, 'shared': False}


def role_to_attributes(role):
    """Convertit un rôle baguette en dictionnaire used/created/shared."""
    return ROLE_TO_ATTRIBUTES.get(role, DEFAULT_ATTRIBUTES)


def default_attributes():
    """Attributs used/created/shared : false partout, score 0.0."""
    return {
        'used':    {'value': False, 'score': 0.0},
        'created': {'value': False, 'score': 0.0},
        'shared':  {'value': False, 'score': 0.0},
    }


def build_attributes(flags):
    """Construit mentionContextAttributes/documentContextAttributes à partir
    d'un dict {used, created, shared} de booléens."""
    return {
        key: {'value': val, 'score': 1.0 if val else 0.0}
        for key, val in flags.items()
    }


# ---------------------------------------------------------------------------
# Conversion d'une entité baguette (software ou dataset) -> mention softcite
# ---------------------------------------------------------------------------
def _named_field(value):
    """Construit un champ {rawForm, normalizedForm, offsets null}."""
    return {
        'rawForm': value,
        'normalizedForm': value,
        'offsetStart': None,
        'offsetEnd': None,
    }


def entity_to_mention(entity, type_name):
    """Convertit un élément baguette (software ou dataset) en mention softcite.

    - type_name : 'software' ou 'dataset'
    - role -> ContextAttributes : reused->used, produced->created, mentioned->false
    """
    role = entity.get('role')
    flags = role_to_attributes(role)

    mention = {
        'type': type_name,
        'software': entity.get('artifact_type'),
        'software-type': (
            'software' if entity.get('explicit_or_implicit') == 'explicit'
            else 'implicit'
        ),
        'software-name': _named_field(entity.get('name')),
        'context': entity.get('evidence'),
        'mentionContextAttributes': build_attributes(flags),
        'documentContextAttributes': build_attributes(flags),
    }

    # Champs spécifiques aux datasets
    if entity.get('data_types'):
        mention['data_types'] = entity['data_types']
    if entity.get('identifiers'):
        mention['identifiers'] = entity['identifiers']

    # Champs optionnels communs
    if entity.get('version'):
        mention['version'] = _named_field(entity['version'])
    if entity.get('programming_language'):
        mention['language'] = _named_field(entity['programming_language'])
    url = entity.get('repository_or_url') or entity.get('repository')
    if url:
        mention['url'] = _named_field(url)

    return mention


# ---------------------------------------------------------------------------
# Assemblage du document de sortie
# ---------------------------------------------------------------------------
def build_output(software_list, dataset_list, source_path, file_name):
    """Construit le document JSON complet au format softcite."""
    mentions = [entity_to_mention(sw, 'software') for sw in software_list]
    mentions += [entity_to_mention(ds, 'dataset') for ds in dataset_list]
    doc_id = str(abs(hash(source_path)))  # identifiant déterministe simple

    return {
        'application': 'software-mentions',
        'source': 'Baguette',
        'version': '0.9.0-SNAPSHOT',
        'revision': 'baguette-to-softcite',
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
def convert(baguette_path, output_path=None):
    """Convertit un fichier de sortie baguette en JSON softcite."""
    data = json.loads(Path(baguette_path).read_text(encoding='utf-8'))

    mentions = (data.get('mentions') or {})
    software_list = mentions.get('software') or []
    dataset_list = mentions.get('datasets') or []
    output = build_output(
        software_list,
        dataset_list,
        source_path=baguette_path,
        file_name=Path(baguette_path).name,
    )

    if output_path:
        Path(output_path).write_text(
            json.dumps(output, indent=2, ensure_ascii=False),
            encoding='utf-8',
        )
    return output


def main():
    parser = argparse.ArgumentParser(
        description='Convertit une sortie baguette en JSON softcite.'
    )
    parser.add_argument('--baguette', required=True,
                        help='Fichier de sortie baguette (.json)')
    parser.add_argument('-o', '--output',
                        help='Fichier JSON de sortie (sinon affiché sur stdout)')
    args = parser.parse_args()

    output = convert(args.baguette, args.output)
    if not args.output:
        print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
