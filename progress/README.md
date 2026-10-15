# Hackathon Progress: Completed Work and Next Steps

**Dates:** October 14–15

## Overview

We worked with three models (SoftCite, BioToFlow, and Baguette) and ran predictions on the files provided by the [PEPR Santé Numérique](https://hal.science/PEPR_SANTENUM/).

We harmonized the models' outputs, analyze the extracted information and perform an initial evaluation of the models.

## Completed Work

### 1. Output Harmonization

We converted the outputs of SoftCite, BioToFlow, and Baguette into a common format based on the SoftCite output structure.

This harmonization facilitates the comparison and analysis of the information extracted by the different models.

### 2. Data Integration and Preliminary Analysis

We merged the outputs from the three models and conducted an initial analysis, including statistics on the information extracted by each model.

This first analysis provides an overview of the models' outputs and helps identify potential differences between them.

### 3. Initial Model Evaluation

In the absence of a manually annotated corpus specifically designed for the PEPR Santé Numérique, we performed an initial evaluation using [SoMeSCi](https://data.gesis.org/somesci/), an existing corpus that differs from the PEPR corpora.

This preliminary evaluation provides a first assessment of the models' performance.

## Upcoming Work

### 1. Create a PEPR Santé Numérique Gold-Standard Corpus

We plan to launch an annotation campaign to create a gold-standard corpus for the PEPR.

The main steps are:
- Select a representative subset of the PEPR files.
- Manually annotate the selected files.
- Establish a reference dataset for evaluating the models.

### 2. Annotate Tools with Fine-Grained Attributes

The annotation schema will include the following attributes:

- **Created:** Tools created or developed as part of the work.
- **Used:** Tools explicitly used in the described work.
- **Shared:** Tools mentioned in the article but not used or created by the authors.

### 3. Evaluate and Compare the Models

Once the gold-standard corpus is available, we will use it to conduct a more detailed evaluation of SoftCite, BioToFlow, and Baguette.

The objective is to compare their performance and better understand their strengths and limitations.

### 4. Share the Results with the Community

We plan to present the results of this work to the community.

## Summary

The hackathon established a common output format for SoftCite, BioToFlow and Baguette, enabled an initial analysis of their predictions, and provided a preliminary evaluation using SoMeSCi.

The next steps focus on creating a manually annotated PEPR Santé Numérique corpus, introducing fine-grained tool annotations, conducting a more detailed comparative evaluation, and sharing the findings with the community.s