---
marp: true
theme: default
paginate: true
size: 16:9
header: 'Hackathon — Software Mention Extraction · Digital Health Seminar 2026'
footer: 'Luca Foppiano & Clémence Sebe · Marseille, 14–15 Oct 2026'
style: |
  section { font-size: 26px; }
  h1 { color: #1f4e79; }
  h2 { color: #1f4e79; }
  table { font-size: 22px; }
  .small { font-size: 18px; }
  .logos { position: absolute; bottom: 40px; left: 0; right: 0;
           display: flex; justify-content: center; gap: 48px; align-items: center; }
  .logos img { height: 55px; }

---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _header: '' -->

# Séminaire Santé Numérique 2026

**Hackathon — extraction de logiciels**
Campus Biaggi, Marseille · Salle Australie · 14–15 October 2026

Luca Foppiano (ScienciaLAB, Inria) · Clémence Sebe (LISN, Université Paris-Saclay)

<div class="logos">
  <img src="logos/rt-santenum.svg">
  <img src="logos/inria.svg">
  <img src="logos/sciencialab.png">
</div>


---

## Morning programme (9:00 – 9:30)

| Duration | Talk |
|---|---|
| 10 min | **Luca** — SoftCite & HAL publications |
| 10 min | **Clémence** — BioToFlow & NER methods |
| 10 min | **The hackathon** — goals, resources, organisation |

---

<!-- _class: lead -->

# Part 1 — SoftCite & HAL
*Luca Foppiano*

---

## The problem: software is mentioned, rarely cited

> "Statistical analyses were performed with **SPSS** v25 (IBM) and **R** 4.3 (lme4 package)…"

- Most software appears as **informal mentions** in the text, not as references in the bibliography
- So citation does not follow any standard, indexes **miss** most of it
- To measure software's role in research, we have to **read the full text**

➡️ This is a **named entity recognition** problem over full-text PDFs

---

## The Available datasets

**SoftCite**: A **gold-standard** corpus of software mentions (Du et al., JASIST 2021)

- **4,971** open-access full-text articles, half **life sciences**, half **economics**
- **5,134** software mentions in v2.0 (2023), up from 4,093 in v1.0
- Each mention annotated with its attributes: **name**, **version**, **publisher**, **URL**
- v2.0 adds the **type** of software and **relations** between mentions
- TEI/XML, CC-BY — [zenodo.org/records/7995565](https://doi.org/10.5281/zenodo.7995565)

**SoMeSci** — *Software Mentions in Science* (Schindler et al., CIKM 2021)
- ~**3,700** software mentions in **1,367** PubMed Central articles
- Rich annotation: mention type (**usage**, **creation**, deposition, allusion), software type, version, developer, URL, license
- Published as a **knowledge graph** (linked open data)


---

### Other datasets (SoFAIR, SoMeSci)

**SoFAIR** — CHIST-ERA project (2024–2025), led by the Open University (CORE) with HAL and Software Heritage
- New **multidisciplinary** corpus, beyond the biomedical domain
- Attributes: name, version, publisher, URL, programming language
- 🤗 [SoFairOA/sofair_dataset](https://huggingface.co/datasets/SoFairOA/sofair_dataset) (gated) · [github.com/SoFairOA/Dataset](https://github.com/SoFairOA/Dataset)
- Used to benchmark **LLMs vs. classic NER** on SoftCite, SoMeSci & SoFAIR (JCDL 2025)

➡️ Different domains and **different annotation schemes**: comparing them is a challenge in itself!

---

## From dataset to tool: Softcite software-mentions

A [GROBID](https://github.com/kermitt2/grobid) module — [github.com/softcite/software-mentions](https://github.com/softcite/software-mentions)

```
PDF ──► GROBID (structure) ──► NER (name, version, publisher, URL)
                                 ──► entity linking (Wikidata)
                                 ──► context: used / created / shared
                                 ──► JSON with PDF coordinates
```

- Sequence labelling models (CRF, BiLSTM-CRF, SciBERT-based) via DeLFT
- Works on **PDF** or text, at **corpus scale**
- Mentions composed by software names, version, producer, type etc...
- Mentions are **characterised**: is the software *used*, *created* or *shared* by the authors?

---

## Applying it to HAL

**Inria DataLake** — a pipeline on top of the French open archive HAL

```
HAL PDFs ──► GROBID ──► software mentions ──► notifications
                                               (COAR Notify)
                                          ──► Software Heritage
```

- Runs at scale on **Grid'5000**
- Detected software is **notified back** to HAL via COAR Notify, so authors and the archive can link publications ↔ software
- Links to archived source code in **Software Heritage**

*Demo paper at TPDL 2026, September 21-25, Faro*

---

## What this means for the hackathon

- The **PEPR Santé Numérique** collection is a HAL collection → same pipeline, same formats
- We already ran **GROBID** on it → PDF, TXT, JSON, Markdown ready to use
- Softcite was trained on **biomedicine + economics**
  → how well does it transfer to **digital health** (imaging, ML, clinical informatics…)?
- **Open questions** for you:
  - What does Softcite miss? What does it over-detect?
  - Is "used / created / shared" useful for the PEPR's own software output?

---

<!-- _class: lead -->

# Part 2 — BioToFlow & NER methods
*Clémence Sebe*

Paper: [academic.oup.com/bioinformatics/article/42/8/btag565](https://academic.oup.com/bioinformatics/article/42/8/btag565/8747618)

<!-- Insert BioToFlow slides here -->

---

<!-- _class: lead -->

# Part 3 — The hackathon

---

## Why look at software in publications?

- Software is central to research… but rarely **cited** formally
- Finding it lets us:
  - **track research practices** in a community
  - **tell apart** software that is created vs. merely used
  - **discover** new tools and technologies
- Our playground: publications of the **PEPR Santé Numérique**
- … but the methods apply to **any corpus**

---

## The goal

> **Extract and analyse the software names mentioned in PEPR Santé Numérique publications**

Three questions to guide your two days:

1. **What new analyses** can we run on these publications?
2. **Which methods** work (and which fail)?
3. **What other data** could we bring in?

---

## Data available

**HAL publications of the PEPR Santé Numérique**
[univ-perp.hal.science/PEPR_SANTENUM](https://univ-perp.hal.science/PEPR_SANTENUM)

- Unannotated, as **PDF**, **TXT**, **JSON** and **Markdown** (via GROBID)
- 🤗 [huggingface.co/datasets/HackatonSanteNumerique/pepr-hal-data](https://huggingface.co/datasets/HackatonSanteNumerique/pepr-hal-data)

**Annotated corpora**

- **SoftCite** — software mentions
- **CPL-Article**
- **BioToFlow**

**Bonus**: notebooks and code from our own experiments

---

## Models available

| Tool | Type | Access |
|---|---|---|
| **SoftCite** | Software mention extraction | HF Space *(to be confirmed)* |
| **CoPaLink** (NER) + **BioToFlow** | NER trained on BioToFlow | Hugging Face |
| **Baguette** (dataESR) | LLM for software extraction | API via `lm-inference` client |

<div class="small">

- Baguette: [huggingface.co/buckets/dataesr/Baguette-Software-Dataset](https://huggingface.co/buckets/dataesr/Baguette-Software-Dataset)
- Client / server: [github.com/ScienciaLAB/lm-inference](https://github.com/ScienciaLAB/lm-inference)

</div>

---

## And also…

- **Alternative sources**: [OpenAlex](https://openalex.org/) — metadata, citations, authors, institutions
- **Vibe-coding welcome**: [opencode.ai](https://opencode.ai/) or your favourite assistant
- **Environment**: VM with Conda, Docker, Python
- **Code & discussion**: hackathon GitHub organisation → `<link to add>`

---

## Ideas if you don't know where to start

**🔬 Extraction**
- Run our existing approaches on the PEPR data and **compare** results
- Separate software that is **created** from software that is **used**
- Apply a **classification model** to the predictions of the BioToFlow-trained model

**📊 Analysis**
- Which software dominates? By research axis, lab, year?
- Open source vs. proprietary, languages, linked repositories
- Cross with OpenAlex: author ↔ software networks

**🛠️ Tools**
- Visualisation, dashboards, search over mentions…

---

## Evaluation: an open question

- No gold annotations on the PEPR corpus
- How do we judge extraction quality?
  - agreement between models (SoftCite vs. CoPaLink vs. Baguette)
  - manual annotation of a **small sample**
  - transfer from the annotated corpora
- Any proposal is welcome!

---

## Schedule — Tuesday 14 October

| Time | Activity |
|---|---|
| 9:00 – 9:30 | Presentations |
| 9:30 – 9:45 | **Form groups** |
| 9:45 – 11:00 | **Brainstorming**: pick a topic |
| 11:00 – 11:15 | *Break* |
| 11:15 – 12:15 | **Quick share** — 5 min per group |
| 12:15 – 13:45 | *Lunch* |
| 13:45 – 15:45 | Hacking |
| 15:45 – 16:00 | *Break* |
| 16:00 – 18:00 | Hacking |

🎯 **By end of morning**: every group knows what it will test in the afternoon

---

## Schedule — Wednesday 15 October

| Time | Activity |
|---|---|
| 9:00 – 10:30 | Hacking — wrap-up |
| 10:30 – 11:00 | *Break* |
| 11:00 – 12:00 | **Group presentations** & discussion |
| 12:00 – 12:15 | Conclusion / closing |

---

## What we expect from each group

A short presentation, even if "it didn't work":

- **Question** tackled
- **Data & methods** used
- **Results** (numbers, visualisation, demo…)
- **Difficulties** & possible **next steps**

Please share code and notebooks on the hackathon GitHub 🙏

---

## Forming groups

- Groups of **3 to 5 people**
- Mix profiles: NLP, dev, health, data
- One group = **one question** (not necessarily technical)

**Brainstorming (9:45 – 11:00)**
1. What interests you in this data?
2. What can be done in ~6 hours?
3. What do you need? (data, models, compute)

---

<!-- _class: lead -->

# Your turn! 🚀

**Data**: 🤗 HackatonSanteNumerique/pepr-hal-data
**Code**: `<GitHub link>`
**Contacts**: Luca Foppiano · Clémence Sebe

---

<!-- _class: lead -->
<!-- _header: 'Wednesday 15 October — Presentations' -->

# Group presentations

11:00 – 12:00

---

## Conclusion

- What we learned about software in the PEPR Santé Numérique
- What works / what remains hard
- Next steps: annotated corpus? shared tools? publication?

**Thank you all!**
