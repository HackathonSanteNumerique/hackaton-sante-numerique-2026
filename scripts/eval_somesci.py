"""Evaluate Baguette and Softcite on SoMeSci (https://huggingface.co/datasets/SoFairOA/somesci_dataset).

Documentation: evaluation/README.md

SoMeSci is gated: accept its conditions on the Hugging Face page, and log in with a
token that can read gated repositories (`hf auth login`).

Three steps, one config at a time (pubmed_fulltext, plos_methods, plos_sentences):

1. Write the gold annotations and the Baguette inputs:
    uv run python scripts/eval_somesci.py prepare        # all configs into data/somesci
    uv run python scripts/eval_somesci.py prepare --source ~/Downloads/somesci_dataset   # a local copy

   Methods sections and full papers are split into paragraphs (each line), in the folders
   <config>-paragraphs; --split blocks gives the inputs of the first runs, in <config>.

2. Run Baguette with the client of lm-inference (resumable, see models/README.md):
    python lm-inference/deployments/baguette/baguette_client.py --endpoint $URL \\
        --input-folder data/somesci/input/plos_methods-paragraphs \\
        --output-dir data/somesci/baguette/plos_methods-paragraphs \\
        --csv-output data/somesci/baguette/plos_methods-paragraphs.csv --threads 4 --no-analyze

   or run Softcite (the text service of the Hugging Face Space; resumable):
    uv run python scripts/eval_somesci.py softcite --config plos_methods

3. Score the outputs, with 95% bootstrap intervals:
    uv run python scripts/eval_somesci.py evaluate --config plos_methods                    # Baguette
    uv run python scripts/eval_somesci.py evaluate --config plos_methods --tool softcite
    uv run python scripts/eval_somesci.py evaluate --config plos_methods --split blocks     # the first runs

Gold software are the APPLICATION, PLUGIN, PROGRAMMINGENVIRONMENT and OPERATINGSYSTEM
entities; SOFTWARECOREFERENCE ("the software") is left out. Two levels are scored,
micro-averaged, with one-to-one matching:

- document: the software of the doc (the dataset's `software` field) against the unique
  predicted names. exact: same normalised name (or alternative name / abbreviation);
  relaxed: the words of one name are all in the other ("SPSS" ~ "IBM SPSS Statistics").
- mention: predicted spans against the gold spans. Softcite gives offsets; Baguette does not,
  so every occurrence of one of its names in the text is a predicted span. strict: same
  offsets; overlap: the spans overlap. A name that is not in the text counts as one false positive. Predicted spans that only hit an abbreviation or
  alternative name are not counted.

Versions are scored on the software found (relaxed): the `version` field and the numbers of the
predicted name, against the gold versions. --exclude-os leaves the operating systems out.

SoMeSci on Hugging Face has no mention types (usage, creation...), so the roles (Baguette) and
the used / created / shared attributes (Softcite) are not scored.
"""

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
from huggingface_hub import hf_hub_download

REPO_ID = "SoFairOA/somesci_dataset"
CONFIGS = ["pubmed_fulltext", "plos_methods", "plos_sentences"]  # "default" is pubmed_fulltext
DEFAULT_DIR = Path(__file__).resolve().parent.parent / "data" / "somesci"
SOFTCITE_URL = "https://lfoppiano-softcite-software-mentions.hf.space"
TOOLS = ["baguette", "softcite"]
SPLITS = ["paragraphs", "blocks"]
LEVELS = ["doc_exact", "doc_relaxed", "mention_strict", "mention_overlap", "version"]

LABELS = ["O"] + [
    f"{prefix}-{entity}"
    for entity in [
        "PROGRAMMINGENVIRONMENT", "SOFTWARECOREFERENCE", "APPLICATION", "PLUGIN", "OPERATINGSYSTEM",
        "ALTERNATIVENAME", "URL", "ABBREVIATION", "LICENSE", "CITATION", "VERSION", "EXTENSION",
        "RELEASE", "DEVELOPER",
    ]
    for prefix in "BI"
]
SOFTWARE_TYPES = {"APPLICATION", "PLUGIN", "PROGRAMMINGENVIRONMENT", "OPERATINGSYSTEM"}
ALIAS_TYPES = {"ABBREVIATION", "ALTERNATIVENAME"}


