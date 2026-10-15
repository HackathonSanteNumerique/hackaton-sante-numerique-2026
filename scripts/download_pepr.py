"""Download the PEPR Santé Numérique HAL corpus from the Hugging Face Hub.

The repo holds the GROBID outputs (grobid/xml, grobid/json, grobid/md) and the outputs of the
tools on them: softcite/, baguette/, bio2flow/ and bio2flow_json/.

Usage:
    uv run python scripts/download_pepr.py                            # everything into data/pepr-hal-data
    uv run python scripts/download_pepr.py --pattern "softcite/*"     # only the Softcite output
    uv run python scripts/download_pepr.py --pattern "grobid/xml/*"   # only the GROBID TEI files
"""

import argparse
from pathlib import Path

from huggingface_hub import snapshot_download

REPO_ID = "HackatonSanteNumerique/pepr-hal-data"
# A dataset repo: https://huggingface.co/datasets/HackatonSanteNumerique/pepr-hal-data
REPO_TYPE = "dataset"
DEFAULT_DIR = Path(__file__).resolve().parent.parent / "data" / "pepr-hal-data"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=DEFAULT_DIR, help=f"output directory (default: {DEFAULT_DIR})")
    parser.add_argument(
        "--pattern",
        action="append",
        help="glob of files to download, can be repeated (e.g. 'softcite/*'); default: all files",
    )
    args = parser.parse_args()

    path = snapshot_download(
        repo_id=REPO_ID,
        repo_type=REPO_TYPE,
        local_dir=args.out,
        allow_patterns=args.pattern,
    )
    print(f"Downloaded {REPO_ID} to {path}")


if __name__ == "__main__":
    main()
