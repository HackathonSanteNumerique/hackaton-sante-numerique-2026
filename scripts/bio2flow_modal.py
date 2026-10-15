"""
bio2flow (the CoPaLink paper-text NER) served on Modal.

The model is csebe_scibert_bioinfo_voc_iteration4_seed100.pt of sharefair/nlp_models
(https://gitlab.liris.cnrs.fr/sharefair/nlp_models), run with nlstruct by the code of
copalink_client.py: the paragraphs of a paper are joined with blank lines, predicted as
one document, and each Tool entity is given back to its paragraph. The response is the
JSON that copalink_client.py writes for a paper.

The model (474 MB) is downloaded once from the public GitLab repo into a Modal volume;
SciBERT, which nlstruct loads from Hugging Face, is cached in the same volume.

Deploy (from this repo; modal and a Modal token are needed, `modal token new`):
    uvx modal deploy scripts/bio2flow_modal.py
Deploy parameters, as environment variables of the deploy command:
    BIO2FLOW_GPU             GPU type, a key of GPU_COST_PER_SECOND (default L4)
    BIO2FLOW_MAX_CONTAINERS  GPU containers at most (default 4)
    BIO2FLOW_BATCH_SIZE      sequences per SciBERT batch (default 32)
    BIO2FLOW_GPU=T4 uvx modal deploy scripts/bio2flow_modal.py
Smoke test:
    uvx modal run scripts/bio2flow_modal.py
Request, one paper:
    curl -X POST https://<workspace>--bio2flow-app-extract-endpoint.modal.run \\
      -H 'Content-Type: application/json' \\
      -d '{"paragraphs": ["Reads were aligned with BWA and sorted with samtools."], "name": "test"}'
Client, with the inputs, outputs and resume of a local run:
    uv run python scripts/copalink_client.py --endpoint https://<workspace>--bio2flow-app-extract-endpoint.modal.run \\
      --input-folder data/pepr-hal-data/grobid/xml --output-dir data/bio2flow --csv-output data/bio2flow.csv
"""

import os
import time
from pathlib import Path
from types import SimpleNamespace

import modal

APP_NAME = "bio2flow-app"
MODEL_NAME = "csebe_scibert_bioinfo_voc_iteration4_seed100.pt"
MODEL_URL = f"https://gitlab.liris.cnrs.fr/sharefair/nlp_models/-/raw/main/{MODEL_NAME}"
MODEL_SIZE = 474065197
# The same versions as the copalink extra of pyproject.toml (uv.lock).
NLSTRUCT = "nlstruct @ git+https://github.com/ClemenceS/nlstruct.git@f7fc39ebaf6bbb8255c692dca6d01ee9e727c898"
# Modal GPU prices per second, as in lm-inference (lm_inference_utils.py).
GPU_COST_PER_SECOND = {
    "T4": 0.000164,
    "L4": 0.000222,
    "A10G": 0.000264,
    "L40S": 0.000542,
    "A100_40GB": 0.000583,
    "A100_80GB": 0.000694,
    "H100": 0.001097,
}
# Deploy parameters. They are read when the app is deployed and copied into the
# image, so that the containers see the same values.
GPU_TYPE = os.environ.get("BIO2FLOW_GPU", "L4")
MAX_CONTAINERS = int(os.environ.get("BIO2FLOW_MAX_CONTAINERS", "4"))
BATCH_SIZE = int(os.environ.get("BIO2FLOW_BATCH_SIZE", "32"))
if GPU_TYPE.replace("-", "_") not in GPU_COST_PER_SECOND:
    raise ValueError(f"Unknown GPU type {GPU_TYPE!r}; one of {', '.join(GPU_COST_PER_SECOND)}")
COST_PER_SECOND = GPU_COST_PER_SECOND[GPU_TYPE.replace("-", "_")]