# ---------------------------------------------------------------- prepare


def decode_bio(text, tokens, starts, labels):
    """Entities {start, end, label, text} of a BIO-tagged document."""
    entities = []
    current = None
    for token, start, label_id in zip(tokens, starts, labels):
        label = LABELS[label_id]
        start = int(start)
        end = start + len(token)
        if label.startswith("I-") and current and current["label"] == label[2:]:
            current["end"] = end
            continue
        if current:
            entities.append(current)
        current = {"start": start, "end": end, "label": label[2:]} if label != "O" else None
    if current:
        entities.append(current)
    for entity in entities:
        entity["text"] = text[entity["start"]:entity["end"]]
    return entities


def split_paragraphs(text):
    """Paragraphs of a full paper: the blocks between blank lines, or the lines when there is none.
    The server only takes a 'paragraphs' list in a JSON input, and splits the long ones itself."""
    blocks = re.split(r"\n\s*\n", text)
    if len(blocks) == 1:
        blocks = text.split("\n")
    return [block.strip() for block in blocks if block.strip()] or [text]


def paragraphs_of(text, config, split):
    """The paragraphs sent to the tools.
    paragraphs: each line of the text, the paragraphs of SoMeSci, as GROBID paragraphs on PEPR.
    blocks (the first runs): a methods section in one block, a full paper split at blank lines.
    A sentence is always one block."""
    if config == "plos_sentences":
        return [text]
    if split == "blocks":
        return split_paragraphs(text) if config == "pubmed_fulltext" else [text]
    return [line.strip() for line in text.split("\n") if line.strip()] or [text]


def run_name(config, split):
    """Folder name of the inputs and outputs of a config. The paragraph split has its own folders,
    so that the outputs of the first runs (blocks) are kept apart and a resumed run never mixes them."""
    return config if split == "blocks" or config == "plos_sentences" else f"{config}-paragraphs"


def safe_name(doc_id, used):
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", str(doc_id)).strip("_") or "doc"
    candidate, i = name, 1
    while candidate in used:
        i += 1
        candidate = f"{name}_{i}"
    used.add(candidate)
    return candidate


def to_list(value):
    return [] if value is None else list(value)


def plain(value):
    """A parquet value (numpy array, list or scalar) as plain Python."""
    if value is None or isinstance(value, str):
        return value
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    return value


def software_records(value):
    """The `software` field as a list of records. A Sequence of dicts is stored as a dict of lists
    ({"name": [...], "type": [...], ...}), but a list of dicts is accepted too."""
    if value is None:
        return []
    if isinstance(value, dict):
        columns = {key: to_list(column) for key, column in value.items()}
        size = max((len(column) for column in columns.values()), default=0)
        return [{key: plain(column[i]) if i < len(column) else None for key, column in columns.items()}
                for i in range(size)]
    return [{key: plain(v) for key, v in record.items()} for record in to_list(value)]


def local_parquet(source, config):
    """Parquet file of a config in a local copy of the dataset: <config>/*.parquet, or a file named after it."""
    candidates = sorted((source / config).glob("*.parquet")) + sorted(source.rglob(f"*{config}*.parquet"))
    candidates += sorted(p for p in source.rglob("*.parquet") if config in p.parts)
    if not candidates:
        raise SystemExit(f"no parquet file for {config} in {source}")
    return candidates[0]


