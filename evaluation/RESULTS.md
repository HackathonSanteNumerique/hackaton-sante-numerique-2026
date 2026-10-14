# Results on SoMeSci

Scores of the software-mention tools against [SoMeSci](../datasets/README.md#somesci), computed by [`scripts/eval_somesci.py`](../scripts/eval_somesci.py). How they are computed, and their limits, are in [README.md](README.md).

- **Main score:** document level with relaxed matching (`doc_relaxed`): the software of a document against the unique names given by the tool.
- **All the numbers:** `data/somesci/results/<tool>/<config>.json`, with the errors of each document.
- **Run:** all software types, implicit mentions included (no `--explicit-only`, no `--exclude-os`), unless written otherwise.

## Comparison

Document level, relaxed matching:

| Config | Tool | P | R | F1 | F1 mention (overlap) | F1 version |
|---|---|---|---|---|---|---|
| `plos_sentences` | Baguette | 0.915 | 0.746 | **0.822** | 0.770 | 0.529 |
| | Softcite | 0.932 | 0.879 | **0.904** | 0.906 | 0.939 |
| `plos_methods` | Baguette | 0.710 | 0.438 | **0.542** | 0.512 | 0.382 |
| | Softcite | 0.787 | 0.834 | **0.809** | 0.791 | 0.888 |
| `pubmed_fulltext` | Baguette | 0.634 | 0.456 | **0.531** | 0.519 | 0.574 |
| | Softcite | 0.836 | 0.807 | **0.821** | 0.793 | 0.935 |

Recall by type, document level (relaxed):

| Type | Baguette sentences | Softcite sentences | Baguette methods | Softcite methods | Baguette full papers | Softcite full papers |
|---|---|---|---|---|---|---|
| `APPLICATION` | 0.797 | **0.939** | 0.429 | **0.860** | 0.475 | **0.872** |
| `PROGRAMMINGENVIRONMENT` | 0.785 | **0.989** | 0.598 | **0.920** | 0.471 | **0.706** |
| `PLUGIN` | 0.674 | **0.698** | 0.450 | **0.775** | 0.472 | **0.750** |
| `OPERATINGSYSTEM` | 0.037 | 0.018 | 0.032 | 0.097 | 0.077 | 0.000 |

**Differences between the tools:**

- **Softcite is better on all three configs:** F1 0.90 against 0.82 on sentences, 0.81 against 0.54 on methods sections, 0.82 against 0.53 on full papers.
- **Longer texts hurt Baguette much more.** From sentences to longer texts, Softcite loses 0.08 to 0.10 of F1, Baguette about 0.28. Both tools got the same inputs: one block per sentence or methods section, the same paragraphs for the full papers. Softcite segments each text itself, while Baguette's server cuts long texts into pieces of about 200 tokens and the model misses mentions in long inputs. That points at how Baguette handles longer inputs, to be confirmed in the `errors`.
- **Recall is Baguette's main problem.** On sentences, precision is about the same (0.93 against 0.92) and only recall differs (0.88 against 0.75). On longer texts, Baguette gives far fewer names than there are gold software (719 for 1,142 on methods sections, 208 for 285 on full papers), and its recall falls below 0.46. Softcite gives about as many names as there are gold software, and keeps recall above 0.8.
- **Versions are where the gap is largest:** F1 0.89 to 0.94 for Softcite, 0.38 to 0.57 for Baguette, with the same metric. So the weak version scores of Baguette come from Baguette, not from the way versions are scored.
- **By type:** Softcite finds most applications (0.86–0.94) and programming environments (0.71–0.99) in every config. Plugins are the weakest type of both tools on sentences (about 0.7).
- **Operating systems:** neither tool gives them (recall 0.02–0.04). This is a choice of SoMeSci, which annotates them as software, more than a fault of the tools. `--exclude-os` gives the scores without them.
- **Exact names:** Softcite loses less from relaxed to exact matching (e.g. 0.90 → 0.82 on sentences) than Baguette (0.82 → 0.68): its names are closer to the annotated forms.
- **Mention level:** Softcite gives offsets, so its mention level is exact (F1 0.91, overlap). Baguette gives only names, and its mention level comes from searching them in the text (0.77). Compare the tools at document level first.
- **Training data:** Softcite is trained on the Softcite corpus (biomedical and economics papers), close to the PLoS and PMC papers of SoMeSci. Baguette is distilled from an LLM, on English and French papers. Neither was trained on SoMeSci, as far as we know.

## Baguette

[Baguette](../models/README.md#baguette-dataesr) through the hackathon endpoint, `--no-analyze` (step 1 only).

### Summary

| Config | Documents | Gold software | Predicted names | P | R | F1 | F1 mention (overlap) |
|---|---|---|---|---|---|---|---|
| `plos_sentences` | 677 | 916 | 753 | 0.915 | 0.746 | **0.822** | 0.770 |
| `plos_methods` | 480 | 1,142 | 719 | 0.710 | 0.438 | **0.542** | 0.512 |
| `pubmed_fulltext` | 97 | 285 | 208 | 0.634 | 0.456 | **0.531** | 0.519 |

- **Sentences against longer texts:** Baguette does well on single sentences (F1 0.82). On methods sections and full papers it drops to about 0.53–0.54, with both precision and recall lower.
- **Methods sections are as hard as full papers.** A methods section is sent as one paragraph, which the server cuts into pieces of about 200 tokens. So the drop seems to come with the length of the input, more than with the parts of the paper (introduction, references…) that only a full text has. This is a hypothesis, to check in the `errors`.
- **Baguette gives fewer names than there are gold software** on the longer texts: 719 against 1,142 on methods sections, 208 against 285 on full papers. Recall is the main problem there.

### `plos_sentences`

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
- **Versions are weak (F1 0.53)**, on the 683 software found: about half of the predicted versions are not the gold one, and 213 of the 479 gold versions are missed. Part of it can come from the way versions are written or attached in SoMeSci (see [Limits](README.md#limits)); the `version_errors` show which.

The `errors` of the results JSON tell real misses apart from differences of name that relaxed matching does not catch.

### `plos_methods`

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

### `pubmed_fulltext`

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

## Softcite

[Softcite software-mentions](../models/README.md#softcite-software-mentions) through the text service of the hackathon 🤗 Space (`software-mentions` 0.9.0-SNAPSHOT).

```bash
for c in plos_sentences plos_methods pubmed_fulltext; do
  uv run python scripts/eval_somesci.py softcite --config $c
  uv run python scripts/eval_somesci.py evaluate --config $c --tool softcite
done
```

### Summary

| Config | Documents | Gold software | Predicted names | P | R | F1 | F1 mention (overlap) |
|---|---|---|---|---|---|---|---|
| `plos_sentences` | 677 | 916 | 866 | 0.932 | 0.879 | **0.904** | 0.906 |
| `plos_methods` | 480 | 1,142 | 1,227 | 0.787 | 0.834 | **0.809** | 0.791 |
| `pubmed_fulltext` | 97 | 285 | 281 | 0.836 | 0.807 | **0.821** | 0.793 |

- **Stable across inputs:** F1 0.90 on sentences, about 0.81–0.82 on methods sections and full papers.
- **It gives about as many names as there are gold software** in every config: precision and recall stay close to each other.

### `plos_sentences`

677 sentences. Softcite gave 866 unique names. Its names come with offsets, so all are in the text.

| Level | P | R | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| `doc_exact` | 0.841 | 0.795 | 0.817 | 728 | 138 | 188 |
| `doc_relaxed` | **0.932** | **0.879** | **0.904** | 805 | 59 | 111 |
| `mention_strict` | 0.839 | 0.789 | 0.813 | 755 | 145 | 202 |
| `mention_overlap` | 0.934 | 0.879 | 0.906 | 841 | 59 | 116 |
| `version` | 0.921 | 0.958 | 0.939 | 527 | 45 | 23 |

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

| Level | P | R | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| `doc_exact` | 0.685 | 0.736 | 0.709 | 840 | 387 | 302 |
| `doc_relaxed` | **0.787** | **0.834** | **0.809** | 952 | 258 | 190 |
| `mention_strict` | 0.704 | 0.672 | 0.688 | 1051 | 442 | 512 |
| `mention_overlap` | 0.810 | 0.773 | 0.791 | 1209 | 284 | 354 |
| `version` | 0.900 | 0.876 | 0.888 | 423 | 47 | 60 |

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

| Level | P | R | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| `doc_exact` | 0.730 | 0.719 | 0.724 | 205 | 76 | 80 |
| `doc_relaxed` | **0.836** | **0.807** | **0.821** | 230 | 45 | 55 |
| `mention_strict` | 0.706 | 0.645 | 0.674 | 267 | 111 | 147 |
| `mention_overlap` | 0.831 | 0.758 | 0.793 | 314 | 64 | 100 |
| `version` | 0.940 | 0.931 | 0.935 | 94 | 6 | 7 |

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

## Adding a tool

1. Write the outputs of the tool, one file per document, in `data/somesci/<tool>/<config>/`.
2. In `scripts/eval_somesci.py`, add the tool to `TOOLS`, a loader to `LOADERS` (it returns the unique `(name, version)` of a document, and its spans, or `None` when the tool has no offsets) and the name of its files to `OUTPUT_NAMES`.
3. Run `evaluate --tool <tool>` on the three configs.
4. Here: add rows to the [comparison](#comparison) and a section for the tool, like the ones above.
