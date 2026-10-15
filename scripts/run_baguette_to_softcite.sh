#!/usr/bin/env bash
# Itère sur tous les fichiers de sortie baguette (.json) d'un dossier d'entrée,
# convertit chacun en JSON softcite (via baguette_to_softcite.py) et écrit le
# résultat dans un dossier de sortie.
#
# Usage :
#   ./run_baguette_to_softcite.sh [dossier_entree] [dossier_sortie]
#
# Valeurs par défaut :
#   entrée = pepr-hal-data/baguette/   sortie = pepr-hal-data/softcite_from_baguette/
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

INPUT_DIR="${1:-pepr-hal-data/baguette}"
OUTPUT_DIR="${2:-pepr-hal-data/softcite_from_baguette}"

VENV_DIR=".venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "==> Création de l'environnement virtuel ($VENV_DIR)"
    python3 -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

mkdir -p "$OUTPUT_DIR"

echo "==> Dossier d'entrée : $INPUT_DIR"
echo "==> Dossier de sortie : $OUTPUT_DIR"

processed=0

shopt -s nullglob
json_files=("$INPUT_DIR"/*.json)
shopt -u nullglob

if [ "${#json_files[@]}" -eq 0 ]; then
    echo "!! Aucun fichier .json trouvé dans $INPUT_DIR"
    exit 0
fi

for json_file in "${json_files[@]}"; do
    base="$(basename "$json_file" .json)"
    out_file="$OUTPUT_DIR/${base}.software.json"
    echo "--> $(basename "$json_file") -> $(basename "$out_file")"
    python3 baguette_to_softcite.py --baguette "$json_file" -o "$out_file"
    processed=$((processed + 1))
done

echo ""
echo "==> Terminé : $processed fichier(s) converti(s)."
echo "==> Sorties dans $OUTPUT_DIR"