def prepare(args):
    gold_dir = args.out / "gold"
    gold_dir.mkdir(parents=True, exist_ok=True)
    for config in args.config:
        if args.source:
            parquet = local_parquet(args.source, config)
        else:
            parquet = hf_hub_download(REPO_ID, f"{config}/test-00000-of-00001.parquet", repo_type="dataset")
        print(f"{config}: reading {parquet}")
        df = pd.read_parquet(parquet)
        input_dir = args.out / "input" / run_name(config, args.split)
        input_dir.mkdir(parents=True, exist_ok=True)
        used, mismatches, n_entities, sizes = set(), 0, 0, []
        with open(gold_dir / f"{config}.jsonl", "w", encoding="utf-8") as gold:
            for row in df.itertuples(index=False):
                tokens = to_list(row.tokens)
                entities = decode_bio(row.text, tokens, to_list(row.start_offsets), to_list(row.labels))
                n_entities += len(entities)
                # A span is checked against its tokens, without spaces (tokens may be separated by several)
                for entity in entities:
                    covered = [t for t, s in zip(tokens, row.start_offsets) if entity["start"] <= s < entity["end"]]
                    if re.sub(r"\s", "", entity["text"]) != "".join(covered).replace(" ", ""):
                        mismatches += 1
                software = software_records(row.software)
                name = safe_name(row.id, used)
                gold.write(json.dumps({"id": row.id, "file": name, "text": row.text,
                                       "entities": entities, "software": software}, ensure_ascii=False) + "\n")
                paragraphs = paragraphs_of(row.text, config, args.split)
                sizes.append([len(paragraph.split()) for paragraph in paragraphs])
                (input_dir / f"{name}.json").write_text(json.dumps({"paragraphs": paragraphs}, ensure_ascii=False),
                                                        encoding="utf-8")
        print(f"{config}: {len(df)} documents, {n_entities} entities, {mismatches} span/token mismatches "
              f"-> {gold_dir / f'{config}.jsonl'}, {input_dir}")
        words = [n for doc in sizes for n in doc]
        single = sum(len(doc) == 1 for doc in sizes)
        print(f"  {args.split}: {len(words)} paragraphs, {np.median([len(d) for d in sizes]):.0f} per document "
              f"({single} documents in one paragraph), {np.median(words):.0f} words per paragraph (max {max(words)})")
        if config != "plos_sentences" and args.split == "paragraphs" and single > len(sizes) / 2:
            print("  warning: most texts have no line breaks, so they are not split into paragraphs")


# ---------------------------------------------------------------- softcite


def softcite_request(url, text, timeout, retries, wait):
    """Mentions of a text by the Softcite service; retries when the service is busy (503) or fails."""
    data = urllib.parse.urlencode({"text": text}).encode()
    request = urllib.request.Request(f"{url.rstrip('/')}/service/processSoftwareText", data=data)
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read()
            return json.loads(body) if body.strip() else {"mentions": []}
        except urllib.error.HTTPError as error:
            if error.code < 500 or attempt == retries:
                raise
            reason = f"HTTP {error.code}"
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            if attempt == retries:
                raise
            reason = str(getattr(error, "reason", error)) or type(error).__name__
        print(f"  {reason}, retry {attempt + 1}/{retries} in {wait} s", flush=True)
        time.sleep(wait)


def shift_mention(mention, offset, text):
    """Offsets of a mention of a paragraph, made relative to the document. A name whose offsets do
    not fall on its raw form is searched for around them."""
    for key in ("software-name", "version", "publisher", "url", "language"):
        component = mention.get(key)
        if not isinstance(component, dict) or not isinstance(component.get("offsetStart"), int):
            continue
        start, end = component["offsetStart"] + offset, component["offsetEnd"] + offset
        raw = component.get("rawForm") or ""
        if raw and text[start:end] != raw:
            found = text.find(raw, max(0, start - 50))
            if found >= 0:
                start, end = found, found + len(raw)
        component["offsetStart"], component["offsetEnd"] = start, end
    return mention


def softcite_document(doc, config, args):
    paragraphs = paragraphs_of(doc["text"], config, args.split)
    mentions, cursor, response = [], 0, {}
    for paragraph in paragraphs:
        start = doc["text"].find(paragraph, cursor)
        if start < 0:
            start = doc["text"].find(paragraph)
        cursor = start + len(paragraph)
        response = softcite_request(args.endpoint, paragraph, args.timeout, args.retries, args.retry_wait)
        mentions += [shift_mention(m, start, doc["text"]) for m in response.get("mentions", [])]
    return {"application": response.get("application"), "version": response.get("version"),
            "id": doc["id"], "paragraphs": len(paragraphs), "mentions": mentions}