VOLUME = modal.Volume.from_name("bio2flow-model", create_if_missing=True)
VOLUME_PATH = "/models"
MODEL_PATH = f"{VOLUME_PATH}/{MODEL_NAME}"
CLIENT = Path(__file__).resolve().parent / "copalink_client.py"

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git")
    .pip_install("torch==2.14.1", "transformers==4.56.1", "huggingface_hub==0.36.2", NLSTRUCT, "fastapi[standard]")
    .env({
        "HF_HOME": f"{VOLUME_PATH}/huggingface",
        "BIO2FLOW_GPU": GPU_TYPE,
        "BIO2FLOW_MAX_CONTAINERS": str(MAX_CONTAINERS),
        "BIO2FLOW_BATCH_SIZE": str(BATCH_SIZE),
    })  # fmt: skip
    .add_local_file(CLIENT, "/root/copalink_client.py")
)
# The endpoint only reads the request and calls the GPU class: no torch.
endpoint_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("fastapi[standard]")
    .env({"BIO2FLOW_GPU": GPU_TYPE})
    .add_local_file(CLIENT, "/root/copalink_client.py")
)

app = modal.App(APP_NAME, image=image)


def download_model():
    """The model into the volume, once; written under another name first, so that an
    interrupted download is never taken for the model."""
    import urllib.request

    if os.path.exists(MODEL_PATH) and os.path.getsize(MODEL_PATH) == MODEL_SIZE:
        return False
    print(f"Downloading {MODEL_URL} ...")
    partial = f"{MODEL_PATH}.part"
    with urllib.request.urlopen(MODEL_URL, timeout=600) as response, open(partial, "wb") as f:
        while chunk := response.read(1 << 20):
            f.write(chunk)
    if os.path.getsize(partial) != MODEL_SIZE:
        raise RuntimeError(f"incomplete download: {os.path.getsize(partial)} of {MODEL_SIZE} bytes")
    os.replace(partial, MODEL_PATH)
    return True


@app.cls(
    gpu=GPU_TYPE.replace("_", "-"),
    scaledown_window=300,
    max_containers=MAX_CONTAINERS,
    timeout=1800,
    volumes={VOLUME_PATH: VOLUME},
)
class Bio2flowService:
    """One paper at a time per container: nlstruct is not made for concurrent calls."""

    @modal.enter()
    def load(self):
        import copalink_client

        downloaded = download_model()
        cached = os.path.isdir(f"{VOLUME_PATH}/huggingface")
        # The client's loader: the installed nlstruct (no clone), the GPU, SciBERT by batches.
        args = SimpleNamespace(model=MODEL_PATH, nlstruct="/nonexistent", device="auto", batch_size=BATCH_SIZE)
        self.model = copalink_client.load_model(args)
        if downloaded or not cached:
            VOLUME.commit()

    @modal.method()
    def predict(self, name: str, paragraphs: list[str]) -> dict:
        import copalink_client

        data, _ = copalink_client.predict(self.model, MODEL_NAME, name, paragraphs)
        return data


@app.function(image=endpoint_image, cpu=1, memory=1024, timeout=1800)
@modal.concurrent(max_inputs=20)
@modal.fastapi_endpoint(method="POST")
async def extract_endpoint(body: dict):
    """One paper per request, as JSON:
    {"paragraphs": ["...", "..."], "name": "paper"}   the paragraphs of the paper
    {"text": "...", "name": "paper"}                  a text, split at blank lines
    The paragraphs are read as copalink_client.py reads a JSON file."""
    import copalink_client
    from fastapi import HTTPException

    try:
        paragraphs = copalink_client.read_json(body)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid input: {e}") from e
    if not paragraphs:
        raise HTTPException(status_code=400, detail="no paragraph found in the input")
    name = str(body.get("name") or "document")

    start = time.time()
    try:
        result = await Bio2flowService().predict.remote.aio(name, paragraphs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    request_seconds = time.time() - start
    # duration_seconds is the time of the model; request_seconds adds the wait for a
    # container (the first request after an idle period loads the model).
    result["request_seconds"] = round(request_seconds, 2)
    result["cost_usd"] = round(request_seconds * COST_PER_SECOND, 6)
    result["gpu"] = GPU_TYPE
    return result


@app.local_entrypoint()
def main():
    """Smoke test on two paragraphs."""
    import json

    paragraphs = [
        "Reads were aligned to the reference genome with BWA-MEM and sorted with samtools.",
        "Variants were called with GATK HaplotypeCaller and annotated with VEP.",
    ]
    result = Bio2flowService().predict.remote("smoke-test", paragraphs)
    print(json.dumps(result, ensure_ascii=False, indent=1))
