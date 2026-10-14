# Datasets

This page covers the **target corpus** (PEPR Santé Numérique publications, with Softcite predictions but no gold annotations) and the **annotated corpora** you can use for training, evaluation, or comparison.

Figures were checked against the linked sources on 2026-10-13. Counts marked † are our own counts from the released files, not official figures.

- [At a glance](#at-a-glance)
- [PEPR Santé Numérique HAL corpus](#pepr-santé-numérique-hal-corpus): the target corpus
- [SoftCite](#softcite)
- [SoMeSci](#somesci)
- [SoFAIR](#sofair)
- [BioToFlow](#biotoflow)
- [CPL-Article (CoPaLink corpora)](#cpl-article-copalink-corpora)
- [Related: dataESR paragraph categorisation](#related-dataesr-scientific-paragraphs-categorization)
- [Annotation schemes compared](#annotation-schemes-compared)

## At a glance

| Dataset | Domain | Docs | Software mentions | Other annotations | Format | License | Access |
|---|---|---|---|---|---|---|---|
| **PEPR HAL corpus** | Digital health | 264 (of 295 full texts on HAL) | 916 † *Softcite predictions, no gold* | used / created / shared (predicted) | GROBID TEI XML, JSON, Markdown; Softcite JSON | per paper (mostly CC-BY) | 🤗 public |
| **SoftCite v2.0** | Biomedicine + economics | 4,971 | 5,134 | version, publisher, URL, language, relations | TEI XML, JSON | CC-BY 4.0 | Zenodo / GitHub |
| **SoMeSci v1.1** | Biomedicine (PMC) | 1,367 | 3,756 | mention type (usage/creation/deposition/mention), software type, version, developer, URL, license, citation… | brat, RDF (JSON-LD), SPARQL | CC-BY 4.0 | Zenodo / GitHub |
| **SoFAIR** | Multidisciplinary (15 domains) | 298 | 3,295 † | version, publisher, URL, language | TEI XML; 🤗 parquet (BIO) | not declared (CC-BY source papers) | 🤗 gated / GitHub |
| **BioToFlow** | Bioinformatics workflows | 52 | 1,482 `Tool` | 16 entity types, 9 relation types | brat | CC BY-NC-SA 2.0 | Zenodo |
| **CPL-Article** | Bioinformatics workflows | 50 | 1,455 `Tool` (425 unique) | — | brat | CC BY-NC-SA 2.0 | Zenodo |

---

## PEPR Santé Numérique HAL corpus

Publications from the PEPR Santé Numérique HAL collection, processed with GROBID and Softcite. **This is the corpus the hackathon works on.** It has no gold annotations: the software mentions are Softcite's predictions.

- 🤗 **[HackatonSanteNumerique/pepr-hal-data](https://huggingface.co/HackatonSanteNumerique/pepr-hal-data)**: public, not gated, about 112 MB. It's a *model*-type repo, so pass `repo_type="model"` (the default) to `huggingface_hub`; [`scripts/download_pepr.py`](../scripts/download_pepr.py) does it for you.
- HAL collection: **[univ-perp.hal.science/PEPR_SANTENUM](https://univ-perp.hal.science/PEPR_SANTENUM)**.

**Contents.** 264 documents. The same file stem (the paper title in CamelCase) appears in each folder:

| Folder | Files | Size | What it is |
|---|---|---|---|
| `grobid/xml/*.grobid.tei.xml` | 264 | 40 MB | GROBID 0.9.1 TEI, with header consolidation and coordinates on title, persName, affiliation, figure, ref, biblStruct, head, p, s… |
| `grobid/json/*.json` | 264 | 55 MB | JSON version of the TEI: `biblio` (title, authors, publisher, abstract), `body_text[]` (`text`, `head_section`, `coords`, `refs`), `figures_and_tables[]`, `references[]` |
| `grobid/md/*.md` | 264 | 14 MB | Markdown rendering of the body text |
| `softcite/*.tei.software.json` | 204 | 1 MB | Softcite software-mentions (0.9.0-SNAPSHOT) run on the GROBID TEI: one JSON per paper with `biblio` and `mentions[]` (name, version, publisher, URL, language, context, used / created / shared at mention and document level). **916 mentions** †, 191 distinct software, in 97 papers |
| `softcite/*.software.json` | 204 | 1.4 MB | The same, run on the plain text instead of the TEI (no `biblio`) |

> **Note:** there are **no PDFs and no plain-text files**; get PDFs from HAL. Softcite output exists for 204 of the 264 papers. The [starter notebook](../notebooks/softcite_analysis.ipynb) reads `softcite/*.tei.software.json`. To compare with other extractors, run the [models](../models/README.md) on the `grobid/` files.

**The HAL collection** (from the [HAL search API](https://api.archives-ouvertes.fr/search/PEPR_SANTENUM/?q=*:*&rows=0&wt=json)):

- **Size:** 370 records, of which **295** have a full-text file (282 open access). The 🤗 dataset covers 264 of these.
- **Years:** 2024 (90), 2025 (161), 2026 (117), plus one each in 2023 and 2027.
- **Document types:** conference papers (COMM, 120), journal articles (ART, 113), undefined (78), posters (24), **software deposits (SOFTWARE, 10)**, other (16).
- **Languages:** English 322, French 38, undetermined 10.
- **Licences of the full texts:** CC-BY 4.0 (164), HAL authorisation (54), CC-BY-NC-ND (29), CC-BY-NC (18), CC-BY-NC-SA (8), other (22). Check the licence before redistributing anything derived from a paper.

**Things to watch for:**
- Some documents start with the HAL cover page boilerplate ("L'archive ouverte pluridisciplinaire HAL…").
- Posters and slides can have empty titles or abstracts.
- The 10 `SOFTWARE` records in HAL are the PEPR's own software deposits. They make a natural ground truth for software *created* by the PEPR.
- The HAL API gives metadata the GROBID output lacks: year, document type, lab (`structAcronym_s`), domain.

---

## SoftCite

A gold-standard corpus of software mentions in biomedical and economics papers. It is the training data behind the [Softcite software-mentions](../models/README.md#softcite-software-mentions) tool.

- **Papers:** 4,971 English open-access full texts (about 46M tokens): half life sciences (PubMed Central), half economics.
- **Annotation:** double-blind, with disagreements reconciled by a curator.
- **Versions:** v1.0 (2021, [10.5281/zenodo.4445202](https://doi.org/10.5281/zenodo.4445202)) and **v2.0 (2023, [10.5281/zenodo.7995565](https://doi.org/10.5281/zenodo.7995565))**.
- **GitHub:** [softcite/softcite_dataset_v2](https://github.com/softcite/softcite_dataset_v2).
- **License:** data CC-BY 4.0, scripts Apache 2.0.

| Annotation | v1.0 | v2.0 |
|---|---|---|
| software name | 4,093 | **5,134** |
| ↳ environment / component / implicit | – | 1,089 / 88 / 106 |
| version | 1,258 | 1,478 |
| publisher | 1,111 | 1,311 |
| URL | 172 | 231 |
| programming language | – | 71 |

**Scheme.** TEI inline `<rs type="software|version|publisher|url|language">` over GROBID paragraphs. Each attribute points to its software with `@corresp`. Software subtypes are `environment`, `component` and `implicit`. Component→environment links also use `@corresp`.

**Files** (`softcite_dataset_v2.zip`, 25 MB):

| File | Contents |
|---|---|
| `softcite_corpus-full` | Every document, keeping only paragraphs that contain a mention |
| `softcite_corpus-holdout-full` | 20% of documents with **full text** (the realistic distribution, for evaluation) |
| `softcite_corpus-working` | `full` minus the holdout |

Each file comes in TEI XML and a lossy JSON version with character offsets.

**Cite:** Du, C., Cohoon, J., Lopez, P., & Howison, J. (2021). Softcite dataset: A dataset of software mentions in biomedical and economic research publications. *JASIST* 72(7), 870–884. [doi:10.1002/asi.24454](https://doi.org/10.1002/asi.24454)

---

## SoMeSci

*Software Mentions in Science*: a knowledge graph of software mentions in PubMed Central articles. It annotates **why** the software is mentioned.

- **Papers:** 1,367 PMC articles (47,524 sentences, inter-annotator κ = 0.82), in four subsets:

| Subset | Documents |
|---|---|
| PLoS methods sections | 480 |
| PLoS sentences | 677 |
| PubMed full texts | 100 |
| Creation sentences | 110 |

- **Mentions:** **3,756** software mentions, plus 1,381 versions, 858 developers, 588 citations, 347 URLs, 87 releases, 81 abbreviations, 53 licenses and 35 alternative names.
- **Scheme:** each software label combines a type and a mention type:
  - software types: `Application`, `PlugIn`, `ProgrammingEnvironment`, `OperatingSystem`
  - mention types: `Usage`, `Creation`, `Deposition`, `Mention`
  - example labels: `Application_Usage`, `PlugIn_Creation`
- **Relations:** `Version_of`, `Developer_of`, `URL_of`, `License_of`, `Citation_of`, `Abbreviation_of`, `PlugIn_of`… Software is also linked to unique identifiers.
- **Formats:** brat standoff (`.txt` + `.ann`) with a `train_devel_test_split.json`, plus RDF as JSON-LD (NIF vocabulary).
- **SPARQL endpoint:** [data.gesis.org/somesci/sparql](https://data.gesis.org/somesci/sparql), about 400k triples. Site: [data.gesis.org/somesci](https://data.gesis.org/somesci/).
- **Download:** Zenodo v1.1, [10.5281/zenodo.8100213](https://doi.org/10.5281/zenodo.8100213) (concept DOI [10.5281/zenodo.4701763](https://doi.org/10.5281/zenodo.4701763)). GitHub: [dave-s477/SoMeSci](https://github.com/dave-s477/SoMeSci).
- **License:** CC-BY 4.0.

**Cite:** Schindler, D., Bensmann, F., Dietze, S., & Krüger, F. (2021). SoMeSci — A 5 Star Open Data Gold Standard Knowledge Graph of Software Mentions in Scientific Articles. *CIKM '21*, 4574–4583. [doi:10.1145/3459637.3482017](https://doi.org/10.1145/3459637.3482017)

---

## SoFAIR

A **multidisciplinary** software-mention corpus from the CHIST-ERA SoFAIR project. The partners are the Open University (CORE), Inria/HAL and Software Heritage.

- **Papers:** 298 expert-validated documents, all CC-BY papers from CORE with a DOI, published 2019 or later.
- **Domains:** 15, including computer science (30), mathematics (31), medicine (28), engineering (27), physics (27), linguistics (26) and the social sciences and humanities.
- **Mentions** †: 3,295 software (of which 268 environment, 242 component, 219 implicit), 474 versions, 179 publishers, 125 URLs, 53 languages.
- **Scheme:** SoftCite-style TEI (`<rs>` with `@corresp`) with the same attributes. Documents were pre-annotated by Softcite, then corrected by hand and validated by experts.
- 🤗 **[SoFairOA/sofair_dataset](https://huggingface.co/datasets/SoFairOA/sofair_dataset)**: **gated, manual approval** (you share your contact details). Request access early.
  - Configurations: `documents`, `paragraphs`, and `*_w_i` variants without implicit mentions.
  - Fields: `tokens` with BIO `labels` (`SOFTWARE`, `VERSION`, `PUBLISHER`, `URL`, `LANGUAGE`), plus a deduplicated `software` list per document.
- 🤗 **[SoFairOA/sofair_dataset_splits](https://huggingface.co/datasets/SoFairOA/sofair_dataset_splits)**: not gated. Train / validation / test split: 238 / 30 / 30 documents.
- **GitHub:** [SoFairOA/Dataset](https://github.com/SoFairOA/Dataset). Raw annotated TEI is in `tei-annotated/`, validated TEI in `tei-validated/`, guidelines in `guidelines/`.
- **More on 🤗 [SoFairOA](https://huggingface.co/SoFairOA):** SoftCite and SoMeSci converted to the same format (`softcite_dataset`, `somesci_dataset`, `sofair_softcite_somesci`), handy for cross-corpus experiments.
- **License:** not declared on the dataset. The source papers are CC-BY.

**Related paper (benchmark of LLMs vs. classic NER on SoftCite, SoMeSci and SoFAIR):** Pride, D., Guenci, M., Docekal, M., Peroni, S., & Knoth, P. (2025). Identifying and classifying software mentions in full text scholarly documents. *ACM/IEEE JCDL 2025*. [doi:10.1109/jcdl67857.2025.00041](https://doi.org/10.1109/jcdl67857.2025.00041). Its finding: LLM-based approaches clearly outperform rule-based and classic NER methods, especially on the multidisciplinary corpus.

---

## BioToFlow

A corpus annotated with information about **bioinformatics workflows**: tools, data, parameters, environments, and how they connect. It covers far more than software names.

- **Papers:** 52 PubMed articles describing workflows (26 Nextflow, 26 Snakemake). 78,419 tokens, 27,786 of them annotated. Split 39 train / 13 test. About 8% of entities are nested.
- **16 entity types:**

| Entity | Count |
|---|---|
| Data | 2,434 |
| **Tool** | **1,482** |
| Description | 1,300 |
| Biblio | 1,251 |
| Method | 936 |
| WorkflowName | 851 |
| File | 780 |
| Parameter | 464 |
| **Version** | **454** |
| Hardware | 429 |
| Database | 288 |
| ManagementSystem | 243 |
| Container | 108 |
| ProgrammingLanguage | 104 |
| LibraryPackage | 101 |
| Environment | 83 |

- **Hierarchy:** `Data` includes `File` and `Database`. `Environment` includes `Container`, `ManagementSystem`, `LibraryPackage`, `ProgrammingLanguage` and `Hardware`.
- **Relations** †: `DescriptionOf` (477), `BiblioOf` (426), `InputOf` (175), `VersionOf` (168), `IncludeIn` (106), `OutputOf` (92), `ParameterOf` (38), `ComeFrom`, `ExampleOf`.
- **Attributes on Tool and Method:** `BioInfo`, `General`, `Lab`, `Context`.
- **Format:** brat standoff.
- **License:** CC BY-NC-SA 2.0.
- **Download:** Zenodo [10.5281/zenodo.14900544](https://doi.org/10.5281/zenodo.14900544).
- **NER experiments** (BioToFlow + SoftCite): Zenodo [10.5281/zenodo.14879025](https://doi.org/10.5281/zenodo.14879025), code at [gitlab.liris.cnrs.fr/sharefair/ner_workflows](https://gitlab.liris.cnrs.fr/sharefair/ner_workflows).

**Cite:** Sebe, C., Cohen-Boulakia, S., Ferret, O., & Névéol, A. (2025). Extracting Information in a Low-Resource Setting: Case Study on Bioinformatics Workflows. *IDA 2025*, LNCS 15669. [doi:10.1007/978-3-031-91398-3_21](https://doi.org/10.1007/978-3-031-91398-3_21), [arXiv:2411.19295](https://arxiv.org/abs/2411.19295). It reports a SciBERT NER at F = 70.4, close to inter-annotator agreement.

Earlier versions were published in French at TALN 2024 ([hal-04623033](https://hal.science/hal-04623033)) and EGC 2023.

---

## CPL-Article (CoPaLink corpora)

Built for **CoPaLink**, which links bioinformatics tools mentioned in papers to the tools used in the workflow code ("CPL" = CoPaLink). It was expanded from BioToFlow.

- **Papers:** 50 PubMed Central articles describing Nextflow workflows, 76,002 tokens.
- **Annotation:** a single entity type, `Tool`, with no relations. 1,455 occurrences, 425 unique tools.
- **Splits:** 36 train / 14 test, plus five `iteration_{1..5}` train/validation splits.
- **Metadata:** `CPL-Article_info.csv` gives the PMID, DOI, journal and licence of each article.
- **Format:** brat standoff.
- **License:** CC BY-NC-SA 2.0.
- **Download:** Zenodo [10.5281/zenodo.20746904](https://doi.org/10.5281/zenodo.20746904).

**Sibling corpora:**

| Corpus | Contents | Format | License | Zenodo |
|---|---|---|---|---|
| **CPL-Code** | 1,368 Nextflow processes, 3,398 tool occurrences (537 unique) | brat | GPL-3.0+ | [10.5281/zenodo.20746970](https://doi.org/10.5281/zenodo.20746970) |
| **CPL-Gold-Entity-Resolution** | 39 workflows, 490 article↔code tool links | YAML | GPL-3.0+ | [10.5281/zenodo.20746994](https://doi.org/10.5281/zenodo.20746994) |

**Cite:** Sebe, C., Ferret, O., Névéol, A., Esmailoghli, M., Leser, U., & Cohen-Boulakia, S. (2026). Supporting workflow reproducibility by linking bioinformatics tools across papers and executable code. *Bioinformatics* 42(8), btag565. [doi:10.1093/bioinformatics/btag565](https://doi.org/10.1093/bioinformatics/btag565), [arXiv:2603.08195](https://arxiv.org/abs/2603.08195).

---

## Related: dataESR scientific-paragraphs-categorization

🤗 [dataesr/scientific-paragraphs-categorization](https://huggingface.co/datasets/dataesr/scientific-paragraphs-categorization) contains 833k paragraphs from CC-BY publications, mostly in English and French. Each paragraph is labelled as acknowledgements, data mentions, **software/code mentions** or clinical-trial mentions. MIT license, [doi:10.57967/hf/6679](https://doi.org/10.57967/hf/6679).

It is not span-annotated, but it can train or evaluate a paragraph-level filter ("does this paragraph mention software?") before you run NER.

> The Baguette bucket `dataesr/Baguette-Software-Dataset` holds a **model**, not a dataset. See [models](../models/README.md#baguette-dataesr).

---

## Annotation schemes compared

Each corpus defines "software" differently, so **comparing them is a challenge in itself**.

| | SoftCite | SoMeSci | SoFAIR | BioToFlow | CPL-Article |
|---|---|---|---|---|---|
| Software entity | `software` (+ environment / component / implicit) | Application, PlugIn, ProgrammingEnvironment, OperatingSystem | as SoftCite | `Tool` (+ Method, LibraryPackage, ManagementSystem, Container…) | `Tool` |
| Purpose of the mention | ✗ in the corpus (the Softcite tool predicts used/created/shared) | ✅ Usage / Creation / Deposition / Mention | ✗ | Attributes on Tool: BioInfo / General / Lab / Context | ✗ |
| Version | ✅ | ✅ | ✅ | ✅ | ✗ |
| Publisher / developer | ✅ | ✅ | ✅ | ✗ | ✗ |
| URL | ✅ | ✅ | ✅ | ✗ | ✗ |
| Programming language | ✅ | (ProgrammingEnvironment) | ✅ | ProgrammingLanguage | ✗ |
| License / citation | ✗ | ✅ | ✗ (bibr refs only) | Biblio | ✗ |
| Relations | `@corresp` | ✅ typed `*_of` | `@corresp` | ✅ 9 types | ✗ |
| Unit | full-text paragraphs | sentences / methods / full text | full text | full text | full text |
| Format | TEI XML / JSON | brat / JSON-LD | TEI XML / BIO parquet | brat | brat |

Some practical consequences:

- To evaluate one model across corpora, map everything down to the common core: **software name, plus version where available**.
- SoftCite, SoFAIR and the PEPR corpus all use GROBID TEI, so the Softcite tool runs on them unchanged.
- BioToFlow and CPL count *tools* and *methods* in bioinformatics workflows. Their notion of "tool" differs from SoftCite's "software". For example, a programming language is a separate entity in BioToFlow but a software *environment* in SoftCite.