def softcite(args):
    """Runs Softcite on the documents of a config; the documents already done are skipped."""
    docs = [json.loads(line) for line in (args.data / "gold" / f"{args.config}.jsonl").open(encoding="utf-8")]
    out_dir = args.output_dir or args.data / "softcite" / run_name(args.config, args.split)
    out_dir.mkdir(parents=True, exist_ok=True)
    todo = [d for d in docs if not (out_dir / f"{d['file']}.software.json").exists()]
    print(f"{run_name(args.config, args.split)}: {len(todo)} documents to process "
          f"({len(docs) - len(todo)} already done) -> {out_dir}")
    if not todo:
        return
    # One short request first, so that a service that does not answer is seen before the documents;
    # a busy or sleeping Space (503) gets the usual retries
    print(f"checking {args.endpoint} ...", flush=True)
    try:
        softcite_request(args.endpoint, "Analyses were done with SPSS.", args.timeout, args.retries, args.retry_wait)
    except Exception as error:  # noqa: BLE001
        raise SystemExit(f"Softcite does not answer at {args.endpoint}: {error}")
    failed = 0
    pool = ThreadPoolExecutor(max_workers=args.threads)
    try:
        futures = {pool.submit(softcite_document, doc, args.config, args): doc for doc in todo}
        for n, future in enumerate(as_completed(futures), 1):
            doc = futures[future]
            try:
                result = future.result()
            except Exception as error:  # noqa: BLE001 - the document is retried on the next run
                failed += 1
                print(f"[{n}/{len(todo)}] {doc['file']}: FAILED ({error})", flush=True)
                continue
            # Written under another name first: an interrupted run never leaves a half-written output
            path = out_dir / f"{doc['file']}.software.json"
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(path)
            print(f"[{n}/{len(todo)}] {doc['file']}: {len(result['mentions'])} mentions", flush=True)
    except KeyboardInterrupt:
        # Without waiting for the requests in progress; the documents done are kept
        print("\ninterrupted: run the same command again to continue", flush=True)
        os._exit(130)
    pool.shutdown()
    print(f"{len(todo) - failed} done, {failed} failed -> {out_dir}" + (" (run again to retry)" if failed else ""))


# ---------------------------------------------------------------- evaluate


def normalise(name):
    name = re.sub(r"\s+", " ", (name or "").lower()).strip()
    return name.strip(" .,;:()[]{}'\"")


def words(name):
    return set(re.findall(r"\w+", normalise(name)))


def match_score(pred, aliases):
    """2: exact match with one of the aliases, 1: relaxed match, 0: none."""
    p = normalise(pred)
    if p in {normalise(a) for a in aliases}:
        return 2
    pw = words(pred)
    for alias in aliases:
        aw = words(alias)
        if pw and aw and (pw <= aw or aw <= pw):
            return 1
    return 0


def greedy(pairs):
    """One-to-one matching of (score, i, j) pairs, best scores first."""
    used_i, used_j, matched = set(), set(), []
    for score, i, j in sorted(pairs, key=lambda x: -x[0]):
        if i not in used_i and j not in used_j:
            used_i.add(i)
            used_j.add(j)
            matched.append((score, i, j))
    return matched


def strip_version(name, version):
    if version and normalise(name).endswith(normalise(version)):
        name = name[: len(name) - len(version)]
    return re.sub(r"\s+(v(ersion)?\.?\s*)?\d[\w.\-]*$", "", name.strip(), flags=re.I).strip()


VERSION_PREFIX = re.compile(r"^(version|ver\.?|v\.?|release|rel\.?|build|r)\s*(?=\d)", re.I)


def normalise_version(version):
    """'Version 2.15', 'v.2.15' and '2.15' are the same version."""
    return VERSION_PREFIX.sub("", normalise(version)).strip()


