"""
CoPaLink article NER on papers: text, TEI (GROBID) or JSON input.

Runs the paper-text model of sharefair/nlp_models
(https://gitlab.liris.cnrs.fr/sharefair/nlp_models) locally, with nlstruct.
The inputs are read as in the Baguette client and server (lm-inference):

One input is one paper:
    --text          a text, given on the command line
    --input-file    one or more files
    --input-folder  all the files of a folder

File types, by extension:
    .txt, .md  text; the paragraphs are the blocks separated by blank lines
    .xml       TEI (GROBID): the <p> elements of the abstract, body and back
    .json      a list of strings, or an object with 'paragraphs' or 'text'

The paragraphs are joined with blank lines into one document, predicted with
nlstruct, and each entity is assigned back to its paragraph.

Setup (once), in the copalink-experiments Conda environment of nlp_models:
    git clone https://gitlab.liris.cnrs.fr/sharefair/nlp_models.git   # with git-lfs, for the .pt model
    cd nlp_models && git clone https://github.com/ClemenceS/nlstruct.git
nlstruct needs transformers 4.x (nlp_models pins 4.56.1): transformers 5 removed
tokenizer.encode_plus.

Usage, from the nlp_models folder (the defaults of --model and --nlstruct):
    python copalink_client.py --text "Reads were aligned with BWA and sorted with samtools."

    python copalink_client.py \
        --input-folder ../hackaton-sante-numerique-2026/data/pepr-hal-data/grobid/xml \
        --output-dir ./copalink_out \
        --csv-output ./copalink_results.csv \
        --softcite-dir ./copalink_softcite \
        --brat-dir ./copalink_brat

Without --output-dir (or --softcite-dir) the result is printed. --softcite-dir also
writes each paper in the JSON schema of the Softcite software-mentions service
(<paper>.tei.software.json for a TEI input, <paper>.software.json otherwise), so
that the tools written for Softcite, such as notebooks/softcite_analysis.ipynb,
read it too. --brat-dir also writes the .txt and .ann files of each paper, in the
format of predict_files.py, to view in brat.

A run can be stopped (Ctrl+C) and restarted: the papers that already have their
files in --output-dir and --softcite-dir are skipped. With neither, the papers
with a successful row in --csv-output are skipped.

The model runs on the GPU when there is one (CUDA, or MPS on a Mac), otherwise on
the CPU; --device forces one. If a prediction fails on MPS, the client retries it
and runs the rest of the papers on the CPU.
"""

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
import traceback
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

EXTENSIONS = (".txt", ".md", ".xml", ".json")
FIELDS = ["document", "paragraphs", "entities", "unique_entities", "runtime_sec", "success"]
BLANK_LINES = re.compile(r"\n[ \t\r]*\n")
TEI = "{http://www.tei-c.org/ns/1.0}"
PARAGRAPH_SEPARATOR = "\n\n"


# Input reading, as in the Baguette server (deployments/baguette/inference_baguette.py).
def clean(text: str) -> str:
    return " ".join(text.split())


def split_text(text: str) -> list[str]:
    """Paragraphs of a plain text: the blocks separated by blank lines."""
    return [clean(block) for block in BLANK_LINES.split(text) if block.strip()]


def read_tei(content: bytes) -> list[str]:
    """Paragraphs of a TEI document (GROBID): the <p> elements of the abstract,
    body and back."""
    root = ET.fromstring(content)
    paragraphs = []
    for section in (f".//{TEI}abstract", f"./{TEI}text"):
        for parent in root.iterfind(section):
            for p in parent.iter(f"{TEI}p"):
                paragraphs.append(clean("".join(p.itertext())))
    return [p for p in paragraphs if p]


def read_paragraphs_field(paragraphs) -> list[str]:
    if not isinstance(paragraphs, list) or not all(isinstance(p, str) for p in paragraphs):
        raise ValueError("'paragraphs' must be a list of strings")
    return [clean(p) for p in paragraphs if p.strip()]


def read_json(data) -> list[str]:
    """Paragraphs of a JSON input: a list of strings, or an object with a
    'paragraphs' list or a 'text'."""
    if isinstance(data, list):
        return read_paragraphs_field(data)
    if isinstance(data, dict) and "paragraphs" in data:
        return read_paragraphs_field(data["paragraphs"])
    if isinstance(data, dict) and isinstance(data.get("text"), str):
        return split_text(data["text"])
    raise ValueError("expected 'paragraphs' (list of strings) or 'text' (string)")


