#!/usr/bin/env bash
# Itère sur tous les fichiers .ann d'un dossier d'entrée, convertit chacun en
# JSON softcite (via ann_to_softcite.py) et écrit le résultat dans un dossier
# de sortie.
#
# Pour chaque .ann, le .txt source associé est recherché dans le même dossier
# (même nom de base, extension .txt). S'il est introuvable, le fichier est
# ignoré avec un avertissement.
#
# Usage :
#   ./run_ann_to_softcite.sh [dossier_entree] [dossier_sortie]
#
# Valeurs par défaut : entrée=data/  sortie=data/software_json/
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

INPUT_DIR="${1:-data}"
OUTPUT_DIR="${2:-data/software_json}"

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
skipped=0

# Activer le globbing nul pour que le glob ne reste pas littéral s'il n'y a rien
shopt -s nullglob
ann_files=("$INPUT_DIR"/*.ann)
shopt -u nullglob

if [ "${#ann_files[@]}" -eq 0 ]; then
    echo "!! Aucun fichier .ann trouvé dans $INPUT_DIR"
    exit 0
fi

for ann_file in "${ann_files[@]}"; do
    base="${ann_file%.ann}"
    txt_file="${base}.txt"

    if [ ! -f "$txt_file" ]; then
        echo "!! Ignoré (pas de .txt associé) : $(basename "$ann_file")"
        skipped=$((skipped + 1))
        continue
    fi

    out_file="$OUTPUT_DIR/$(basename "$base").software.json"
    echo "--> $(basename "$ann_file") -> $(basename "$out_file")"
    python3 ann_to_softcite.py --ann "$ann_file" --txt "$txt_file" -o "$out_file"
    processed=$((processed + 1))
done

echo ""
echo "==> Terminé : $processed fichier(s) converti(s), $skipped ignoré(s)."
echo "==> Sorties dans $OUTPUT_DIR"
