# Results on SoMeSci

Scores of the software-mention tools against [SoMeSci](../datasets/README.md#somesci), computed by [`scripts/eval_somesci.py`](../scripts/eval_somesci.py). How they are computed, and their limits, are in [README.md](README.md).

- **Main score:** document level with relaxed matching (`doc_relaxed`): the software of a document against the unique names given by the tool.
- **All the numbers:** `data/somesci/results/<tool>/<run>.json`, with the errors of each document.
- **Run:** all software types, implicit mentions included (no `--explicit-only`, no `--exclude-os`), unless written otherwise.
- **Inputs:** Baguette and Softcite with `--split blocks` (a methods section in one block, a full paper split at blank lines, which in SoMeSci are sections), bio2flow with `--split paragraphs` (one paragraph per line of the text; its client joins them into one document anyway). Sentences are the same input for all three.
- **Intervals:** 95% bootstrap intervals over the documents (1,000 samples).

## How the evaluation works

The full description is in [README.md](README.md); this is the short version.

### The steps

1. **`prepare`** reads SoMeSci and writes, for each document, its text and its gold annotations (`gold/<config>.jsonl`), and the Baguette input.
2. **The tools run on the same texts.** Baguette goes through its endpoint, Softcite through its text service (`softcite` command), and bio2flow through its Modal endpoint with `copalink_client.py --endpoint` (or locally, with the same outputs). Each writes one output file per document.
3. **`evaluate --tool <tool>`** reads the gold and the outputs of the tool, matches them, and counts true positives (TP), false positives (FP) and false negatives (FN). The scores are micro-averaged over all the documents of a config: P = TP / (TP + FP), R = TP / (TP + FN), F1 their harmonic mean.

### The fields used

**SoMeSci (gold):**

| Field | Used for |
|---|---|
| `software[]`: `name`, `alternativename`, `abbreviation`, `type`, `version` | document level: the software of the document, all its names, its type, its versions |
| BIO tags + `start_offsets` → spans of `APPLICATION`, `PLUGIN`, `PROGRAMMINGENVIRONMENT`, `OPERATINGSYSTEM` | mention level: where each software is written in the text |
| spans of `ABBREVIATION`, `ALTERNATIVENAME` | mention level: a predicted span that only falls on one of them is not counted |

`SOFTWARECOREFERENCE` ("the software") and the other attributes (developer, URL, license, citation…) are not used.

**Baguette** (`paragraphs[].software[]` of each output):

| Field | Used for |
|---|---|
| `name` | the predicted software |
| `version` | the predicted version (with the numbers of `name`) |
| `explicit_or_implicit` | `--explicit-only` drops the `implicit` ones |

Not used: `role`, `evidence`, `artifact_type`, `repository_or_url`, `programming_language`, the `datasets`, and the article-level `record`. Baguette has no offsets.

**Softcite** (`mentions[]` of each output, those with `type` `software`):

| Field | Used for |
|---|---|
| `software-name.rawForm` | the predicted software |
| `software-name.offsetStart`, `offsetEnd` | the predicted span |
| `version.rawForm` | the predicted version |
| `software-type` | `--explicit-only` drops the `implicit` ones |

Not used: `normalizedForm`, `publisher`, `url`, `language`, `context`, the `used` / `created` / `shared` attributes, and the Wikidata ids.

**bio2flow** (`paragraphs[].entities[]` of each output of `copalink_client.py`, those with `type` `Tool`, the only type the model gives):

| Field | Used for |
|---|---|
| `text` | the predicted software |
| `begin`, `end` | the predicted span, in the paragraph; moved back to the text of the document |

Not used: `confidence` (all entities count), `attributes` (empty). bio2flow gives no versions: its only predicted versions are numbers inside a name (`SPSS 22`), so its version scores are near 0 by construction.

SoMeSci on Hugging Face has no usage / creation types, so the roles of Baguette and the attributes of Softcite cannot be scored.

### The metrics, on an example

The sentence:

> Data were analysed with IBM SPSS Statistics version 25 and R.

- **Gold:** two software, `IBM SPSS Statistics` (application, version 25, characters 24–43) and `R` (programming environment, characters 59–60).
- **Softcite** (its real output): `SPSS Statistics` at 28–43 with version 25, and `R` at 59–60. It leaves `IBM` out of the name.
- **Baguette** (for the example): `IBM SPSS Statistics` with version 25, and `R`. No offsets.

**Document level** compares the *software* of the document with the *unique names* given by the tool, whatever the number of times they are written. A name matches a software if it matches its name, its alternative name or one of its abbreviations.

| Metric | A name matches a software when | Softcite | Baguette |
|---|---|---|---|
| `doc_exact` | it is the same, after lower case and spaces and punctuation at the ends are normalised | `R` ✓, `SPSS Statistics` ✗ → TP 1, FP 1, FN 1 | both ✓ → TP 2 |
| `doc_relaxed` | all the words of one are in the other | `SPSS Statistics` ⊂ `IBM SPSS Statistics` ✓ → TP 2 | TP 2 |

So `doc_exact` asks for the same name as the annotators; `doc_relaxed` accepts a name with a word more or less (vendor, version, "software"…), such as `SPSS` ~ `IBM SPSS Statistics` or `SPSS 22` ~ `SPSS`, but not two different names. **`doc_relaxed` is the main score.**

**Mention level** compares *spans*: every place where a software is written. A software written three times is three gold spans.

| Metric | A predicted span matches a gold span when | Softcite | Baguette |
|---|---|---|---|
| `mention_strict` | they have the same start and end | `R` ✓, 28–43 ≠ 24–43 ✗ → TP 1, FP 1, FN 1 | TP 2 |
| `mention_overlap` | they share at least one character | 28–43 overlaps 24–43 ✓ → TP 2 | TP 2 |

- **Softcite's spans** are its own offsets.
- **Baguette has no offsets.** Each of its names is searched in the text, as whole words and ignoring case, and every place found is a predicted span (here, 24–43 and 59–60). A name that is not in the text is one false positive. This makes Baguette's mention level an approximation: it assumes Baguette would find every occurrence of a name it gives once.

**`version`** is scored on the software matched by `doc_relaxed` only. The predicted versions of the software (the version field, and the numbers of the name that are not part of the software's name) are compared with its gold versions, after `v`, `version`, `release`… are removed. Here both tools give `25` → TP 1.

**Matching is one-to-one:** a predicted name or span matches at most one gold software or span, and the reverse. Two names of the same software (e.g. `Statistical Parametric Mapping` and `SPM`) give one true positive; the second one is not a false positive.

## Comparison

Document level, relaxed matching:

| Config | Tool | P | R | F1 (95% interval) | F1 mention (overlap) | F1 version |
|---|---|---|---|---|---|---|
| `plos_sentences` | Baguette | 0.915 | 0.746 | **0.822** (0.802–0.843) | 0.770 | 0.529 |
| | Softcite | 0.932 | 0.879 | **0.904** (0.891–0.917) | 0.906 | 0.939 |
| | bio2flow ‡ | 0.717 | 0.094 | **0.166** (0.133–0.197) | 0.172 | – |
| `plos_methods` | Baguette | 0.710 | 0.438 | **0.542** (0.513–0.576) | 0.512 | 0.382 |
| | Softcite | 0.787 | 0.834 | **0.809** (0.787–0.831) | 0.791 | 0.888 |
| | bio2flow ‡ | 0.491 | 0.452 | **0.471** (0.427–0.511) | 0.449 | – |
| `pubmed_fulltext` | Baguette | 0.634 | 0.456 | **0.531** (0.462–0.598) | 0.519 | 0.574 |
| | Softcite | 0.836 | 0.807 | **0.821** (0.784–0.866) | 0.793 | 0.935 |
| | bio2flow ‡ | 0.367 | 0.604 | **0.456** (0.371–0.534) | 0.398 | – |

‡ For completeness only. bio2flow is on paragraphs, and it gives no versions (–). Its training corpus never counts programming languages or operating systems as tools, so all types put it at a disadvantage by definition; compare it on applications and plugins, below.

So the three tools are compared on **applications and plugins only**, the software that all three count (see [bio2flow](#bio2flow) and [Excluding types](README.md#excluding-types)):

```bash
evaluate --config <config> --tool <tool> --exclude-types PROGRAMMINGENVIRONMENT OPERATINGSYSTEM
```

Document level, relaxed matching, applications and plugins only:

| Config | Tool | P | R | F1 (95% interval) |
|---|---|---|---|---|
| `plos_sentences` | Baguette | 0.906 | 0.791 | **0.844** (0.824–0.866) |
| | Softcite | 0.923 | 0.926 | **0.925** (0.911–0.938) |
| | bio2flow | 0.714 | 0.111 | **0.191** (0.153–0.227) |
| `plos_methods` | Baguette | 0.679 | 0.432 | **0.528** (0.497–0.563) |
| | Softcite | 0.766 | 0.847 | **0.805** (0.779–0.829) |
| | bio2flow | 0.490 | 0.513 | **0.501** (0.456–0.542) |
| `pubmed_fulltext` | Baguette | 0.617 | 0.474 | **0.537** (0.464–0.610) |
| | Softcite | 0.829 | 0.855 | **0.842** (0.797–0.893) |
| | bio2flow | 0.364 | 0.667 | **0.471** (0.385–0.550) |

Baguette and Softcite on blocks, bio2flow on paragraphs (see the inputs at the top); on sentences the inputs are the same.

- **The ranking does not change: Softcite, then Baguette, then bio2flow.** Softcite is clearly ahead everywhere: its interval overlaps neither of the others in any config.
- **The exclusion changes little for Baguette and Softcite** (F1 within 0.03 of their all-types F1: Baguette 0.822 → 0.844, 0.542 → 0.528, 0.531 → 0.537; Softcite 0.904 → 0.925, 0.809 → 0.805, 0.821 → 0.842), and little for bio2flow (+0.02 to +0.03). So bio2flow's low scores are not an effect of what counts as software.
- **bio2flow against Baguette:** far below on sentences (0.19 against 0.84). On the longer texts the two are close and their intervals overlap (methods 0.456–0.542 against 0.497–0.563, full papers 0.385–0.550 against 0.464–0.610), so the difference there is not clear. They get there differently: bio2flow has the higher recall (0.51 against 0.43 on methods sections, 0.67 against 0.47 on full papers), Baguette the higher precision (0.68 against 0.49, 0.62 against 0.36).
- **Sentences:** bio2flow names a software in few of them (121 names for 916 gold software), so recall is 0.11. Its precision there is the best of its three configs (0.71).
- **Longer texts:** recall rises (0.51 on methods sections, 0.67 on full papers), but precision falls (0.49, 0.36). On full papers it gives 477 names for 285 gold software.

Recall by type, document level (relaxed):

| Type | Baguette sentences | Softcite sentences | bio2flow sentences | Baguette methods | Softcite methods | bio2flow methods | Baguette full papers | Softcite full papers | bio2flow full papers |
|---|---|---|---|---|---|---|---|---|---|
| `APPLICATION` | 0.797 | **0.939** | 0.096 | 0.429 | **0.860** | 0.485 | 0.475 | **0.872** | 0.621 |
| `PROGRAMMINGENVIRONMENT` | 0.785 | **0.989** | 0.011 | 0.598 | **0.920** | 0.027 | 0.471 | **0.706** | 0.118 |
| `PLUGIN` | 0.674 | **0.698** | 0.349 | 0.450 | **0.775** | 0.675 | 0.472 | 0.750 | **0.944** |
| `OPERATINGSYSTEM` | 0.037 | 0.018 | 0.000 | 0.032 | 0.097 | 0.000 | 0.077 | 0.000 | 0.000 |

bio2flow's columns are on paragraphs, the others on blocks.

**Differences between the tools:**

- **Softcite is better on all three configs:** F1 0.90 against 0.82 on sentences, 0.81 against 0.54 on methods sections, 0.82 against 0.53 on full papers.
- **Longer texts hurt Baguette much more.** From sentences to longer texts, Softcite loses 0.08 to 0.10 of F1, Baguette about 0.28. Both tools got the same inputs. The cutting of long inputs into pieces by Baguette's server is probably not the main cause: on the PEPR corpus, Baguette gives about the same share of names on paragraphs it cut as on the others (see [Is the comparison fair?](#is-the-comparison-fair)). The more likely cause is that Baguette gives fewer names per passage than are annotated: on PEPR, about half as many as Softcite. That matters little on a sentence chosen for its software mention, and a lot on a methods section that names several. This is still a hypothesis, to be confirmed in the `errors`.
- **Recall is Baguette's main problem.** On sentences, precision is about the same (0.93 against 0.92) and only recall differs (0.88 against 0.75). On longer texts, Baguette gives far fewer names than there are gold software (719 for 1,142 on methods sections, 208 for 285 on full papers), and its recall falls below 0.46. Softcite gives about as many names as there are gold software, and keeps recall above 0.8.
- **Versions are where the gap is largest:** F1 0.89 to 0.94 for Softcite, 0.38 to 0.57 for Baguette, with the same metric. So the weak version scores of Baguette come from Baguette, not from the way versions are scored.
- **By type:** Softcite finds most applications (0.86–0.94) and programming environments (0.71–0.99) in every config. Plugins are the weakest type of both tools on sentences (about 0.7).
- **Operating systems:** neither tool gives them (recall 0.10 at most). This is a choice of SoMeSci, which annotates them as software, more than a fault of the tools. `--exclude-os` gives the scores without them.
- **Exact names:** Softcite loses less from relaxed to exact matching (e.g. 0.90 → 0.82 on sentences) than Baguette (0.82 → 0.68): its names are closer to the annotated forms.
- **Mention level:** Softcite gives offsets, so its mention level is exact (F1 0.79–0.91, overlap). Baguette gives only names, and its mention level comes from searching them in the text (0.51–0.77). Compare the tools at document level first.
- **Training data:** Softcite is trained on human annotations of the Softcite corpus (biomedical and economics papers), close to the PLoS and PMC papers of SoMeSci. Baguette is distilled from an LLM, on English and French papers. None of the SoMeSci articles is in the Softcite corpus; for Baguette, it is not known (see [Is the comparison fair?](#is-the-comparison-fair)).

### Is the comparison fair?

Checked with the public sources and the outputs of both tools on the PEPR corpus (🤗 [`pepr-hal-data`](https://huggingface.co/datasets/HackatonSanteNumerique/pepr-hal-data), `baguette/` and `softcite/`).

| Check | Result | Fair? |
|---|---|---|
| Same texts for both tools | Yes: the same sentence, methods section or full-text blocks, from `prepare` | ✓ |
| Same scoring for both tools | Yes, the same code. Only the mention level differs: Baguette has no offsets, so its spans are searched in the text | ✓ at document level; mention level of Baguette is approximate |
| Same tool versions as on PEPR | Softcite: the same service, `software-mentions` 0.9.0-SNAPSHOT, revision `54efbc6`, for PEPR and SoMeSci. Baguette: the same endpoint, which cuts long inputs on both | ✓ |
| SoMeSci articles in the training data of Softcite | None of the 1,257 SoMeSci articles (PMC ids) is in the Softcite corpus of the [software-mentions](https://github.com/softcite/software-mentions) repo (2,561 PMC articles in training, about 530 in the holdout). The repo uses SoMeSci only to build training data for the used / created / shared classifier, which is not scored here. Not checked: whether the weights on the Space were trained on more data than the repo | ✓ as far as the repo shows |
| SoMeSci articles in the training data of Baguette | Unknown: its 531k training paragraphs are not public. Its labels come from an LLM teacher, not from SoMeSci, so at most the texts could overlap, not the annotations | ? |
| Inputs as in normal use | No, for both. On PEPR, Baguette gets GROBID paragraphs (median 314 characters, 14% cut into pieces); here, a methods section (median about 1,350 words, 7 paragraphs) is one input, and a full paper is split at blank lines, which in SoMeSci separate sections, not paragraphs. On PEPR, Softcite reads the whole paper (TEI or PDF) and spreads a name found once to its other occurrences; here it gets the same blocks as Baguette, through its text service `--split paragraphs` sends the paragraphs of SoMeSci instead, one per line of the text; Baguette and Softcite have not been run on it | ~ |
| Effect of cutting on Baguette | Measured on PEPR, paragraph by paragraph, against the Softcite mentions of the same paragraph: Baguette gives 0.48 names per Softcite name on paragraphs it did not cut (3,307 paragraphs), 0.42 on paragraphs it cut (1,131). Cutting costs little | ✓ probably |
| Failed requests counted as misses | On PEPR, 7 of 22,410 Baguette paragraphs failed. On SoMeSci, not checked | ✓ probably |
| What counts as software | Not neutral. SoMeSci and Softcite are human annotation schemes for the same task, with similar choices on names and versions; Softcite learned them from human annotations, Baguette from an LLM teacher with its own definition (software apart from datasets, roles…). SoMeSci measures agreement with such a scheme, which favours a model trained on one | ✗ favours Softcite |
| Uncertainty | 95% bootstrap intervals over the documents (1,000 samples), in the tables. On all types, the intervals of Baguette and Softcite do not overlap in any config (e.g. 0.462–0.598 against 0.784–0.866 on full papers, the fewest documents): the gap between the two tools is clear | ✓ |

**On PEPR, without gold:** on the 263 papers with both outputs, Baguette gives 7.9 unique names per paper and Softcite 8.8. Only about half are shared (51% of Baguette's names, 46% of Softcite's, with the relaxed matching). Per paragraph, Baguette gives about half as many names as Softcite: it names a software in fewer of the paragraphs where it appears. So the two tools disagree a lot on real papers too, and SoMeSci only says which one is closer to its annotators.

**bio2flow:**

| Check | Result | Fair? |
|---|---|---|
| SoMeSci articles in its training data | None of the 1,257 SoMeSci articles is among the 50 PMC articles of [CPL-Article](https://doi.org/10.5281/zenodo.20746904) (2019–2026), its training corpus. Checked through the PMC ids of the PMIDs it lists | ✓ |
| Same model as on PEPR | The PEPR outputs (`bio2flow/` on 🤗) come from `csebe_scibert_bioinfo_voc_iteration4_seed100.pt`, the default of `copalink_client.py`. Use the same file | ✓ if the same file is used |
| Same inputs, as in normal use | The same paragraphs as the other tools; the client joins them into one document, as it does with the GROBID paragraphs on PEPR | ✓ |
| What counts as software | **Not comparable on all types.** CPL-Article annotates bioinformatics tools only: R (written 42 times in its articles), Python (24), Linux (11), Docker (66), Nextflow (134) are never annotated as `Tool`. SoMeSci counts R, Python and Linux as software. The tools are compared on applications and plugins only (`--exclude-types PROGRAMMINGENVIRONMENT OPERATINGSYSTEM`). Even there, CPL-Article's tools are bioinformatics ones; general applications such as SPSS or Excel are not in it either (Excel: written twice, not annotated) | ~ on applications and plugins |
| Versions | The model tags no versions; only numbers inside a predicted name count | ✗ near 0 by construction; leave out |
| Domain | CPL-Article is bioinformatics workflows; SoMeSci is PLoS and PMC papers of all biomedical fields | ✗ favours the other tools |

**What would make it fairer:**

1. Run Baguette and Softcite on paragraphs (`--split paragraphs`), as on PEPR and as bio2flow, on `plos_methods` and `pubmed_fulltext` (see [README.md](README.md#1-prepare)).
2. Read the `errors`: whether Baguette's misses are software it does not see, or names SoMeSci counts as software and Baguette does not (or puts in `datasets`).
3. Compare the tools on the same resampled documents (a paired bootstrap): it says whether a gap is real even when the intervals of two tools overlap.

## Baguette

[Baguette](../models/README.md#baguette-dataesr) through the hackathon endpoint, `--no-analyze` (step 1 only).

### Summary

| Config | Documents | Gold software | Predicted names | P | R | F1 (95% interval) | F1 mention (overlap) |
|---|---|---|---|---|---|---|---|
| `plos_sentences` | 677 | 916 | 753 | 0.915 | 0.746 | **0.822** (0.802–0.843) | 0.770 |
| `plos_methods` | 480 | 1,142 | 719 | 0.710 | 0.438 | **0.542** (0.513–0.576) | 0.512 |
| `pubmed_fulltext` | 97 | 285 | 208 | 0.634 | 0.456 | **0.531** (0.462–0.598) | 0.519 |

- **Sentences against longer texts:** Baguette does well on single sentences (F1 0.82). On methods sections and full papers it drops to about 0.53–0.54, with both precision and recall lower.
- **Methods sections are as hard as full papers.** A methods section is sent as one paragraph, which the server cuts into pieces of about 200 tokens. So the drop seems to come with the length of the input, more than with the parts of the paper (introduction, references…) that only a full text has. This is a hypothesis, to check in the `errors`.
- **Baguette gives fewer names than there are gold software** on the longer texts: 719 against 1,142 on methods sections, 208 against 285 on full papers. Recall is the main problem there.

### `plos_sentences`

677 sentences. Baguette gave 753 unique names; 17 of them are not in the text.

| Level | P | R | F1 | F1 95% | TP | FP | FN |
|---|---|---|---|---|---|---|---|
| `doc_exact` | 0.756 | 0.621 | 0.682 | 0.651–0.713 | 569 | 184 | 347 |
| `doc_relaxed` | **0.915** | **0.746** | **0.822** | 0.802–0.843 | 683 | 63 | 233 |
| `mention_strict` | 0.660 | 0.607 | 0.633 | 0.604–0.661 | 581 | 299 | 376 |
| `mention_overlap` | 0.803 | 0.739 | 0.770 | 0.748–0.792 | 707 | 173 | 250 |
| `version` | 0.506 | 0.555 | 0.529 | 0.484–0.573 | 266 | 260 | 213 |

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
- **Versions are weak (F1 0.53)**, on the 683 software found: about half of the predicted versions are not the gold one, and 213 of the 479 gold versions are missed. Part of it can come from the way versions are written or attached in SoMeSci (see [Limits](README.md#limits)); the `version_errors` show which.

The `errors` of the results JSON tell real misses apart from differences of name that relaxed matching does not catch.

### `plos_methods`

480 methods sections. Baguette gave 719 unique names, 1.5 per section; 26 of them are not in the text. The gold has 1,142 software (2.4 per section) and 1,563 mentions.

| Level | P | R | F1 | F1 95% | TP | FP | FN |
|---|---|---|---|---|---|---|---|
| `doc_exact` | 0.558 | 0.351 | 0.431 | 0.404–0.464 | 401 | 318 | 741 |
| `doc_relaxed` | **0.710** | **0.438** | **0.542** | 0.513–0.576 | 500 | 204 | 642 |
| `mention_strict` | 0.450 | 0.397 | 0.422 | 0.379–0.468 | 620 | 757 | 943 |
| `mention_overlap` | 0.546 | 0.481 | 0.512 | 0.460–0.559 | 752 | 625 | 811 |
| `version` | 0.367 | 0.399 | 0.382 | 0.326–0.444 | 99 | 171 | 149 |

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

### `pubmed_fulltext`

97 full papers. Baguette gave 208 unique names, about 2 per paper; 11 of them are not in the text. The gold has 285 software (about 3 per paper) and 414 mentions.

| Level | P | R | F1 | F1 95% | TP | FP | FN |
|---|---|---|---|---|---|---|---|
| `doc_exact` | 0.490 | 0.358 | 0.414 | 0.358–0.473 | 102 | 106 | 183 |
| `doc_relaxed` | **0.634** | **0.456** | **0.531** | 0.462–0.598 | 130 | 75 | 155 |
| `mention_strict` | 0.409 | 0.406 | 0.407 | 0.306–0.503 | 168 | 243 | 246 |
| `mention_overlap` | 0.521 | 0.517 | 0.519 | 0.414–0.618 | 214 | 197 | 200 |
| `version` | 0.547 | 0.603 | 0.574 | 0.418–0.730 | 35 | 29 | 23 |

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

## Softcite

[Softcite software-mentions](../models/README.md#softcite-software-mentions) through the text service of the hackathon 🤗 Space (`software-mentions` 0.9.0-SNAPSHOT).

```bash
for c in plos_sentences plos_methods pubmed_fulltext; do
  uv run python scripts/eval_somesci.py softcite --config $c
  uv run python scripts/eval_somesci.py evaluate --config $c --tool softcite
done
```

### Summary

| Config | Documents | Gold software | Predicted names | P | R | F1 (95% interval) | F1 mention (overlap) |
|---|---|---|---|---|---|---|---|
| `plos_sentences` | 677 | 916 | 866 | 0.932 | 0.879 | **0.904** (0.891–0.917) | 0.906 |
| `plos_methods` | 480 | 1,142 | 1,227 | 0.787 | 0.834 | **0.809** (0.787–0.831) | 0.791 |
| `pubmed_fulltext` | 97 | 285 | 281 | 0.836 | 0.807 | **0.821** (0.784–0.866) | 0.793 |

- **Stable across inputs:** F1 0.90 on sentences, about 0.81–0.82 on methods sections and full papers.
- **It gives about as many names as there are gold software** in every config: precision and recall stay close to each other.

### `plos_sentences`

677 sentences. Softcite gave 866 unique names. Its names come with offsets, so all are in the text.

| Level | P | R | F1 | F1 95% | TP | FP | FN |
|---|---|---|---|---|---|---|---|
| `doc_exact` | 0.841 | 0.795 | 0.817 | 0.794–0.839 | 728 | 138 | 188 |
| `doc_relaxed` | **0.932** | **0.879** | **0.904** | 0.891–0.917 | 805 | 59 | 111 |
| `mention_strict` | 0.839 | 0.789 | 0.813 | 0.789–0.835 | 755 | 145 | 202 |
| `mention_overlap` | 0.934 | 0.879 | 0.906 | 0.891–0.918 | 841 | 59 | 116 |
| `version` | 0.921 | 0.958 | 0.939 | 0.922–0.955 | 527 | 45 | 23 |

| Recall by type | document (relaxed) | mention (overlap) |
|---|---|---|
| `PROGRAMMINGENVIRONMENT` | 0.989 | 0.952 |
| `APPLICATION` | 0.939 | 0.939 |
| `PLUGIN` | 0.698 | 0.750 |
| `OPERATINGSYSTEM` | 0.018 | 0.018 |

**How to read it:**

- **F1 0.90** at document level (relaxed), with precision and recall both near 0.9.
- **Document and mention levels agree** (0.904 and 0.906): Softcite's spans are its own, and it finds the occurrences of a software, not only the software.
- **Strict vs overlap (0.81 → 0.91):** about one span in ten has other boundaries than the gold one, e.g. with or without the vendor (`IBM SPSS Statistics` against `SPSS Statistics`).
- **Versions: F1 0.94,** on the 805 software found (550 gold versions).
- **Plugins** are its weak point (0.70), and it gives almost no operating systems.

### `plos_methods`

480 methods sections, each sent as one text. Softcite gave 1,227 unique names, 2.6 per section, for 1,142 gold software (2.4 per section).

| Level | P | R | F1 | F1 95% | TP | FP | FN |
|---|---|---|---|---|---|---|---|
| `doc_exact` | 0.685 | 0.736 | 0.709 | 0.679–0.738 | 840 | 387 | 302 |
| `doc_relaxed` | **0.787** | **0.834** | **0.809** | 0.787–0.831 | 952 | 258 | 190 |
| `mention_strict` | 0.704 | 0.672 | 0.688 | 0.657–0.717 | 1051 | 442 | 512 |
| `mention_overlap` | 0.810 | 0.773 | 0.791 | 0.767–0.813 | 1209 | 284 | 354 |
| `version` | 0.900 | 0.876 | 0.888 | 0.852–0.916 | 423 | 47 | 60 |

| Recall by type | document (relaxed) | mention (overlap) |
|---|---|---|
| `PROGRAMMINGENVIRONMENT` | 0.920 | 0.888 |
| `PLUGIN` | 0.775 | 0.736 |
| `APPLICATION` | 0.860 | 0.781 |
| `OPERATINGSYSTEM` | 0.097 | 0.121 |

**How to read it:**

- **F1 0.81** at document level (relaxed), 0.10 below sentences.
- **Recall is higher than precision here (0.83 against 0.79),** the only config where it is. Softcite gives more names than there are gold software (1,227 for 1,142). The 258 false positives are to be checked in the `errors`: names SoMeSci does not annotate, or one software given under several names.
- **Exact vs relaxed (0.71 → 0.81):** a good part of the exact-match errors are differences of name, more than on sentences.
- **Versions: F1 0.89,** on 483 gold versions.
- **Programming environments** are found best (0.92); operating systems hardly at all (0.10).

### `pubmed_fulltext`

97 full papers, sent paragraph by paragraph. Softcite gave 281 unique names, about 3 per paper, for 285 gold software.

| Level | P | R | F1 | F1 95% | TP | FP | FN |
|---|---|---|---|---|---|---|---|
| `doc_exact` | 0.730 | 0.719 | 0.724 | 0.675–0.768 | 205 | 76 | 80 |
| `doc_relaxed` | **0.836** | **0.807** | **0.821** | 0.784–0.866 | 230 | 45 | 55 |
| `mention_strict` | 0.706 | 0.645 | 0.674 | 0.614–0.731 | 267 | 111 | 147 |
| `mention_overlap` | 0.831 | 0.758 | 0.793 | 0.738–0.841 | 314 | 64 | 100 |
| `version` | 0.940 | 0.931 | 0.935 | 0.892–0.975 | 94 | 6 | 7 |

| Recall by type | document (relaxed) | mention (overlap) |
|---|---|---|
| `APPLICATION` | 0.872 | 0.807 |
| `PLUGIN` | 0.750 | 0.783 |
| `PROGRAMMINGENVIRONMENT` | 0.706 | 0.667 |
| `OPERATINGSYSTEM` | 0.000 | 0.000 |

**How to read it:**

- **F1 0.82** at document level (relaxed), 0.08 below sentences. Precision and recall both stay above 0.8.
- **It gives about as many names as there are gold software** (281 for 285), while Baguette gives 208.
- **Mention level is a little below document level (0.79):** in a full paper, Softcite finds a software but not all of its occurrences (mention recall 0.76).
- **Versions: F1 0.94,** as on sentences (101 gold versions on the software found).
- **Programming environments** are found less often than on sentences (0.71 against 0.99); the `errors` will show which ones.

## bio2flow

The paper-text NER of [CoPaLink](../models/README.md#copalink) (`csebe_scibert_bioinfo_voc_iteration4_seed100.pt`), trained on CPL-Article, through its Modal endpoint ([`scripts/bio2flow_modal.py`](../scripts/bio2flow_modal.py), L4 GPU) with [`copalink_client.py --endpoint`](../scripts/copalink_client.py), on paragraphs (`--split paragraphs`). Commands in [README.md](README.md#2c-run-bio2flow), then:

```bash
for c in plos_sentences plos_methods pubmed_fulltext; do
  uv run python scripts/eval_somesci.py evaluate --config $c --tool bio2flow
  uv run python scripts/eval_somesci.py evaluate --config $c --tool bio2flow --exclude-types PROGRAMMINGENVIRONMENT OPERATINGSYSTEM
done
```

Every document has an output (0 failed requests).

### Summary

Document level, relaxed matching; "apps & plugins" is the run with `--exclude-types PROGRAMMINGENVIRONMENT OPERATINGSYSTEM`, the one to compare with the other tools.

| Config | Documents | Predicted names | Gold software (all / apps & plugins) | F1 all types (95% interval) | F1 apps & plugins (95% interval) | F1 mention (overlap), apps & plugins |
|---|---|---|---|---|---|---|
| `plos_sentences` | 677 | 121 | 916 / 769 | 0.166 (0.133–0.197) | **0.191** (0.153–0.227) | 0.200 |
| `plos_methods` | 480 | 1,053 | 1,142 / 999 | 0.471 (0.427–0.511) | **0.501** (0.456–0.542) | 0.480 |
| `pubmed_fulltext` | 97 | 477 | 285 / 255 | 0.456 (0.371–0.534) | **0.471** (0.385–0.550) | 0.411 |

- **Recall grows with the length of the text, precision falls.** On sentences it gives few names, mostly right; on full papers, many names, mostly wrong.
- **Sentences and methods sections come from the same PLoS papers,** yet recall is 0.11 on sentences and 0.51 on methods sections. So the drop on sentences is not the domain. A likely cause is context: the model sees the sentences around a word (`doc_context` in its configuration), and an isolated sentence gives it none. This is a hypothesis, to check in the `errors`.
- **Plugins are its strong point** (recall 0.35, 0.68, 0.94: the best of the three tools on full papers, with few plugins there), applications are found half as often, programming environments and operating systems hardly at all, as expected.
- **Versions:** near 0, by construction (see above).

### `plos_sentences`

677 sentences, 121 unique names.

| Level | P (all) | R (all) | F1 (all) | 95% interval (all) | P (apps & plugins) | R (apps & plugins) | F1 (apps & plugins) | 95% interval (apps & plugins) |
|---|---|---|---|---|---|---|---|---|
| `doc_exact` | 0.653 | 0.086 | 0.152 | 0.121–0.183 | 0.650 | 0.101 | 0.175 | 0.140–0.210 |
| `doc_relaxed` | **0.717** | **0.094** | **0.166** | 0.133–0.197 | **0.714** | **0.111** | **0.191** | 0.153–0.227 |
| `mention_strict` | 0.653 | 0.085 | 0.150 | 0.119–0.183 | 0.650 | 0.100 | 0.173 | 0.139–0.211 |
| `mention_overlap` | 0.750 | 0.097 | 0.172 | 0.140–0.204 | 0.748 | 0.115 | 0.200 | 0.162–0.236 |

Counts (`doc_relaxed`): all types TP 86, FP 34, FN 830; apps & plugins TP 85, FP 34, FN 684. Recall by type (document / mention): `APPLICATION` 0.096 / 0.102, `PLUGIN` 0.349 / 0.341, `PROGRAMMINGENVIRONMENT` 0.011 / 0.010, `OPERATINGSYSTEM` 0 / 0.

- **Recall 0.09–0.11:** bio2flow misses nine software in ten. It gives a name in very few sentences, although each sentence was chosen for its software.
- **Precision 0.71:** when it gives a name, it is mostly a software, but still below the 0.92–0.93 of the other tools.

### `plos_methods`

480 methods sections, 1,053 unique names (2.2 per section) for 1,142 gold software.

| Level | P (all) | R (all) | F1 (all) | 95% interval (all) | P (apps & plugins) | R (apps & plugins) | F1 (apps & plugins) | 95% interval (apps & plugins) |
|---|---|---|---|---|---|---|---|---|
| `doc_exact` | 0.451 | 0.416 | 0.433 | 0.387–0.475 | 0.450 | 0.472 | 0.461 | 0.413–0.504 |
| `doc_relaxed` | **0.491** | **0.452** | **0.471** | 0.427–0.511 | **0.490** | **0.513** | **0.501** | 0.456–0.542 |
| `mention_strict` | 0.419 | 0.386 | 0.402 | 0.347–0.451 | 0.418 | 0.442 | 0.430 | 0.371–0.482 |
| `mention_overlap` | 0.468 | 0.432 | 0.449 | 0.396–0.501 | 0.467 | 0.494 | 0.480 | 0.424–0.533 |

Counts (`doc_relaxed`): all types TP 516, FP 534, FN 626; apps & plugins TP 513, FP 534, FN 486. Recall by type: `APPLICATION` 0.485 / 0.474, `PLUGIN` 0.675 / 0.626, `PROGRAMMINGENVIRONMENT` 0.027 / 0.018, `OPERATINGSYSTEM` 0 / 0.

- **About half right, half found:** precision and recall both near 0.5. It gives about as many names as there are gold software, but only half of them match.
- **534 false positives:** more than its true positives. The `errors` will tell names that are not software (on PEPR it gave `Cat`, `append`, `SHA256`, `PC`) from software SoMeSci does not annotate.

### `pubmed_fulltext`

97 full papers, 477 unique names (4.9 per paper) for 285 gold software.

| Level | P (all) | R (all) | F1 (all) | 95% interval (all) | P (apps & plugins) | R (apps & plugins) | F1 (apps & plugins) | 95% interval (apps & plugins) |
|---|---|---|---|---|---|---|---|---|
| `doc_exact` | 0.321 | 0.537 | 0.402 | 0.314–0.481 | 0.319 | 0.592 | 0.414 | 0.324–0.495 |
| `doc_relaxed` | **0.367** | **0.604** | **0.456** | 0.371–0.534 | **0.364** | **0.667** | **0.471** | 0.385–0.550 |
| `mention_strict` | 0.258 | 0.466 | 0.333 | 0.252–0.409 | 0.256 | 0.519 | 0.343 | 0.260–0.423 |
| `mention_overlap` | 0.309 | 0.558 | 0.398 | 0.306–0.492 | 0.307 | 0.622 | 0.411 | 0.313–0.509 |

Counts (`doc_relaxed`): all types TP 172, FP 297, FN 113; apps & plugins TP 170, FP 297, FN 85. Recall by type: `APPLICATION` 0.621 / 0.590, `PLUGIN` 0.944 / 0.848, `PROGRAMMINGENVIRONMENT` 0.118 / 0.074, `OPERATINGSYSTEM` 0 / 0.

- **Its best recall (0.67 on apps & plugins), its worst precision (0.36):** 297 false positives for 170 true positives. A full paper has more text that is not about software (introduction, results, references), where it tags words as tools.
- **Mention level below document level (0.41 against 0.47):** more of its spans are wrong than of its names, consistent with tags on words that are not software.

## Adding a tool

1. Write the outputs of the tool, one file per document, in `data/somesci/<tool>/<run>/`, on the inputs of `prepare` (`data/somesci/input/<run>/`).
2. In `scripts/eval_somesci.py`, add the tool to `TOOLS`, a loader to `LOADERS` and the name of its files to `OUTPUT_NAMES`. A loader gets the output file, the `--explicit-only` flag and the text of the document; it returns the unique `(name, version)` of the document, and its spans in the text, or `None` when the tool has no offsets. `load_bio2flow` is an example of offsets given in paragraphs.
3. Run `evaluate --tool <tool>` on the three configs.
4. Here: add rows to the [comparison](#comparison) and a section for the tool, like the ones above.
