# Evaluation: Baguette, Softcite and bio2flow on SoMeSci

[`scripts/eval_somesci.py`](../scripts/eval_somesci.py) measures how well [Baguette](../models/README.md#baguette-dataesr), [Softcite](../models/README.md#softcite-software-mentions) and bio2flow, the paper-text NER of [CoPaLink](../models/README.md#copalink), find software mentions, with precision, recall and F1 against the human annotations of [SoMeSci](../datasets/README.md#somesci). It uses the version converted by SoFAIR on 🤗 [`SoFairOA/somesci_dataset`](https://huggingface.co/datasets/SoFairOA/somesci_dataset).

Three steps, one config at a time:

1. `prepare`: write the gold annotations and the Baguette inputs.
2. Run the tools: Baguette with the batch client of [lm-inference](../models/README.md#lm-inference), Softcite with the `softcite` command of the script, bio2flow with [`copalink_client.py`](../scripts/copalink_client.py).
3. `evaluate --tool baguette|softcite|bio2flow`: score the outputs. All the tools get the same metrics, so they can be compared.

## The data

The dataset only has a `test` split, in three configs:

| Config | Documents | What a document is |
|---|---|---|
| `plos_sentences` | 677 | a sentence |
| `plos_methods` | 480 | the methods section of a PLoS paper |
| `pubmed_fulltext` | 97 | a full PMC paper |

The `default` config is a copy of `pubmed_fulltext`.

- **Annotations:** BIO tags on tokens, with the character offset of each token, plus a `software` list per document: name, type, alternative name, abbreviation, version, developer, URL…
- **Software types:** `APPLICATION`, `PLUGIN`, `PROGRAMMINGENVIRONMENT`, `OPERATINGSYSTEM`, `SOFTWARECOREFERENCE`.
- **No mention types:** this version has no usage / creation / deposition / mention, so neither Baguette's `role` nor Softcite's `used` / `created` / `shared` is scored. The original SoMeSci (brat files on Zenodo) has them.
- **Gated:** accept the conditions on the dataset page. To download with the script, log in with `hf auth login`, using a token allowed to read gated repositories (fine-grained tokens: tick *public gated repositories*). Or download the parquet files yourself and use `--source`.

## 1. Prepare

```bash
uv run python scripts/eval_somesci.py prepare                           # downloads the three configs
uv run python scripts/eval_somesci.py prepare --source data/somesci/    # a local copy of the dataset
uv run python scripts/eval_somesci.py prepare --config plos_sentences   # only some configs
uv run python scripts/eval_somesci.py prepare --split blocks            # the inputs of the first runs
```

- **`--source`:** a folder with the layout of the 🤗 repo (`<config>/test-00000-of-00001.parquet`). A parquet file with the config in its name also works.
- **`--out`:** where to write; default `data/somesci/`, which is not in git.
- **`--split`:** how methods sections and full papers are cut into the paragraphs sent to the tools. Sentences are always one block.

| `--split` | Methods section | Full paper | Folder (`<run>`) |
|---|---|---|---|
| `paragraphs` (default) | one paragraph per line of the text | one paragraph per line | `<config>-paragraphs` |
| `blocks` (the first runs) | one block | the blocks between blank lines, which in SoMeSci are sections | `<config>` |

`paragraphs` is the fair choice: SoMeSci writes one paragraph per line, so both tools get paragraphs, as they do on the PEPR corpus with GROBID. The two splits have their own folders, so that outputs of different inputs are never mixed (the Baguette client skips the documents already in its CSV).

It writes:

- **`gold/<config>.jsonl`:** one document per line, with `id`, `file` (the file name used for the document), `text`, `entities` (`start`, `end`, `label`, `text`) and `software`. The `softcite` command reads its documents from here.
- **`input/<run>/<file>.json`:** the Baguette input, `{"paragraphs": [...]}`, split as above. The server still cuts paragraphs longer than about 200 tokens into pieces.

It prints, per config:

- the number of documents and entities, and the number of span/token mismatches, which should be 0;
- the number of paragraphs, per document and their length in words. If most methods sections or full papers come out as one paragraph, the texts have no line breaks and a warning says so: then `paragraphs` changes nothing.

## 2a. Run Baguette

Use the batch client of lm-inference, with the `--no-analyze` option (the article-level step is not needed):

```bash
URL=https://sciencialab--baguette-software-dataset-app-extract-endpoint.modal.run/
for r in plos_sentences plos_methods-paragraphs pubmed_fulltext-paragraphs; do
  python lm-inference/deployments/baguette/baguette_client.py --endpoint $URL \
    --input-folder data/somesci/input/$r \
    --output-dir data/somesci/baguette/$r \
    --csv-output data/somesci/baguette/$r.csv --threads 4 --no-analyze
done
```

The folders are the `<run>` names of `prepare`. `plos_sentences` is the same with both splits: there is no need to run it again.

- **How many calls:** 1,254 documents in all, each a call to the GPU service. Try a few first, especially the full papers.
- **Resuming:** `--csv-output` makes the run resumable. A second run skips the documents that succeeded and retries the failed ones.
- **Output:** one `<file>.json.json` per document.

## 2b. Run Softcite

The `softcite` command sends the text of each document to the text service of Softcite (`/service/processSoftwareText`), by default the hackathon [🤗 Space](../models/README.md#softcite-software-mentions):

```bash
for c in plos_sentences plos_methods pubmed_fulltext; do
  uv run python scripts/eval_somesci.py softcite --config $c      # --split blocks for the first runs
done
```

| Option | Default | |
|---|---|---|
| `--config` | (required) | the config |
| `--data` | `data/somesci` | the `--out` folder of `prepare` |
| `--endpoint` | the 🤗 Space | another Softcite service, e.g. `http://localhost:8060` for a Docker instance |
| `--split` | `paragraphs` | as for `prepare` |
| `--output-dir` | `<data>/softcite/<run>` | where to write |
| `--threads` | 2 | parallel requests; keep it low, the Space is shared by everyone |
| `--timeout`, `--retries`, `--retry-wait` | 120 s, 5, 10 s | a busy Space answers `503`, or does not answer: the request is sent again, and each retry is printed with its reason |

- **What is sent:** the same paragraphs as for Baguette (see `--split`), one request per paragraph. The offsets are moved back to the whole text; if an offset does not fall on its name, the name is searched for near it.
- **Start:** a first short request checks that the service answers, with the usual retries; if it still does not, the command stops with the error.
- **Resuming:** documents already done are skipped. A document whose request failed is not written, so running the command again retries it. Ctrl-C stops at once and keeps the documents done.
- **Output:** one `<file>.software.json` per document, with the `mentions` of Softcite (the JSON schema of the service) and offsets in the text of the document.

## 2c. Run bio2flow

bio2flow is the name of the outputs of the CoPaLink paper-text NER in the [PEPR repo](https://huggingface.co/datasets/HackatonSanteNumerique/pepr-hal-data/tree/main/bio2flow): a SciBERT model trained on CPL-Article, bioinformatics papers annotated with `Tool`. It runs locally with [`scripts/copalink_client.py`](../scripts/copalink_client.py), on the same input folders as Baguette. Set it up once as in [models/README.md](../models/README.md#copalink) (`uv sync --extra copalink` and the `.pt` model of nlp_models), then:

```bash
MODEL=../nlp_models/csebe_scibert_bioinfo_voc_iteration4_seed100.pt   # the model of the PEPR outputs
for r in plos_sentences plos_methods-paragraphs pubmed_fulltext-paragraphs; do
  uv run --extra copalink python scripts/copalink_client.py --model $MODEL \
    --input-folder data/somesci/input/$r \
    --output-dir data/somesci/bio2flow/$r \
    --csv-output data/somesci/bio2flow/$r.csv
done
```

- **What it does:** the client joins the paragraphs of a document with blank lines, predicts the whole document, and gives each entity back to its paragraph, as on PEPR.
- **Device:** GPU when there is one (CUDA, or MPS on a Mac), otherwise the CPU, which takes 15–30 s per PEPR paper on 24 cores. Try a few documents first.
- **Resuming:** the documents that already have their output file are skipped.
- **Output:** one `<file>.json.json` per document: `paragraphs[].entities[]`, with `text`, `type` (`Tool`), `begin` and `end` in the paragraph, and `confidence`.

## 3. Evaluate

```bash
uv run python scripts/eval_somesci.py evaluate --config plos_sentences                     # Baguette
uv run python scripts/eval_somesci.py evaluate --config plos_sentences --tool softcite
uv run python scripts/eval_somesci.py evaluate --config plos_sentences --explicit-only
uv run python scripts/eval_somesci.py evaluate --config plos_sentences --exclude-os
uv run python scripts/eval_somesci.py evaluate --config plos_sentences --tool bio2flow --exclude-types PROGRAMMINGENVIRONMENT OPERATINGSYSTEM
uv run python scripts/eval_somesci.py evaluate --config plos_methods --split blocks   # the first runs
```

| Option | Default | |
|---|---|---|
| `--config` | (required) | `plos_sentences`, `plos_methods` or `pubmed_fulltext` |
| `--tool` | `baguette` | `baguette`, `softcite` or `bio2flow` |
| `--split` | `paragraphs` | which run to score, as for `prepare` |
| `--data` | `data/somesci` | the `--out` folder of `prepare` |
| `--predictions-dir` | `<data>/<tool>/<run>` | the outputs of the tool (`--baguette-dir` still works) |
| `--explicit-only` | off | leave out the implicit mentions: `implicit` for Baguette, `software-type` `implicit` for Softcite; no effect on bio2flow |
| `--exclude-types` | none | leave these software types out of the gold (`APPLICATION`, `PLUGIN`, `PROGRAMMINGENVIRONMENT`, `OPERATINGSYSTEM`); a predicted name that matches one of their software is not counted, neither as a true nor as a false positive |
| `--exclude-os` | off | the same as `--exclude-types OPERATINGSYSTEM` |
| `--bootstrap` | 1000 | samples for the 95% intervals; 0 for none |
| `--seed` | 0 | seed of the bootstrap, so that the intervals can be reproduced |
| `--out` | `<data>/results/<tool>/<run>.json` | the JSON results. With `--explicit-only` or excluded types, the name gets a suffix (e.g. `plos_methods-paragraphs.without-operatingsystem-programmingenvironment.json`), so that the default results are not replaced |

A document without an output of the tool counts as one with no prediction. The number of these is printed, and their ids are in the results.

### What is compared

- **Gold software:** the `APPLICATION`, `PLUGIN`, `PROGRAMMINGENVIRONMENT` and `OPERATINGSYSTEM` entities. `SOFTWARECOREFERENCE` ("the software", "this tool") is left out.
- **Predictions:** the names of the software mentions, made unique per document: for Baguette, the `name` of every mention in `paragraphs[].software`; for Softcite, the `rawForm` of `software-name` of every mention; for bio2flow, the `text` of every `Tool` entity in `paragraphs[].entities` (its `confidence` is not used). When a name is repeated, the first mention is kept, or the first one with a `version`.
- **Normalisation:** lower case, whitespace collapsed, punctuation removed at both ends.

Matching is one-to-one and the scores are micro-averaged over all the documents.

### Document level

The software of a document (its `software` list) against the unique predicted names. A predicted name matches a software if it matches its name, its alternative name or one of its abbreviations.

| Metric | A name matches when |
|---|---|
| `doc_exact` | it is the same after normalisation |
| `doc_relaxed` | all the words of one are in the other: `SPSS` ~ `IBM SPSS Statistics`, `ResearchIR MAX 4.0` ~ `ResearchIR MAX` |

Predicting a software under two of its names, such as `Statistical Parametric Mapping` and `SPM`, gives one true positive. The second name is not counted as a false positive.

### Mention level

**Softcite** gives the offsets of each name: its spans are used as they are. When two of them overlap, the longer one is kept.

**bio2flow** gives the offsets of each entity in its paragraph, as read by the client, which collapses whitespace (several spaces or a line break become one space). The script finds each paragraph in the text with its whitespace collapsed the same way, and moves the offsets back to the text of the document.

**Baguette** gives names without positions. The script searches the text for each predicted name, case-insensitively and as whole words; every occurrence is a predicted span. If the name is not in the text, it searches again without the version (`SPSS v25` → `SPSS`). When two spans overlap, the longer one is kept.

| Metric | A predicted span matches a gold span when |
|---|---|
| `mention_strict` | they have the same offsets |
| `mention_overlap` | they overlap |

- **Names not in the text** (Baguette): a name that is not found in the text, even without its version, counts as one false positive. Such names are paraphrased or invented.
- **Abbreviations:** a span that only falls on an annotated abbreviation or alternative name, such as `SPM` in `Statistical Parametric Mapping (SPM)`, is not counted.

### Versions

`version` is scored only on the software found at document level (relaxed match). For each of them, the predicted versions are compared with the gold versions of the software:

- **Predicted versions:** the version of the mention (Baguette: `version`; Softcite: the `rawForm` of `version`; bio2flow gives none), plus the numbers of the predicted name that are not in the name of the software. `SPSS 22` gives `22`, `MATLAB R2014a` gives `2014a`, but `3D Slicer` gives nothing.
- **Normalisation:** a `version`, `ver.`, `v`, `release`, `build` or `r` prefix is removed, so `Version 2.15`, `v2.15` and `2.15` are the same.
- **Counts:** a predicted version that is a gold version is a true positive, the other predicted versions are false positives, and the gold versions not predicted are false negatives.

A version given for a software that SoMeSci annotates without one is a false positive. That happens when SoMeSci attaches the version to another name of the same software (see [Limits](#limits)).

### Confidence intervals

The scores depend on which documents happen to be in SoMeSci. To see how much, `evaluate` draws the documents of the config again, at random and with replacement, as many times as `--bootstrap` (1000), and computes the scores of each sample. The 95% interval goes from the 2.5th to the 97.5th percentile of these scores. A sample in which a score is undefined, e.g. a version F1 when no software of the sample has a version, is left out.

- **Reading:** a narrow interval means the score would change little with other documents of the same kind. Few documents (97 full papers) give wider intervals than many (677 sentences).
- **Comparing two tools:** if their intervals do not overlap, the difference is clear. If they overlap, it may still be real: the intervals of each tool alone do not tell, because both tools are scored on the same documents.

### Output

The script prints a summary and a table:

```
baguette on plos_methods-paragraphs: 480 documents, <n> without output, <n> predicted names (<n> not found in the text)
95% intervals of F1: 1000 bootstrap samples of the documents
level                  P       R      F1        F1 95%     TP     FP     FN
doc_exact          ...
doc_relaxed        ...
mention_strict     ...
mention_overlap    ...
version            ...
recall by type (document relaxed / mention overlap):
  APPLICATION              ... / ...
```

The JSON results have:

- **`metrics`:** precision, recall, F1, TP, FP and FN for each level, and `ci95`: the 95% intervals of precision, recall and F1.
- **`config`, `split`, `run`, `tool`, `bootstrap`:** what was scored, and how.
- **`recall_by_type`:** recall by software type at both levels, and the number of gold software of each type.
- **`errors`:** per document, the `false_positives` and `false_negatives` at document level (relaxed), the names `not_in_text`, and the `version_errors` (gold software, predicted name, gold and predicted versions). Start the error analysis here.
- **`missing_output_ids`:** the documents without a Baguette output.

## Results

The results, with the comparison of the tools, are in [RESULTS.md](RESULTS.md).

## Limits

- **Roles are not scored:** see [The data](#the-data).
- **Lexical identity:** SoMeSci tells software apart by name, so `SPSS` and `IBM SPSS Statistics` in one paper are two gold software. Finding only one of them gives a false negative.
- **Short names:** at mention level, a short name such as `R` matches every standalone `R` of the text. That can lower the mention-level precision.
- **Mentions lost between pieces:** the server cuts long paragraphs into pieces of about 200 tokens, and a mention split between two pieces can be lost.
- **Inputs:** with `--split paragraphs`, both tools get the paragraphs of SoMeSci. On PEPR, Softcite reads the whole paper and spreads a name found once to its other occurrences; through the text service, paragraph by paragraph, it cannot.
- **No offsets for Baguette:** its mention level is an approximation. It assumes Baguette finds every occurrence of a name it gives once. Softcite's and bio2flow's mention levels use their own offsets, so they are exact. Compare the tools at document level first.
- **bio2flow and versions:** the model only tags `Tool`, so its version scores are 0 by construction: leave them out of comparisons.
- **bio2flow and what a tool is:** CPL-Article, its training corpus, never annotates programming languages, operating systems, containers or workflow managers as `Tool`, though they are written in its articles: R 42 times, Python 24, Linux 11, Docker 66, Nextflow 134, all without annotation. SoMeSci counts R, Python or Linux as software. So bio2flow misses programming environments and operating systems by design. Compare it with the other tools with `--exclude-types PROGRAMMINGENVIRONMENT OPERATINGSYSTEM`, on applications and plugins, which all the tools count as software.
- **Softcite on the 🤗 Space:** the Space is shared and may be slower or busy; scores do not depend on it, but run time does. The version of the service (`application`, `version` in each output) is in the outputs.