def read_file(path: Path) -> list[str]:
    """Paragraphs of a file, according to its extension."""
    content = path.read_bytes()
    if path.suffix.lower() == ".xml":
        return read_tei(content)
    text = content.decode("utf-8-sig", errors="replace")
    if path.suffix.lower() == ".json":
        return read_json(json.loads(text))
    return split_text(text)


def read_biblio(path: Path) -> dict:
    """Title, authors and DOI of a TEI document (GROBID), as in the 'biblio' of Softcite."""
    root = ET.fromstring(path.read_bytes())
    biblio = {}
    title = root.find(f".//{TEI}titleStmt/{TEI}title")
    if title is not None and clean("".join(title.itertext())):
        biblio["title"] = clean("".join(title.itertext()))
    authors = []
    for name in root.iterfind(f".//{TEI}sourceDesc//{TEI}analytic/{TEI}author/{TEI}persName"):
        parts = [clean("".join(part.itertext())) for part in name if part.tag in (f"{TEI}forename", f"{TEI}surname")]
        if any(parts):
            authors.append(" ".join(part for part in parts if part))
    if authors:
        biblio["authors"] = ", ".join(authors)
    doi = root.find(f".//{TEI}sourceDesc//{TEI}idno[@type='DOI']")
    if doi is not None and doi.text and doi.text.strip():
        biblio["doi"] = doi.text.strip()
    return biblio


# Prediction.
def parse_args():
    parser = argparse.ArgumentParser(description="CoPaLink article NER client")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", help="Text of one paper")
    source.add_argument("--input-file", nargs="+", help="One file per paper")
    source.add_argument("--input-folder", help="Folder with one file per paper")
    parser.add_argument("--output-dir", help="One JSON file per paper; default: print")
    parser.add_argument("--csv-output", help="CSV summary, one row per paper")
    parser.add_argument("--softcite-dir", help="Also write each paper in the Softcite JSON schema")
    parser.add_argument("--brat-dir", help="Also write <paper>.txt and <paper>.ann for brat")
    parser.add_argument("--model", default="csebe_scibert_bioinfo_voc_iteration4_seed100.pt",
                        help="nlstruct checkpoint (default: the one of nlp_models)")  # fmt: skip
    parser.add_argument("--nlstruct", default="nlstruct", help="Folder of the nlstruct clone")
    parser.add_argument("--batch-size", type=int, default=32,
                        help="Sequences per SciBERT batch; lower it if the GPU runs out of memory (default: 32)")  # fmt: skip
    parser.add_argument("--device", default="auto",
                        help="auto (default: cuda, then mps, then cpu), cuda, cuda:1, mps or cpu")  # fmt: skip
    args = parser.parse_args()
    if args.input_folder and not (args.output_dir or args.softcite_dir):
        parser.error("--input-folder requires --output-dir or --softcite-dir")
    return args


def pick_device(name: str):
    """The device of --device; with 'auto', the GPU if there is one (CUDA, or MPS on a Mac)."""
    import torch

    if name != "auto":
        return torch.device(name)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def patch_pad_to_tensor(torch_utils):
    """Build the input tensors of nlstruct on the CPU, then move them to the device.

    pad_to_tensor creates each row on the device and copies it into a CPU array at
    its offset: on MPS, a copy to an offset that isn't a multiple of 4 bytes fails
    ("Unaligned blit request"), for instance for the bool masks. The result is the
    same, without a round trip per row."""
    pad_to_tensor = torch_utils.pad_to_tensor

    def pad_to_tensor_on_cpu(y, dtype=None, device=None, pad=0):
        array = pad_to_tensor(y, dtype=dtype, pad=pad)
        return array if device is None else array.to(device)

    # batch_to_tensors looks pad_to_tensor up in its module at each call.
    torch_utils.pad_to_tensor = pad_to_tensor_on_cpu


