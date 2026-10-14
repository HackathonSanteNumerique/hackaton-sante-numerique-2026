# Models & tools

| Tool | What it extracts | Trained on | Access |
|---|---|---|---|
| [**Softcite software-mentions**](#softcite-software-mentions) | software name, version, publisher, URL, language; *used / created / shared*; Wikidata linking | SoftCite | 🤗 Space (REST API), or Docker |
| [**CoPaLink**](#copalink) | bioinformatics `Tool` mentions in papers and Nextflow code, plus article↔code linking | CPL-Article, CPL-Code (BioToFlow lineage) | LIRIS GitLab ([nlp_models](https://gitlab.liris.cnrs.fr/sharefair/nlp_models)); run locally (GPU or CPU) with [`copalink_client.py`](#run-the-paper-text-ner-on-the-pepr-corpus) |
| [**Baguette**](#baguette-dataesr) (dataESR) | software and dataset mentions per paragraph, with role and type (generative LLM, JSON output) | distilled from Qwen3.5-27B | 🤗 bucket; served through [`lm-inference`](#lm-inference) |

Plus [external data sources](#external-data) to enrich your results.

---

## Softcite software-mentions

A [GROBID](https://github.com/kermitt2/grobid) module for software mention recognition.

- **Repo:** [github.com/softcite/software-mentions](https://github.com/softcite/software-mentions) (Apache 2.0).
- **Models:** CRF, BiLSTM-CRF and SciBERT-based sequence labelling, via [DeLFT](https://github.com/kermitt2/delft).
- **Output:** JSON with PDF coordinates. Each mention carries:
  - `software-name`, `version`, `publisher`, `url`, `language`
  - `mentionContextAttributes` and `documentContextAttributes`, each with `used`, `created` and `shared` (value + score)
  - an optional Wikidata ID

**Hackathon endpoint:** `https://lfoppiano-softcite-software-mentions.hf.space/` (Hugging Face Space). Open it in a browser for the web console.

```bash
SOFTCITE=https://lfoppiano-softcite-software-mentions.hf.space

# plain text
curl -X POST -d "text=Analyses were performed with SPSS v25 and R 4.3." $SOFTCITE/service/processSoftwareText
# PDF
curl --form input=@paper.pdf $SOFTCITE/service/annotateSoftwarePDF
# GROBID TEI: the PEPR corpus grobid/xml/ files can go in as they are
curl --form input=@paper.grobid.tei.xml $SOFTCITE/service/annotateSoftwareTEI
```

The Space is shared by everyone, so `503` means it's busy: wait a couple of seconds and send the request again.

**The PEPR corpus is already annotated:** the Softcite output for 204 of the 264 papers is in `softcite/` on the [🤗 repo](https://huggingface.co/HackatonSanteNumerique/pepr-hal-data), and the [starter notebook](../notebooks/softcite_analysis.ipynb) reads it:

```bash
uv run python scripts/download_pepr.py --pattern "softcite/*"
```

To re-run Softcite yourself (the 60 missing papers, other settings, a newer model), write the output to a separate folder and point the notebook's `DATA_DIR` at it:

```bash
uv run python scripts/download_pepr.py --pattern "grobid/xml/*"
mkdir -p data/softcite-rerun
for f in data/pepr-hal-data/grobid/xml/*.grobid.tei.xml; do
  b=$(basename "$f" .grobid.tei.xml)
  curl -s --form input=@"$f" $SOFTCITE/service/annotateSoftwareTEI \
    > "data/softcite-rerun/$b.tei.software.json"
done
```

For large batches with concurrency and retries on `503`, use the Python client [softcite/software_mentions_client](https://github.com/softcite/software_mentions_client).

**Run your own instance with Docker** if you need more throughput (the image is about 11 GB; use a GPU if you have one), then set `SOFTCITE=http://localhost:8060`:

```bash
docker pull grobid/software-mentions:0.8.1
docker run --rm --gpus all --init --ulimit core=0 -p 8060:8060 grobid/software-mentions:0.8.1
# without GPU: drop --gpus all
```

---

## CoPaLink

The tool that comes with the paper *Supporting workflow reproducibility by linking bioinformatics tools across papers and executable code* (Sebe et al., [Bioinformatics 42(8) btag565, 2026](https://academic.oup.com/bioinformatics/article/42/8/btag565/8747618)).

It works in three steps:

1. **NER on the paper text:** BiLSTM-CRF via NLStruct with SciBERT embeddings and vocabulary injection. F1 = 77.2 on CPL-Article.
2. **NER on Nextflow code:** CodeBERT with vocabulary injection. F1 = 90.1 on CPL-Code.
3. **Linking:** entity resolution of tools between paper and code using Sentence-BERT (`all-MiniLM-L6-v2`). Joint accuracy is 66.

**Where to get it.** The code and the trained NER checkpoints live in the GitLab repo. There is **nothing on Hugging Face**.

| | Location |
|---|---|
| Code | [gitlab.liris.cnrs.fr/sharefair/copalink](https://gitlab.liris.cnrs.fr/sharefair/copalink) (Zenodo [10.5281/zenodo.20747871](https://doi.org/10.5281/zenodo.20747871), 1.4 GB) |
| Experiments | [gitlab.liris.cnrs.fr/sharefair/copalink-experiments](https://gitlab.liris.cnrs.fr/sharefair/copalink-experiments) |
| Paper-text checkpoint | `modele_mlm_choose/csebe_scibert_bioinfo_voc_iteration4_seed100.pt` |
| Code checkpoint | `modele_mlm_choose/csebe_codebert_bioinfo_voc_iteration3_seed100.pt` |
| BioToFlow NER (earlier model) | [gitlab.liris.cnrs.fr/sharefair/ner_workflows](https://gitlab.liris.cnrs.fr/sharefair/ner_workflows) |

The repo runs in a Conda environment and uses the git submodules `bioflow-insight` and `nlstruct`.

```bash
python main.py --name <workflow> --path_file_publication <article.txt> \
  --path_code <nextflow_dir> --extract_processes --predict_data --delete_temporary_files
```

The licences disagree: the GitLab repo says AGPL-3.0, Zenodo says GPL-3.0-or-later.

On the PEPR corpus, only the **paper-text NER** applies, since there is no workflow code. The model was trained on bioinformatics workflows, so expect a domain shift.

### Run the paper-text NER on the PEPR corpus

[sharefair/nlp_models](https://gitlab.liris.cnrs.fr/sharefair/nlp_models) packages just that model (`csebe_scibert_bioinfo_voc_iteration4_seed100.pt`, 474 MB, via git-lfs). Its own `predict_files.py` only reads a folder of `.txt` files. [`scripts/copalink_client.py`](../scripts/copalink_client.py) reads the same inputs as the Baguette client, GROBID TEI included:

- `.xml` (GROBID TEI): the `<p>` elements of the abstract, body and back; figure captions are left out
- `.txt` / `.md`: blocks separated by blank lines
- `.json`: a list of strings, or an object with `paragraphs` or `text`

It uses the **GPU** when there is one (CUDA, or MPS on a Mac) and falls back to the CPU; `--device cpu` (or `cuda:1`, `mps`) forces a device. On a Mac, some nlstruct operations crash on MPS (`Unaligned blit request`): the client then retries the paper on the CPU and stays there for the rest of the run. On CPU it takes 15–30 s per PEPR paper on a 24-core machine, so all 264 papers take about 1.5 h.

**Setup**, in the `copalink-experiments` Conda environment of nlp_models (see its README):

```bash
git lfs install
git clone https://gitlab.liris.cnrs.fr/sharefair/nlp_models.git
cd nlp_models
git clone https://github.com/ClemenceS/nlstruct.git
conda env create -f environment.yml && conda activate copalink-experiments
```

`nlstruct` needs **transformers 4.x**: transformers 5 removed `tokenizer.encode_plus`, and every paper fails with `BertTokenizer has no attribute encode_plus`. The Conda environment pins 4.56.1. In any other environment, run `pip install "transformers==4.56.1"`; the client refuses to start with 5.x.

**Run**, from the `nlp_models` folder (the defaults of `--model` and `--nlstruct` point there):

```bash
H=../hackaton-sante-numerique-2026      # this repo
python $H/scripts/copalink_client.py \
  --input-folder $H/data/pepr-hal-data/grobid/xml \
  --output-dir $H/data/copalink --csv-output $H/data/copalink.csv \
  --softcite-dir $H/data/copalink-softcite \
  --brat-dir $H/data/copalink-brat
```

You can stop it with Ctrl+C and run the same command again: the papers that already have their files in `--output-dir` and `--softcite-dir` are skipped, and failed ones are retried.

Other options: `--text "..."` for a quick test, `--input-file a.xml b.xml` for a few papers, and `--device` to choose the device (default `auto`).

**Output:**

- **JSON per paper** (`<file>.json`), shaped like the Baguette response:
  - `paragraphs[]`: each with `index`, `text` and `entities[]`
  - each entity has `text`, `type` (`Tool`), `attributes`, `begin` / `end` offsets within the paragraph, and `confidence`
  - `mentions`: deduplicated by lower-cased text and type
  - `duration_seconds` and `model`
- **`--softcite-dir`:** the same predictions in the **JSON schema of Softcite** (`<paper>.tei.software.json`, the file names of the Softcite output), so code written for Softcite reads them too. Each `Tool` entity is a mention with `type` and `software-type` set to `software`, and a `software-name` (`rawForm`, `normalizedForm`, `offsetStart` / `offsetEnd`). For TEI inputs, `biblio` holds the title, authors and DOI. Differences from Softcite:
  - the `context` is the **paragraph**, not the sentence; the offsets are relative to it
  - no `version`, `publisher`, `url` or `language`: CoPaLink only finds the name
  - no `mentionContextAttributes` / `documentContextAttributes`: CoPaLink doesn't say whether the software is used, created or shared

  The [starter notebook](../notebooks/softcite_analysis.ipynb) runs on it if you set `DATA_DIR` to that folder, except the cells about purposes and programming languages, which come out empty.
- **CSV summary:** one row per paper.
- **`--brat-dir`:** `<paper>.txt` + `<paper>.ann`, in the format of `predict_files.py`, to open in the brat viewer that comes with nlp_models.

---

## Baguette (dataESR)

A small generative model from the French Ministry's dataESR team. For each paragraph it extracts **software and dataset mentions**.

- **Weights:** 🤗 bucket [`dataesr/Baguette-Software-Dataset`](https://huggingface.co/buckets/dataesr/Baguette-Software-Dataset), public, about 1.4 GB. The bucket also has `inference_example.py`.
- **Architecture:** `LlamaForCausalLM`, 608M parameters, 8k context, bfloat16. Base model: Pleias *balanced-600M*.
- **Training:** distilled from a Qwen3.5-27B teacher on about 531k examples. Languages: English and French.
- **Step 1 (validated):** paragraph → `{is_boilerplate, datasets[], software[]}`. Each mention has a **role** (`produced` / `reused` / `mentioned`), a type, and a verbatim evidence span.
- **Step 2 (functional, not validated):** an article-level record built from the step-1 mentions.
- **Evaluation:** 89% agreement with the teacher on 685 held-out paragraphs. This is **not** accuracy against human gold data; none exists yet.
- **Prompt:** the tokenizer has no chat template. Use greedy decoding and stop at `<|im_end|>`:
  ```
  <|im_start|>user\n<text>{paragraph}</text><|im_end|>\n<|im_start|>assistant\n
  ```
- **License:** not set yet ("to be set by the owner before public release").
- **Gotcha:** `inference_example.py` refers to the model as `PleIAs/Baguette-Software-Dataset`, which isn't public. Download the weights from the bucket instead.

The `produced` / `reused` / `mentioned` roles roughly map to Softcite's `created` / `used` / `shared`, and to SoMeSci's `Creation` / `Usage` / `Mention`. That makes Baguette a natural candidate for the "created vs. used" comparison.

### lm-inference

[ScienciaLAB/lm-inference](https://github.com/ScienciaLAB/lm-inference) (Apache-2.0) has the scripts that deploy document-AI models as serverless apps on [Modal](https://modal.com/), Baguette among them. The Baguette service runs vLLM on L4 GPUs (at most 4 containers by default). The full documentation is in [`deployments/baguette/readme.md`](https://github.com/ScienciaLAB/lm-inference/tree/main/deployments/baguette). Until [PR #31](https://github.com/ScienciaLAB/lm-inference/pull/31) is merged, read it on the [`feature/baguette-server-splitting`](https://github.com/ScienciaLAB/lm-inference/blob/feature/baguette-server-splitting/deployments/baguette/readme.md) branch.

> **Hackathon endpoint:** `https://sciencialab--baguette-software-dataset-app-extract-endpoint.modal.run/` (POST only). Every call uses real GPU time, so test on a few papers before you run a whole folder.

**One request = one paper.** Send the paper whole; the server splits it into pieces of about 200 tokens, because the model only works on inputs the size of a paragraph.

```bash
URL=https://sciencialab--baguette-software-dataset-app-extract-endpoint.modal.run/

# a text
curl -X POST $URL -H 'Content-Type: application/json' \
  -d '{"text": "Analyses were performed with SPSS v25 and R 4.3."}'

# a GROBID TEI file from the PEPR corpus, without step 2
curl -X POST $URL -F 'file=@data/pepr-hal-data/grobid/xml/<paper>.grobid.tei.xml' -F 'analyze=false'

# paragraphs you split yourself
curl -X POST $URL -H 'Content-Type: application/json' \
  -d '{"paragraphs": ["First paragraph.", "Second paragraph."], "analyze": false}'
```

- **Input:** `text` (JSON, plain-text body or form field), `file` (`.txt`, `.md`, `.xml` TEI or `.json`), or `paragraphs` (a list of strings).
- **TEI files:** the server reads the `<p>` elements of the abstract, body and back. Figure and table captions are left out.
- **`analyze`:** defaults to `true` and runs step 2. Pass `false` if you only need the mentions.

**Response:**

- `paragraphs[]`: per paragraph, `is_boilerplate`, `datasets` and `software`. Each mention has `name`, `role` and `evidence`; split paragraphs also have `chunks`, and failed ones `error` and `raw_output`.
- `mentions`: deduplicated by lower-cased name
- `record`: the step-2 output, with `record_error` when it fails
- `duration_seconds`, `cost_usd` and `gpu`

HTTP 400 means the input couldn't be read; HTTP 500 means the service failed.

**Batch client:** needs only `requests`. It writes one JSON file per paper plus a CSV summary, retries on 5xx errors, and on a second run skips papers that already succeeded:

```bash
git clone https://github.com/ScienciaLAB/lm-inference.git
python lm-inference/deployments/baguette/baguette_client.py --endpoint $URL \
  --input-folder data/pepr-hal-data/grobid/xml \
  --output-dir data/baguette --csv-output data/baguette.csv \
  --threads 4 --no-analyze
```

Keep `--threads` at 4 or below: that's the number of GPU containers the service runs.

**Things to know:**

- The first request after an idle period waits for a container to start, which takes more than a minute. The client's timeout is 30 minutes.
- Deduplication is by name only, so `R` and `R 4.2.1` count as two software.
- A mention cut between two pieces can be lost.
- The output isn't checked against a schema, so the fields of a mention may vary.

---

## External data

- **[OpenAlex](https://openalex.org/)** ([API docs](https://docs.openalex.org/)): metadata, citations, authors, institutions and topics. Look papers up by DOI to build author ↔ software or institution ↔ software networks.
- **[HAL API](https://api.archives-ouvertes.fr/docs/search)**: year, document type, labs and domains for the PEPR collection. For example: `https://api.archives-ouvertes.fr/search/PEPR_SANTENUM/?q=*:*&fl=halId_s,title_s,docType_s,producedDateY_i,structAcronym_s&rows=500&wt=json`.
- **[Software Heritage](https://www.softwareheritage.org/)**: archived source code, useful for linking detected software to repositories.
- **[Wikidata](https://www.wikidata.org/)**: useful for normalising names and finding licence, language and developer.
- **[bio.tools](https://bio.tools/)**: a registry of bioinformatics tools, also used by CoPaLink.
