# Models & tools

| Tool | What it extracts | Trained on | Access |
|---|---|---|---|
| [**Softcite software-mentions**](#softcite-software-mentions) | software name, version, publisher, URL, language; *used / created / shared*; Wikidata linking | SoftCite | Docker image, REST API |
| [**CoPaLink**](#copalink) | bioinformatics `Tool` mentions in papers and Nextflow code, plus article↔code linking | CPL-Article, CPL-Code (BioToFlow lineage) | LIRIS GitLab + Zenodo (checkpoints in the repo) |
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

**Run it with Docker** (the image is about 11 GB; use a GPU if you have one):

```bash
docker pull grobid/software-mentions:0.8.1
docker run --rm --gpus all --init --ulimit core=0 -p 8060:8060 grobid/software-mentions:0.8.1
# without GPU: drop --gpus all
# web console at http://localhost:8060
```

**Endpoints:**

```bash
# plain text
curl -X POST -d "text=Analyses were performed with SPSS v25 and R 4.3." localhost:8060/service/processSoftwareText
# PDF
curl --form input=@paper.pdf --form disambiguate=1 localhost:8060/service/annotateSoftwarePDF
# GROBID TEI: the PEPR corpus xml/ files can go in as they are
curl --form input=@paper.grobid.tei.xml --form disambiguate=1 localhost:8060/service/annotateSoftwareTEI
```

**Annotate the whole PEPR corpus** into the format the [starter notebook](../notebooks/softcite_analysis.ipynb) expects:

```bash
uv run python scripts/download_pepr.py --pattern "xml/*"
mkdir -p data/software-mentions
for f in data/pepr-hal-data/xml/*.grobid.tei.xml; do
  b=$(basename "$f" .grobid.tei.xml)
  curl -s --form input=@"$f" localhost:8060/service/annotateSoftwareTEI \
    > "data/software-mentions/$b.tei.software.json"
done
```

For large batches with concurrency and retries on `503`, use the Python client [softcite/software_mentions_client](https://github.com/softcite/software_mentions_client).

> **HF Space:** a hosted Softcite demo for the hackathon is *to be confirmed*.

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

On the PEPR corpus, only the **paper-text NER** applies, since there is no workflow code. Feed it the Markdown or text from `pepr-hal-data`. The model was trained on bioinformatics workflows, so expect a domain shift.

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

[ScienciaLAB/lm-inference](https://github.com/ScienciaLAB/lm-inference) (Apache-2.0) has the scripts that deploy document-AI models as serverless apps on [Modal](https://modal.com/), Baguette among them. The Baguette deployment runs vLLM on one L4 GPU.

```bash
pip install -r deployments/requirements.txt
modal deploy deployments/baguette/inference_baguette.py
```

**Call it:**

```bash
curl -X POST https://<workspace>--baguette-software-dataset-app-extract-endpoint.modal.run/ \
  -H 'Content-Type: application/json' \
  -d '{"paragraphs": ["We used SPSS v25 for the statistical analysis."], "analyze": true}'
```

The response contains:

- `paragraphs[]`: per paragraph, `is_boilerplate`, `datasets` and `software`
- `mentions`: deduplicated by name
- `record`: the step-2 output
- `duration_seconds` and `cost_usd`

**Batch client:** reads GROBID TEI `<p>` elements, JSON lists, or blank-line-separated text and Markdown, so it works on the PEPR corpus as is:

```bash
python deployments/baguette/baguette_client.py \
  --input_folder data/pepr-hal-data/xml --output_dir data/baguette --csv_output data/baguette.csv \
  --endpoint <endpoint-url> --threads 4
```

> The organisers will share the endpoint URL for the hackathon.

---

## External data

- **[OpenAlex](https://openalex.org/)** ([API docs](https://docs.openalex.org/)): metadata, citations, authors, institutions and topics. Look papers up by DOI to build author ↔ software or institution ↔ software networks.
- **[HAL API](https://api.archives-ouvertes.fr/docs/search)**: year, document type, labs and domains for the PEPR collection. For example: `https://api.archives-ouvertes.fr/search/PEPR_SANTENUM/?q=*:*&fl=halId_s,title_s,docType_s,producedDateY_i,structAcronym_s&rows=500&wt=json`.
- **[Software Heritage](https://www.softwareheritage.org/)**: archived source code, useful for linking detected software to repositories.
- **[Wikidata](https://www.wikidata.org/)**: Softcite already links mentions to it with `disambiguate=1`. It's useful for normalising names and finding licence, language and developer.
- **[bio.tools](https://bio.tools/)**: a registry of bioinformatics tools, also used by CoPaLink.
