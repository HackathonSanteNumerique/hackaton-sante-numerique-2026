# Evaluation: Baguette and Softcite on SoMeSci

[`scripts/eval_somesci.py`](../scripts/eval_somesci.py) measures how well [Baguette](../models/README.md#baguette-dataesr) and [Softcite](../models/README.md#softcite-software-mentions) find software mentions, with precision, recall and F1 against the human annotations of [SoMeSci](../datasets/README.md#somesci). It uses the version converted by SoFAIR on 🤗 [`SoFairOA/somesci_dataset`](https://huggingface.co/datasets/SoFairOA/somesci_dataset).

Three steps, one config at a time:

1. `prepare`: write the gold annotations and the Baguette inputs.
2. Run the tools: Baguette with the batch client of [lm-inference](../models/README.md#lm-inference), Softcite with the `softcite` command of the script.
3. `evaluate --tool baguette|softcite`: score the outputs. Both tools get the same metrics, so they can be compared.

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
```

- **`--source`:** a folder with the layout of the 🤗 repo (`<config>/test-00000-of-00001.parquet`). A parquet file with the config in its name also works.
- **`--out`:** where to write; default `data/somesci/`, which is not in git.

It writes:

- **`gold/<config>.jsonl`:** one document per line, with `id`, `file` (the file name used for the document), `text`, `entities` (`start`, `end`, `label`, `text`) and `software`. The `softcite` command reads its documents from here.
- **`input/<config>/<file>.json`:** the Baguette input, `{"paragraphs": [...]}`. Sentences and methods sections are one paragraph each. Full papers are split at blank lines, or at line breaks when there is none. The server splits the long paragraphs into pieces of about 200 tokens.

It prints, per config, the number of documents and entities, and the number of span/token mismatches, which should be 0.

## 2a. Run Baguette

Use the batch client of lm-inference, with the `--no-analyze` option (the article-level step is not needed):

```bash
URL=https://sciencialab--baguette-software-dataset-app-extract-endpoint.modal.run/
for c in plos_sentences plos_methods pubmed_fulltext; do
  python lm-inference/deployments/baguette/baguette_client.py --endpoint $URL \
    --input-folder data/somesci/input/$c \
    --output-dir data/somesci/baguette/$c \
    --csv-output data/somesci/baguette/$c.csv --threads 4 --no-analyze
done
```

- **How many calls:** 1,254 documents in all, each a call to the GPU service. Try a few first, especially the full papers.
- **Resuming:** `--csv-output` makes the run resumable. A second run skips the documents that succeeded and retries the failed ones.
- **Output:** one `<file>.json.json` per document.

## 2b. Run Softcite

The `softcite` command sends the text of each document to the text service of Softcite (`/service/processSoftwareText`), by default the hackathon [🤗 Space](../models/README.md#softcite-software-mentions):

```bash
for c in plos_sentences plos_methods pubmed_fulltext; do
  uv run python scripts/eval_somesci.py softcite --config $c
done
```

| Option | Default | |
|---|---|---|
| `--config` | (required) | the config |
| `--data` | `data/somesci` | the `--out` folder of `prepare` |
| `--endpoint` | the 🤗 Space | another Softcite service, e.g. `http://localhost:8060` for a Docker instance |
| `--output-dir` | `<data>/softcite/<config>` | where to write |
| `--threads` | 2 | parallel requests; keep it low, the Space is shared by everyone |
| `--timeout`, `--retries`, `--retry-wait` | 300 s, 5, 10 s | a busy Space answers `503`: the request is sent again |

- **What is sent:** a sentence or a methods section in one request. A full paper is sent paragraph by paragraph, split as for Baguette, and the offsets are moved back to the whole text. If an offset does not fall on its name, the name is searched for near it.
- **Resuming:** documents already done are skipped. A document whose request failed is not written, so running the command again retries it.
- **Output:** one `<file>.software.json` per document, with the `mentions` of Softcite (the JSON schema of the service) and offsets in the text of the document.

## 3. Evaluate

```bash
uv run python scripts/eval_somesci.py evaluate --config plos_sentences                     # Baguette
uv run python scripts/eval_somesci.py evaluate --config plos_sentences --tool softcite
uv run python scripts/eval_somesci.py evaluate --config plos_sentences --explicit-only
uv run python scripts/eval_somesci.py evaluate --config plos_sentences --exclude-os
```

| Option | Default | |
|---|---|---|
| `--config` | (required) | `plos_sentences`, `plos_methods` or `pubmed_fulltext` |
| `--tool` | `baguette` | `baguette` or `softcite` |
| `--data` | `data/somesci` | the `--out` folder of `prepare` |
| `--predictions-dir` | `<data>/<tool>/<config>` | the outputs of the tool (`--baguette-dir` still works) |
| `--explicit-only` | off | leave out the implicit mentions: `implicit` for Baguette, `software-type` `implicit` for Softcite |
| `--exclude-os` | off | leave the operating systems out of the gold; a predicted name that matches one is not counted, neither as a true nor as a false positive |
| `--out` | `<data>/results/<tool>/<config>.json` | the JSON results |

A document without an output of the tool counts as one with no prediction. The number of these is printed, and their ids are in the results.

### What is compared

- **Gold software:** the `APPLICATION`, `PLUGIN`, `PROGRAMMINGENVIRONMENT` and `OPERATINGSYSTEM` entities. `SOFTWARECOREFERENCE` ("the software", "this tool") is left out.
- **Predictions:** the names of the software mentions, made unique per document: for Baguette, the `name` of every mention in `paragraphs[].software`; for Softcite, the `rawForm` of `software-name` of every mention. When a name is repeated, the first mention is kept, or the first one with a `version`.
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

**Baguette** gives names without positions. The script searches the text for each predicted name, case-insensitively and as whole words; every occurrence is a predicted span. If the name is not in the text, it searches again without the version (`SPSS v25` → `SPSS`). When two spans overlap, the longer one is kept.

| Metric | A predicted span matches a gold span when |
|---|---|
| `mention_strict` | they have the same offsets |
| `mention_overlap` | they overlap |

- **Names not in the text** (Baguette): a name that is not found in the text, even without its version, counts as one false positive. Such names are paraphrased or invented.
- **Abbreviations:** a span that only falls on an annotated abbreviation or alternative name, such as `SPM` in `Statistical Parametric Mapping (SPM)`, is not counted.

### Versions

`version` is scored only on the software found at document level (relaxed match). For each of them, the predicted versions are compared with the gold versions of the software:

- **Predicted versions:** the version of the mention (Baguette: `version`; Softcite: the `rawForm` of `version`), plus the numbers of the predicted name that are not in the name of the software. `SPSS 22` gives `22`, `MATLAB R2014a` gives `2014a`, but `3D Slicer` gives nothing.
- **Normalisation:** a `version`, `ver.`, `v`, `release`, `build` or `r` prefix is removed, so `Version 2.15`, `v2.15` and `2.15` are the same.
- **Counts:** a predicted version that is a gold version is a true positive, the other predicted versions are false positives, and the gold versions not predicted are false negatives.

A version given for a software that SoMeSci annotates without one is a false positive. That happens when SoMeSci attaches the version to another name of the same software (see [Limits](#limits)).

### Output

The script prints a summary and a table:

```
baguette on plos_sentences: 677 documents, <n> without output, <n> predicted names (<n> not found in the text)
level                  P       R      F1     TP     FP     FN
doc_exact          ...
doc_relaxed        ...
mention_strict     ...
mention_overlap    ...
version            ...
recall by type (document relaxed / mention overlap):
  APPLICATION              ... / ...
```

The JSON results have:

- **`metrics`:** precision, recall, F1, TP, FP and FN for each level.
- **`recall_by_type`:** recall by software type at both levels, and the number of gold software of each type.
- **`errors`:** per document, the `false_positives` and `false_negatives` at document level (relaxed), the names `not_in_text`, and the `version_errors` (gold software, predicted name, gold and predicted versions). Start the error analysis here.
- **`missing_output_ids`:** the documents without a Baguette output.

## Results

The JSON results are in `data/somesci/results/<tool>/<config>.json`. The Softcite results will be added here, next to the Baguette ones.

### Baguette: summary

Document level, relaxed matching, all software types:

| Config | Documents | Gold software | Predicted names | P | R | F1 | F1 mention (overlap) |
|---|---|---|---|---|---|---|---|
| `plos_sentences` | 677 | 916 | 753 | 0.915 | 0.746 | **0.822** | 0.770 |
| `plos_methods` | 480 | 1,142 | 719 | 0.710 | 0.438 | **0.542** | 0.512 |
| `pubmed_fulltext` | 97 | 285 | 208 | 0.634 | 0.456 | **0.531** | 0.519 |

- **Sentences against longer texts:** Baguette does well on single sentences (F1 0.82). On methods sections and full papers it drops to about 0.53–0.54, with both precision and recall lower.
- **Methods sections are as hard as full papers.** A methods section is sent as one paragraph, which the server cuts into pieces of about 200 tokens. So the drop seems to come with the length of the input, more than with the parts of the paper (introduction, references…) that only a full text has. This is a hypothesis, to check in the `errors`.
- **Baguette gives fewer names than there are gold software** on the longer texts: 719 against 1,142 on methods sections, 208 against 285 on full papers. Recall is the main problem there.

### Baguette on `plos_sentences`

677 sentences. Baguette gave 753 unique names; 17 of them are not in the text.

| Level | P | R | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| `doc_exact` | 0.756 | 0.621 | 0.682 | 569 | 184 | 347 |
| `doc_relaxed` | **0.915** | **0.746** | **0.822** | 683 | 63 | 233 |
| `mention_strict` | 0.660 | 0.607 | 0.633 | 581 | 299 | 376 |
| `mention_overlap` | 0.803 | 0.739 | 0.770 | 707 | 173 | 250 |
| `version` | 0.506 | 0.555 | 0.529 | 266 | 260 | 213 |

| Recall by type | document (relaxed) | mention (overlap) |
|---|---|---|
| `APPLICATION` | 0.797 | 0.795 |
| `PROGRAMMINGENVIRONMENT` | 0.785 | 0.718 |
| `PLUGIN` | 0.674 | 0.682 |
| `OPERATINGSYSTEM` | 0.037 | 0.054 |

**How to read it:**

- **Headline: F1 0.82** at document level with relaxed matching. Each document is one sentence here, so this is close to "did Baguette find the software of the sentence".
- **Precision is high (0.92), recall is lower (0.75).** Baguette rarely gives a name that is not software, and only 17 of its 753 names are not in the text (paraphrased or invented). Most errors are missed software.
- **Exact vs relaxed (0.68 → 0.82):** relaxed matching adds 114 true positives. They are differences of name rather than of detection, probably because Baguette puts the version or the vendor in the name (`SPSS 22` where SoMeSci annotates `SPSS`), or the other way round. To be checked in the `errors`.
- **Strict vs overlap (0.63 → 0.77):** the same thing at mention level, with 126 more matches. Baguette finds the right place, but its span is longer or shorter than the gold one, probably for the same reason.
- **Operating systems:** Baguette almost never gives Windows, Linux or macOS as software. This looks like a choice of the model rather than a miss. They are few in the gold; `--exclude-os` gives the scores without them.
- **Plugins** (R or Python packages, toolboxes…) are found less often (0.67) than applications and programming languages (about 0.79).
- **Versions are weak (F1 0.53)**, on the 683 software found: about half of the predicted versions are not the gold one, and 213 of the 479 gold versions are missed. Part of it can come from the way versions are written or attached in SoMeSci (see [Limits](#limits)); the `version_errors` show which.

The `errors` of the results JSON tell real misses apart from differences of name that relaxed matching does not catch.

### Baguette on `plos_methods`

480 methods sections. Baguette gave 719 unique names, 1.5 per section; 26 of them are not in the text. The gold has 1,142 software (2.4 per section) and 1,563 mentions.

| Level | P | R | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| `doc_exact` | 0.558 | 0.351 | 0.431 | 401 | 318 | 741 |
| `doc_relaxed` | **0.710** | **0.438** | **0.542** | 500 | 204 | 642 |
| `mention_strict` | 0.450 | 0.397 | 0.422 | 620 | 757 | 943 |
| `mention_overlap` | 0.546 | 0.481 | 0.512 | 752 | 625 | 811 |
| `version` | 0.367 | 0.399 | 0.382 | 99 | 171 | 149 |

| Recall by type | document (relaxed) | mention (overlap) |
|---|---|---|
| `PROGRAMMINGENVIRONMENT` | 0.598 | 0.612 |
| `PLUGIN` | 0.450 | 0.483 |
| `APPLICATION` | 0.429 | 0.474 |
| `OPERATINGSYSTEM` | 0.032 | 0.030 |

**How to read it:**

- **F1 0.54** at document level (relaxed), against 0.82 on sentences. Recall is the weak part (0.44): Baguette misses more than half of the software of a methods section.
- **Exact vs relaxed (0.43 → 0.54):** as on sentences, a good part of the exact-match errors are differences of name.
- **Programming environments** (R, Python, MATLAB…) are the best found (0.60). Applications and plugins are below 0.45.
- **Versions are weak (F1 0.38),** lower than on sentences (0.53).

### Baguette on `pubmed_fulltext`

97 full papers. Baguette gave 208 unique names, about 2 per paper; 11 of them are not in the text. The gold has 285 software (about 3 per paper) and 414 mentions.

| Level | P | R | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| `doc_exact` | 0.490 | 0.358 | 0.414 | 102 | 106 | 183 |
| `doc_relaxed` | **0.634** | **0.456** | **0.531** | 130 | 75 | 155 |
| `mention_strict` | 0.409 | 0.406 | 0.407 | 168 | 243 | 246 |
| `mention_overlap` | 0.521 | 0.517 | 0.519 | 214 | 197 | 200 |
| `version` | 0.547 | 0.603 | 0.574 | 35 | 29 | 23 |

| Recall by type | document (relaxed) | mention (overlap) |
|---|---|---|
| `APPLICATION` | 0.475 | 0.540 |
| `PROGRAMMINGENVIRONMENT` | 0.471 | 0.518 |
| `PLUGIN` | 0.472 | 0.543 |
| `OPERATINGSYSTEM` | 0.077 | 0.053 |

**How to read it:**

- **Much lower than on sentences: F1 0.53 against 0.82** (document, relaxed). Both precision (0.63 against 0.92) and recall (0.46 against 0.75) drop.
- **Recall:** Baguette gives fewer names than there are gold software (208 against 285), and misses about half of them, whatever the type.
- **Precision:** to be checked in the `errors`. Possible causes: names that SoMeSci does not annotate as software in a full paper, or longer texts giving the model more chances to go wrong.
- **Mention level is close to document level here (0.52):** a name given once is searched everywhere in the paper, so its other occurrences count too, right or wrong.
- **Versions** are a little better than on sentences (F1 0.57), but on few software (58 gold versions).

Before reading this as the quality of Baguette on full papers, check how the papers were sent: the number of paragraphs and pieces per paper and the failed paragraphs, in the Baguette outputs. A full text cut in the wrong places, or failed paragraphs, would lower recall without being a fault of the model.


## Limits

- **Roles are not scored:** see [The data](#the-data).
- **Lexical identity:** SoMeSci tells software apart by name, so `SPSS` and `IBM SPSS Statistics` in one paper are two gold software. Finding only one of them gives a false negative.
- **Short names:** at mention level, a short name such as `R` matches every standalone `R` of the text. That can lower the mention-level precision.
- **Mentions lost between pieces:** the server cuts long paragraphs into pieces of about 200 tokens, and a mention split between two pieces can be lost.
- **No offsets for Baguette:** its mention level is an approximation. It assumes Baguette finds every occurrence of a name it gives once. Softcite's mention level uses its own offsets, so it is exact. Compare the two tools at document level first.
- **Softcite on the 🤗 Space:** the Space is shared and may be slower or busy; scores do not depend on it, but run time does. The version of the service (`application`, `version` in each output) is in the outputs.