def to_cpu(value):
    """The tensors of a (nested) value moved to the CPU."""
    if hasattr(value, "cpu") and hasattr(value, "device"):
        return value.cpu()
    if isinstance(value, dict):
        return {key: to_cpu(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(to_cpu(item) for item in value)
    return value


def batch_bert(model, batch_size: int):
    """Run SciBERT on the sequences of a paper by batches of batch_size.

    nlstruct runs all the sequences of a paper at once and keeps the hidden states
    of the 13 layers: a long paper needs tens of GB, more than a GPU (or a Mac) has.
    Each sequence is encoded independently, so the result is the same; the outputs
    of the batches are padded with zeros to the same length, as nlstruct does."""
    import torch

    for encoder in model.encoder.encoders:
        if not hasattr(encoder, "exec_bert"):
            continue
        exec_bert = encoder.exec_bert

        def exec_bert_batched(tokens, mask, slices_begin, slices_end, exec_bert=exec_bert):
            if len(tokens) <= batch_size:
                return exec_bert(tokens, mask, slices_begin, slices_end)
            batches = [
                exec_bert(tokens[i : i + batch_size], mask[i : i + batch_size],
                          slices_begin[i : i + batch_size], slices_end[i : i + batch_size])  # fmt: skip
                for i in range(0, len(tokens), batch_size)
            ]
            results = []
            for outputs in zip(*batches):
                length = max(output.shape[1] for output in outputs)
                padded = []
                for output in outputs:
                    full = output.new_zeros((output.shape[0], length, *output.shape[2:]))
                    full[:, : output.shape[1]] = output
                    padded.append(full)
                results.append(torch.cat(padded))
            return results

        encoder.exec_bert = exec_bert_batched


def run_decoder_on_cpu(model):
    """Run the decoder of the model on the CPU, the encoder staying on its device.

    The span scorer of the decoder computes the CRF marginals in float64, which MPS
    doesn't support. The encoder (SciBERT, 115M parameters) does most of the work; the
    decoder (BiLSTM, span scorer and qualifier, 4M) is cheap on the CPU, and keeps its
    float64 precision."""
    model.decoder.to("cpu")
    forward = model.decoder.forward

    def forward_on_cpu(*args, **kwargs):
        return forward(*to_cpu(args), **to_cpu(kwargs))

    model.decoder.forward = forward_on_cpu


def load_model(args):
    """Import nlstruct from its clone, as predict_files.py does, and load the model
    on the GPU if there is one."""
    # On MPS, run the operations that PyTorch doesn't implement there on the CPU
    # instead of failing; it must be set before torch is imported.
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    import transformers

    # nlstruct calls tokenizer.encode_plus, which transformers 5 removed: every paper
    # would fail with "BertTokenizer has no attribute encode_plus".
    if int(transformers.__version__.split(".")[0]) >= 5:
        sys.exit(
            f"transformers {transformers.__version__} is not supported by nlstruct; "
            'install the version of nlp_models: pip install "transformers==4.56.1"'
        )
    sys.path.insert(0, str(Path(args.nlstruct).resolve()))
    import nlstruct.torch_utils
    from nlstruct import load_pretrained

    patch_pad_to_tensor(nlstruct.torch_utils)
    # load_pretrained puts the weights on CUDA if available, but the model it builds
    # stays on the CPU: predict runs on the device of the parameters, so move them.
    device = pick_device(args.device)
    model = load_pretrained(args.model).to(device)
    batch_bert(model, args.batch_size)
    if device.type == "mps":
        run_decoder_on_cpu(model)
        print("Model loaded on mps (encoder) and cpu (decoder)", file=sys.stderr)
    else:
        print(f"Model loaded on {device}", file=sys.stderr)
    return model


def split_label(label) -> tuple[str, list[str]]:
    """Entity type and attributes of an nlstruct label. A multi-label entity has
    a list such as ['Tool', 'Usage:Yes']: the label without ':' is the type,
    the others are attributes (as transform_ann.changeFormat does for brat)."""
    labels = label if isinstance(label, (list, tuple)) else [label]
    types = [lab for lab in labels if ":" not in lab]
    attributes = [lab for lab in labels if ":" in lab]
    return (types[0] if types else labels[0]), attributes


def predict_document(model, document: dict) -> dict:
    """model.predict, falling back to the CPU if it fails on MPS, which doesn't
    support every PyTorch operation. The model then stays on the CPU for the rest
    of the run."""
    try:
        return model.predict(document)
    except Exception as e:  # noqa: BLE001
        if next(model.parameters()).device.type != "mps":
            raise
        # The frames of the error, to find the operation that MPS doesn't support.
        frames = "".join(traceback.format_tb(e.__traceback__)[-6:])
        print(f"Prediction failed on mps, switching to the CPU: {str(e).splitlines()[0]}\n{frames}", file=sys.stderr)
        model.to("cpu")
        return model.predict(document)


def predict(model, model_name: str, name: str, paragraphs: list[str]) -> tuple[dict, dict]:
    """Predict one paper and assign each entity to its paragraph."""
    text = PARAGRAPH_SEPARATOR.join(paragraphs)
    starts, offset = [], 0
    for paragraph in paragraphs:
        starts.append(offset)
        offset += len(paragraph) + len(PARAGRAPH_SEPARATOR)

    start = time.time()
    doc = predict_document(model, {"doc_id": name, "text": text})
    duration = time.time() - start

    items = [{"index": i, "text": p, "entities": []} for i, p in enumerate(paragraphs)]
    for entity in doc.get("entities", []):
        fragments = sorted(entity["fragments"], key=lambda f: f["begin"])
        # nlstruct may give numpy integers, which json can't serialise.
        begin, end = int(fragments[0]["begin"]), int(fragments[-1]["end"])
        index = max(i for i, s in enumerate(starts) if s <= begin)
        entity_type, attributes = split_label(entity["label"])
        items[index]["entities"].append({
            "text": text[begin:end],
            "type": entity_type,
            "attributes": attributes,
            "begin": begin - starts[index],
            "end": end - starts[index],
            "confidence": round(float(entity.get("confidence", 0)), 4),
        })  # fmt: skip

    # Deduplicated by lower-cased text and type; the first mention is kept.
    seen, mentions = set(), []
    for item in items:
        for entity in item["entities"]:
            key = (entity["text"].lower(), entity["type"])
            if key not in seen:
                seen.add(key)
                mentions.append(entity)
    return {
        "num_paragraphs": len(items),
        "paragraphs": items,
        "mentions": mentions,
        "duration_seconds": round(duration, 2),
        "model": model_name,
    }, doc


def to_softcite(data: dict, path: Path | None, name: str, content: bytes) -> dict:
    """A paper in the JSON schema of the Softcite software-mentions service.

    Each entity is a mention of type 'software': the model has only one entity type,
    Tool, and no version, publisher, URL or language. The context is the paragraph
    (Softcite gives the sentence), and the offsets of 'software-name' are relative to
    it. There are no 'mentionContextAttributes' and 'documentContextAttributes':
    CoPaLink doesn't predict whether the software is used, created or shared."""
    mentions = [
        {
            "type": "software",
            "software-type": "software",
            "software-name": {
                "rawForm": entity["text"],
                "normalizedForm": clean(entity["text"]),
                "offsetStart": entity["begin"],
                "offsetEnd": entity["end"],
            },
            "context": item["text"],
        }
        for item in data["paragraphs"]
        for entity in item["entities"]
    ]
    result = {
        "application": "copalink",
        "version": data["model"],
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M%z"),
        "md5": hashlib.md5(content).hexdigest().upper(),
    }
    if path is not None and path.suffix.lower() == ".xml":
        result["biblio"] = read_biblio(path)
    result.update({
        "mentions": mentions,
        "references": [],
        "runtime": int(data["duration_seconds"] * 1000),
        "file_name": name,
    })  # fmt: skip
    return result


def softcite_name(path: Path | None, stem: str) -> str:
    """The file name of Softcite: <paper>.tei.software.json for a TEI input."""
    return f"{stem}.tei.software.json" if path is not None and path.suffix.lower() == ".xml" else f"{stem}.software.json"


def write_json(path: Path, data):
    """Written to a temporary file first: a run stopped while writing doesn't leave
    a truncated JSON that a restart would take as done."""
    path_tmp = path.with_name(path.name + ".tmp")
    path_tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    path_tmp.replace(path)


def write_brat(brat_dir: str, name: str, doc: dict):
    """<name>.txt and <name>.ann, in the format of predict_files.py."""
    with open(Path(brat_dir) / f"{name}.txt", "w", encoding="utf-8") as f:
        f.write(doc["text"])
    lines, attribute_index = [], 1
    for i, entity in enumerate(doc.get("entities", []), 1):
        spans = ";".join(f"{f['begin']} {f['end']}" for f in sorted(entity["fragments"], key=lambda f: f["begin"]))
        surface = " ".join(doc["text"][f["begin"] : f["end"]] for f in entity["fragments"]).replace("\n", " ")
        entity_type, attributes = split_label(entity["label"])
        lines.append(f"T{i}\t{entity_type} {spans}\t{surface}")
        for attribute in attributes:
            key, value = attribute.split(":", 1)
            lines.append(f"A{attribute_index}\t{key} T{i}" + (f" {value}" if value else ""))
            attribute_index += 1
    with open(Path(brat_dir) / f"{name}.ann", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))


def output_files(args, path: Path | None) -> list[Path]:
    """The files written for a paper in --output-dir and --softcite-dir."""
    name = path.name if path else "text"
    stem = name.split(".")[0] if path else name
    files = []
    if args.output_dir:
        files.append(Path(args.output_dir) / f"{name}.json")
    if args.softcite_dir:
        files.append(Path(args.softcite_dir) / softcite_name(path, stem))
    return files


def is_done(args, path: Path | None, csv_done: set) -> bool:
    """A paper is done if all its files exist or, without output files, if the CSV
    has a successful row for it."""
    if path is None:
        return False
    files = output_files(args, path)
    return all(f.exists() for f in files) if files else path.name in csv_done


def load_csv_done(csv_path) -> set:
    done = set()
    if csv_path and Path(csv_path).exists():
        with open(csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if str(row.get("success", "")).lower() == "true":
                    done.add(row["document"])
    return done


def append_row(csv_path, row):
    if not csv_path:
        return
    write_header = not Path(csv_path).exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def run_one(args, model, path: Path | None) -> tuple[bool, str]:
    name = path.name if path else "text"
    row = {"document": name, "paragraphs": 0, "entities": 0, "unique_entities": 0, "runtime_sec": 0, "success": False}
    try:
        content = args.text.encode("utf-8") if path is None else path.read_bytes()
        paragraphs = split_text(args.text) if path is None else read_file(path)
        if not paragraphs:
            raise ValueError("no paragraph found in the input")
        # brat and the doc id use the name without the extension(s).
        stem = name.split(".")[0] if path else name
        data, doc = predict(model, Path(args.model).name, stem, paragraphs)
        if args.output_dir:
            write_json(Path(args.output_dir) / f"{name}.json", data)
        if args.softcite_dir:
            write_json(Path(args.softcite_dir) / softcite_name(path, stem), to_softcite(data, path, name, content))
        if not (args.output_dir or args.softcite_dir):
            print(json.dumps(data, ensure_ascii=False, indent=1))
        if args.brat_dir:
            write_brat(args.brat_dir, stem, doc)
        entities = sum(len(item["entities"]) for item in data["paragraphs"])
        row.update({
            "paragraphs": data["num_paragraphs"], "entities": entities,
            "unique_entities": len(data["mentions"]),
            "runtime_sec": data["duration_seconds"], "success": True,
        })  # fmt: skip
        append_row(args.csv_output, row)
        return True, (
            f"{name}: {data['num_paragraphs']} paragraphs, {entities} entities "
            f"({len(data['mentions'])} unique) in {data['duration_seconds']:.1f}s"
        )
    except Exception as e:  # noqa: BLE001
        append_row(args.csv_output, row)
        return False, f"{name}: FAILED ({e})"


def main():
    args = parse_args()
    for folder in (args.output_dir, args.softcite_dir, args.brat_dir):
        if folder:
            os.makedirs(folder, exist_ok=True)

    if args.text is not None:
        papers = [None]
    elif args.input_file:
        papers = [Path(p) for p in args.input_file]
    else:
        papers = [
            p
            for p in sorted(Path(args.input_folder).iterdir())
            if p.is_file() and p.suffix.lower() in EXTENSIONS
        ]
    csv_done = load_csv_done(args.csv_output)
    todo = [p for p in papers if not is_done(args, p, csv_done)]

    # Progress goes to stderr, so that a printed result can be piped.
    print(f"{len(todo)} documents to process ({len(papers) - len(todo)} already done)", file=sys.stderr)
    papers = todo
    if not papers:
        return
    model = load_model(args)
    failures = 0
    for i, path in enumerate(papers, 1):
        success, message = run_one(args, model, path)
        failures += not success
        print(f"[{i}/{len(papers)}] {message}", file=sys.stderr, flush=True)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