def predicted_versions(name, version, aliases):
    """Versions of a prediction: its `version` field and the numbers of its name that are not in the
    name of the software ('SPSS 22' -> 22, but not the 3 of '3D Slicer')."""
    versions = {normalise_version(version)} if version else set()
    alias_words = set().union(*(words(a) for a in aliases))
    for token in re.findall(r"(?<![\w.])[vr]?\.?\d[\w.\-]*", name, flags=re.I):
        if normalise(token) not in alias_words:
            versions.add(normalise_version(token))
    return {v for v in versions if v}


def find_spans(name, text):
    pattern = r"\s+".join(re.escape(part) for part in name.split())
    return [(m.start(), m.end()) for m in re.finditer(rf"(?<!\w){pattern}(?!\w)", text, flags=re.I)]


def locate(predictions, text):
    """Predicted spans of the unique names, the longest first, and the names not found."""
    spans, missing = [], []
    for name, version in predictions:
        found = find_spans(name, text) if name.strip() else []
        if not found:
            short = strip_version(name, version)
            if short and short != name:
                found = find_spans(short, text)
        if found:
            spans.extend((s, e, name) for s, e in found)
        else:
            missing.append(name)
    return keep_longest(spans), missing


def keep_longest(spans):
    """Spans without overlaps: of two overlapping spans, the longer one is kept."""
    kept = []
    for s, e, name in sorted(spans, key=lambda x: (x[0] - x[1], x[0])):
        if all(e <= ks or s >= ke for ks, ke, _ in kept):
            kept.append((s, e, name))
    return sorted(kept)


def add_unique(unique, name, version):
    """Names unique by normalised form; the first mention is kept, or the first one with a version."""
    key = normalise(name)
    if key and (key not in unique or (version and not unique[key][1])):
        unique[key] = (name, version)


def load_baguette(path, explicit_only):
    """(name, version) of the software mentions, unique by normalised name. No offsets."""
    data = json.loads(path.read_text(encoding="utf-8"))
    unique = {}
    for paragraph in data.get("paragraphs", []):
        for mention in paragraph.get("software", []) or []:
            if not isinstance(mention, dict) or not isinstance(mention.get("name"), str):
                continue
            if explicit_only and mention.get("explicit_or_implicit") == "implicit":
                continue
            version = mention.get("version") if isinstance(mention.get("version"), str) else None
            add_unique(unique, mention["name"], version)
    return list(unique.values()), None


def load_softcite(path, explicit_only):
    """(name, version) of the software mentions, unique by normalised name, and their spans."""
    data = json.loads(path.read_text(encoding="utf-8"))
    unique, spans = {}, []
    for mention in data.get("mentions", []):
        if mention.get("type", "software") != "software":
            continue
        if explicit_only and mention.get("software-type") == "implicit":
            continue
        name = mention.get("software-name") or {}
        if not isinstance(name.get("rawForm"), str):
            continue
        version = (mention.get("version") or {}).get("rawForm")
        add_unique(unique, name["rawForm"], version if isinstance(version, str) else None)
        if isinstance(name.get("offsetStart"), int) and isinstance(name.get("offsetEnd"), int):
            spans.append((name["offsetStart"], name["offsetEnd"], name["rawForm"]))
    return list(unique.values()), keep_longest(spans)


LOADERS = {"baguette": load_baguette, "softcite": load_softcite}
OUTPUT_NAMES = {"baguette": ["{}.json.json", "{}.json"], "softcite": ["{}.software.json"]}


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4), "tp": tp, "fp": fp, "fn": fn}


def bootstrap(per_doc, samples, seed):
    """95% intervals of P, R and F1: the documents are drawn again with replacement, `samples` times.
    A sample where a score is undefined (e.g. no version at all) is left out of its interval."""
    counts = np.array(per_doc, dtype=float)  # one row per document: tp, fp, fn
    rng = np.random.default_rng(seed)
    tp, fp, fn = counts[rng.integers(0, len(counts), (samples, len(counts)))].sum(axis=1).T
    with np.errstate(divide="ignore", invalid="ignore"):
        scores = {"precision": tp / (tp + fp), "recall": tp / (tp + fn), "f1": 2 * tp / (2 * tp + fp + fn)}
    intervals = {}
    for name, values in scores.items():
        values = values[np.isfinite(values)]
        intervals[name] = ([round(float(np.percentile(values, 2.5)), 4), round(float(np.percentile(values, 97.5)), 4)]
                           if len(values) else None)
    return intervals


