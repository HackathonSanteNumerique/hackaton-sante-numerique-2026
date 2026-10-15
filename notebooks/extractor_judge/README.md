# Extractor judge

An LLM judge labels a sample of the software found by Softcite, Baguette and bio2flow on the PEPR corpus, for section 8 of [`extractor_comparison.ipynb`](../extractor_comparison.ipynb).

| File | What it is |
|---|---|
| `candidates.jsonl` | The sample, written by section 7 of the notebook (fixed seed): `id`, `paper`, `region` (the tools that found it), `names`, and one context per tool |
| `items.jsonl` | What the judge sees: `id`, `name`, `contexts` (no region, no tool names) |
| `judgments.jsonl` | The judge's answers: `id`, `category`, `is_software`, `confidence`, `reason` |

**How it was run (2026-10-15):** Claude Haiku (`claude-haiku-5-5`), as three Claude Code subagents of about 95 items each, with the instructions below. One pass, no access to the papers beyond the contexts.

## Instructions given to the judge

You label candidate software mentions extracted automatically from scientific papers (digital health, bioinformatics, machine learning, statistics). Each item has a `name` and one to three `contexts`: text from the paper where the name appears.

For each item, decide what the name refers to **in these contexts**, and pick one `category`:

- `software`: a specific, named program, library, package, toolkit, framework, application, plugin, workflow system or web tool that people run or install (e.g. PyTorch, samtools, ImageJ, Monolix, scikit-learn, Snakemake, ChatGPT used as a tool, Excel, Docker, Linux).
- `programming_language`: a programming language or computing environment (Python, R, MATLAB as a language, C++, SQL).
- `ml_model`: a trained model, a model architecture or model family, used as a model rather than as software (ResNet, BERT, VGG16, GPT-4, DINOv2, U-Net).
- `database`: a named database or knowledge base (Ensembl, UniProt, GENCODE).
- `platform_service`: a hosting platform, repository or online service that is not itself the analysed software (GitHub, Zenodo, Hugging Face hub, CRAN, an institution's computing cluster).
- `dataset`: a named dataset or corpus (ImageNet, MNIST, UK Biobank data).
- `method`: an algorithm, statistical method, optimizer, metric, protocol or mathematical object (LASSO, Adam, SHAP as a method, FedAvg as an algorithm, BIC, ReLU, PCA).
- `generic`: a generic word, not a name (code, scripts, software, tool, model, pipeline).
- `other`: anything else (a person, a citation like "Peng et al.", an organisation, a file name, an extraction error, a word fragment).

Then set `is_software` to `true` only when the category is `software` or `programming_language`. When a name is both a method and a software package (SHAP, FedAvg, Mapper), choose by the context: `software` if the context refers to the implementation (a package, a library, a call, a version, "implemented in", "using the X package"), `method` if it refers to the technique.

Give a `confidence` (`high`, `medium`, `low`) and a short `reason` (at most 15 words).

Output one JSON object per line, in the input order, with exactly these keys:

```json
{"id": "c000", "category": "software", "is_software": true, "confidence": "high", "reason": "BioRender, an online figure-drawing application, used to make a figure."}
```
