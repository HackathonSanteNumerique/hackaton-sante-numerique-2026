#!/usr/bin/env bash
# Fusionne les sorties softcite (natif / baguette / bio2flow) en une sortie
# unique par papier, en prenant softcite comme référence.
#
# Usage :
#   ./run_merge.sh [dossier_softcite] [dossier_baguette] [dossier_bio2flow] [dossier_sortie]
#
# Valeurs par défaut :
#   softcite = pepr-hal-data/softcite
#   baguette = pepr-hal-data/softcite_from_baguette
#   bio2flow = pepr-hal-data/softcite_from_bio2flow
#   sortie   = pepr-hal-data/merged
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

SOFTCITE_DIR="${1:-pepr-hal-data/softcite}"
BAGUETTE_DIR="${2:-pepr-hal-data/softcite_from_baguette}"
BIO2FLOW_DIR="${3:-pepr-hal-data/softcite_from_bio2flow}"
OUTPUT_DIR="${4:-pepr-hal-data/merged}"

VENV_DIR=".venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "==> Création de l'environnement virtuel ($VENV_DIR)"
    python3 -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

mkdir -p "$OUTPUT_DIR"

echo "==> Softcite natif   : $SOFTCITE_DIR"
echo "==> Softcite baguette: $BAGUETTE_DIR"
echo "==> Softcite bio2flow: $BIO2FLOW_DIR"
echo "==> Sortie           : $OUTPUT_DIR"

python3 merge_softcite.py \
    --softcite "$SOFTCITE_DIR" \
    --baguette "$BAGUETTE_DIR" \
    --bio2flow "$BIO2FLOW_DIR" \
    -o "$OUTPUT_DIR"