def output_file(predictions_dir, name, tool):
    for pattern in OUTPUT_NAMES[tool]:
        if (predictions_dir / pattern.format(name)).exists():
            return predictions_dir / pattern.format(name)
    return None


def gold_software(doc):
    """Software of the doc: the `software` field, or the BIO entities when it is empty."""
    records = []
    for record in doc["software"]:
        if "COREFERENCE" in (record.get("type") or "").upper():
            continue
        aliases = [record.get("name"), record.get("alternativename")] + list(record.get("abbreviation") or [])
        aliases = [a for a in aliases if a and normalise(a)]
        if aliases:
            records.append({"name": aliases[0], "aliases": aliases, "type": (record.get("type") or "").upper(),
                            "version": [v for v in record.get("version") or [] if v]})
    if not records:
        seen = {}
        for entity in doc["entities"]:
            if entity["label"] in SOFTWARE_TYPES:
                seen.setdefault(normalise(entity["text"]), entity)
        records = [{"name": e["text"], "aliases": [e["text"]], "type": e["label"], "version": []}
                   for e in seen.values()]
    return records


def evaluate(args):
    ignored_types = {"OPERATINGSYSTEM"} if args.exclude_os else set()
    gold_path = args.data / "gold" / f"{args.config}.jsonl"
    run = run_name(args.config, args.split)
    predictions_dir = args.predictions_dir or args.data / args.tool / run
    docs = [json.loads(line) for line in gold_path.open(encoding="utf-8")]

    counts = defaultdict(Counter)
    per_doc = defaultdict(list)  # level -> (tp, fp, fn) of each document, for the bootstrap
    type_recall = defaultdict(Counter)
    mention_type_recall = defaultdict(Counter)
    missing_files, not_in_text, n_names = [], 0, 0
    errors = []

    for doc in docs:
        doc_counts = defaultdict(Counter)
        path = output_file(predictions_dir, doc["file"], args.tool)
        if path is None:
            missing_files.append(doc["id"])
            predictions, predicted_spans = [], []
        else:
            predictions, predicted_spans = LOADERS[args.tool](path, args.explicit_only)
        n_names += len(predictions)

        # Document level
        # With --exclude-os, the operating systems are left out of the gold, and the names that match one
        # are not counted (neither true nor false positives)
        all_gold = gold_software(doc)
        gold = [g for g in all_gold if g["type"] not in ignored_types]
        ignored = {i for i, (name, _) in enumerate(predictions)
                   if any(match_score(name, g["aliases"]) for g in all_gold if g["type"] in ignored_types)}
        pairs = [(score, i, j) for i, (name, _) in enumerate(predictions) for j, g in enumerate(gold)
                 if (score := match_score(name, g["aliases"]))]
        for level, min_score in (("doc_exact", 2), ("doc_relaxed", 1)):
            matched = greedy([p for p in pairs if p[0] >= min_score])
            # Another name of a software already matched (e.g. its abbreviation) is not a false positive
            matched_i, matched_j = {i for _, i, _ in matched}, {j for _, _, j in matched}
            extra = {i for score, i, j in pairs if score >= min_score and j in matched_j and i not in matched_i}
            extra |= ignored - matched_i
            doc_counts[level].update(tp=len(matched), fp=len(predictions) - len(matched) - len(extra),
                                 fn=len(gold) - len(matched))
            if level == "doc_relaxed":
                relaxed, relaxed_extra = matched, extra
                for _, _, j in matched:
                    type_recall[gold[j]["type"]]["tp"] += 1
                for g in gold:
                    type_recall[g["type"]]["total"] += 1
        # Versions of the software found (relaxed): predicted versions against the gold versions
        version_errors = []
        for _, i, j in relaxed:
            name, version = predictions[i]
            predicted = predicted_versions(name, version, gold[j]["aliases"])
            expected = {normalise_version(v) for v in gold[j]["version"]} - {""}
            doc_counts["version"].update(tp=len(predicted & expected), fp=len(predicted - expected),
                                     fn=len(expected - predicted))
            if predicted != expected:
                version_errors.append({"software": gold[j]["name"], "predicted_name": name,
                                       "gold": sorted(expected), "predicted": sorted(predicted)})

        # Mention level
        gold_spans = [e for e in doc["entities"] if e["label"] in SOFTWARE_TYPES - ignored_types]
        alias_spans = [e for e in doc["entities"] if e["label"] in ALIAS_TYPES | ignored_types]
        # Softcite gives the offsets; for Baguette, the names are searched in the text
        if predicted_spans is None:
            spans, missing = locate(predictions, doc["text"])
        else:
            spans, missing = predicted_spans, []
        not_in_text += len(missing)
        spans = [s for s in spans
                 if any(s[0] < g["end"] and g["start"] < s[1] for g in gold_spans)
                 or not any(s[0] < a["end"] and a["start"] < s[1] for a in alias_spans)]
        strict = greedy([(1, i, j) for i, s in enumerate(spans) for j, g in enumerate(gold_spans)
                         if (s[0], s[1]) == (g["start"], g["end"])])
        overlap = greedy([(min(s[1], g["end"]) - max(s[0], g["start"]), i, j)
                          for i, s in enumerate(spans) for j, g in enumerate(gold_spans)
                          if s[0] < g["end"] and g["start"] < s[1]])
        for level, matched in (("mention_strict", strict), ("mention_overlap", overlap)):
            doc_counts[level].update(tp=len(matched), fp=len(spans) - len(matched) + len(missing),
                                 fn=len(gold_spans) - len(matched))
        for j in {j for _, _, j in overlap}:
            mention_type_recall[gold_spans[j]["label"]]["tp"] += 1
        for g in gold_spans:
            mention_type_recall[g["label"]]["total"] += 1

        for level in LEVELS:
            c = doc_counts[level]
            counts[level].update(c)
            per_doc[level].append((c["tp"], c["fp"], c["fn"]))

        # Errors, at document level (relaxed)
        fp = [predictions[i][0] for i in range(len(predictions))
              if i not in {i for _, i, _ in relaxed} and i not in relaxed_extra]
        fn = [gold[j]["name"] for j in range(len(gold)) if j not in {j for _, _, j in relaxed}]
        if fp or fn or version_errors:
            errors.append({"id": doc["id"], "file": doc["file"], "false_positives": fp, "false_negatives": fn,
                           "not_in_text": missing, "version_errors": version_errors})

    metrics = {level: prf(counts[level]["tp"], counts[level]["fp"], counts[level]["fn"]) for level in LEVELS}
    if args.bootstrap and docs:
        for level in LEVELS:
            metrics[level]["ci95"] = bootstrap(per_doc[level], args.bootstrap, args.seed)
    result = {
        "config": args.config,
        "split": args.split,
        "run": run,
        "tool": args.tool,
        "predictions_dir": str(predictions_dir),
        "explicit_only": args.explicit_only,
        "exclude_os": args.exclude_os,
        "bootstrap": {"samples": args.bootstrap, "seed": args.seed} if args.bootstrap else None,
        "documents": len(docs),
        "missing_outputs": len(missing_files),
        "predicted_names": n_names,
        "names_not_in_text": not_in_text,
        "metrics": metrics,
        "recall_by_type": {
            "document_relaxed": {t: round(c["tp"] / c["total"], 4) for t, c in type_recall.items() if c["total"]},
            "mention_overlap": {t: round(c["tp"] / c["total"], 4) for t, c in mention_type_recall.items()},
            "gold_counts": {t: c["total"] for t, c in type_recall.items()},
        },
        "missing_output_ids": missing_files,
        "errors": errors,
    }

    print(f"{args.tool} on {run}: {len(docs)} documents, {len(missing_files)} without output, "
          f"{n_names} predicted names ({not_in_text} not found in the text)")
    if args.bootstrap:
        print(f"95% intervals of F1: {args.bootstrap} bootstrap samples of the documents")
    print(f"{'level':<16} {'P':>7} {'R':>7} {'F1':>7} {'F1 95%':>13} {'TP':>6} {'FP':>6} {'FN':>6}")
    for level in LEVELS:
        m = metrics[level]
        ci = "{:.3f}-{:.3f}".format(*m["ci95"]["f1"]) if m.get("ci95", {}).get("f1") else ""
        print(f"{level:<16} {m['precision']:>7.3f} {m['recall']:>7.3f} {m['f1']:>7.3f} {ci:>13} "
              f"{m['tp']:>6} {m['fp']:>6} {m['fn']:>6}")
    print("recall by type (document relaxed / mention overlap):")
    for t in sorted(set(type_recall) | set(mention_type_recall)):
        doc_r = result["recall_by_type"]["document_relaxed"].get(t, float("nan"))
        men_r = result["recall_by_type"]["mention_overlap"].get(t, float("nan"))
        print(f"  {t:<24} {doc_r:.3f} / {men_r:.3f}")

    out = args.out or args.data / "results" / args.tool / f"{run}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {out}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("prepare", help="write the gold annotations and the Baguette inputs")
    p.add_argument("--config", nargs="+", choices=CONFIGS, default=CONFIGS)
    p.add_argument("--out", type=Path, default=DEFAULT_DIR, help=f"output directory (default: {DEFAULT_DIR})")
    p.add_argument("--source", type=Path,
                   help="local copy of the dataset (<config>/test-00000-of-00001.parquet); default: download it")
    p.add_argument("--split", choices=SPLITS, default="paragraphs",
                   help="paragraphs (default): each line of a methods section or full paper, as on PEPR; "
                        "blocks: a methods section in one block, a full paper at blank lines (the first runs)")
    p.set_defaults(func=prepare)

    s = sub.add_parser("softcite", help="run Softcite on the documents of one config")
    s.add_argument("--config", required=True, choices=CONFIGS)
    s.add_argument("--data", type=Path, default=DEFAULT_DIR, help=f"directory of prepare (default: {DEFAULT_DIR})")
    s.add_argument("--endpoint", default=SOFTCITE_URL, help=f"Softcite service (default: {SOFTCITE_URL})")
    s.add_argument("--split", choices=SPLITS, default="paragraphs", help="as for prepare")
    s.add_argument("--output-dir", type=Path, help="Softcite outputs (default: <data>/softcite/<run>)")
    s.add_argument("--threads", type=int, default=2, help="parallel requests (default: 2, the Space is shared)")
    s.add_argument("--timeout", type=int, default=120, help="seconds per request (default: 120)")
    s.add_argument("--retries", type=int, default=5, help="retries on 5xx errors and timeouts")
    s.add_argument("--retry-wait", type=int, default=10, help="seconds between retries")
    s.set_defaults(func=softcite)

    e = sub.add_parser("evaluate", help="score the outputs of a tool on one config")
    e.add_argument("--config", required=True, choices=CONFIGS)
    e.add_argument("--tool", choices=TOOLS, default="baguette", help="the tool to score (default: baguette)")
    e.add_argument("--split", choices=SPLITS, default="paragraphs", help="as for prepare: which run to score")
    e.add_argument("--data", type=Path, default=DEFAULT_DIR, help=f"directory of prepare (default: {DEFAULT_DIR})")
    e.add_argument("--predictions-dir", "--baguette-dir", type=Path,
                   help="outputs of the tool (default: <data>/<tool>/<run>)")
    e.add_argument("--explicit-only", action="store_true",
                   help="leave out the implicit mentions (Baguette: implicit, Softcite: software-type implicit)")
    e.add_argument("--exclude-os", action="store_true",
                   help="leave the operating systems out of the gold, and do not count the names that match one")
    e.add_argument("--bootstrap", type=int, default=1000,
                   help="bootstrap samples for the 95%% intervals (default: 1000; 0: no intervals)")
    e.add_argument("--seed", type=int, default=0, help="seed of the bootstrap (default: 0)")
    e.add_argument("--out", type=Path, help="JSON results (default: <data>/results/<tool>/<run>.json)")
    e.set_defaults(func=evaluate)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
