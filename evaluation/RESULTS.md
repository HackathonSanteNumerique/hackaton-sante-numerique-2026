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
| | Softcite | – | – | – | – | – |
| `plos_methods` | Baguette | 0.710 | 0.438 | **0.542** | 0.512 | 0.382 |
| | Softcite | – | – | – | – | – |
| `pubmed_fulltext` | Baguette | 0.634 | 0.456 | **0.531** | 0.519 | 0.574 |
| | Softcite | – | – | – | – | – |

**Differences between the tools:** to be written when the Softcite runs are done. Things to compare:

- **Document level first.** Softcite gives offsets, so its mention level is exact. Baguette gives only names, so its mention level comes from searching them in the text, which is an approximation. Compare mention levels with that in mind.
- **Recall by type:** for example operating systems, which Baguette almost never gives.
- **Inputs:** sentences, methods sections, full papers. Baguette drops a lot on the longer texts.

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

[Softcite software-mentions](../models/README.md#softcite-software-mentions) through the text service of the hackathon 🤗 Space. Not run yet:

```bash
for c in plos_sentences plos_methods pubmed_fulltext; do
  uv run python scripts/eval_somesci.py softcite --config $c
  uv run python scripts/eval_somesci.py evaluate --config $c --tool softcite
done
```

## Adding a tool

1. Write the outputs of the tool, one file per document, in `data/somesci/<tool>/<config>/`.
2. In `scripts/eval_somesci.py`, add the tool to `TOOLS`, a loader to `LOADERS` (it returns the unique `(name, version)` of a document, and its spans, or `None` when the tool has no offsets) and the name of its files to `OUTPUT_NAMES`.
3. Run `evaluate --tool <tool>` on the three configs.
4. Here: add rows to the [comparison](#comparison) and a section for the tool, like the ones above.
