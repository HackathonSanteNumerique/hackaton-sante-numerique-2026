"""Download the PEPR Santé Numérique HAL corpus from the Hugging Face Hub.

Usage:
    uv run python scripts/download_pepr.py                 # everything into data/pepr-hal-data
    uv run python scripts/download_pepr.py --pattern "*.md" # only some files
"""

import argparse
from pathlib import Path

from huggingface_hub import snapshot_download

REPO_ID = "HackatonSanteNumerique/pepr-hal-data"
DEFAULT_DIR = Path(__file__).resolve().parent.parent / "data" / "pepr-hal-data"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=DEFAULT_DIR, help=f"output directory (default: {DEFAULT_DIR})")
    parser.add_argument(
        "--pattern",
        action="append",
        help="glob of files to download, can be repeated (e.g. '*.json'); default: all files",
    )
    args = parser.parse_args()

    path = snapshot_download(
        repo_id=REPO_ID,
        repo_type="dataset",
        local_dir=args.out,
        allow_patterns=args.pattern,
    )
    print(f"Downloaded {REPO_ID} to {path}")


if __name__ == "__main__":
    main()
