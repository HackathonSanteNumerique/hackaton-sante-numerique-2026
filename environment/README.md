# Environment

You can work on your own laptop or on a VM on **[Biosphere](https://biosphere.france-bioinformatique.fr/)**, the IFB cloud for life sciences. Biosphere has the advantage that you don't need to install anything locally: a Jupyter VM opens in your browser.

- [Biosphere: get a Jupyter VM](#biosphere-get-a-jupyter-vm)
- [Vibe-coding with opencode + Albert API](#vibe-coding-with-opencode--albert-api)
- [Where to run each model](#where-to-run-each-model)

---

## Biosphere: get a Jupyter VM

Do steps 1–3 **before the hackathon**: account and group requests are approved by hand.

1. **Sign in** at [biosphere.france-bioinformatique.fr](https://biosphere.france-bioinformatique.fr/cloudweb/login/?next=/) with your institution's credentials (RENATER / eduGAIN). If your institution isn't in the federation, create a local Biosphere account instead.
2. **Join the hackathon group:** go to [Groups](https://biosphere.france-bioinformatique.fr/cloudweb_account/groups), open the **Join a group** tab, search for **`SN-training (Ateliers Santé Numérique 2026)`** and apply.
3. **Wait for approval.** The hackathon team accepts your request into the group.
4. **Deploy a VM:** pick the **Jupyter** appliance in the [RAINBio catalogue](https://biosphere.france-bioinformatique.fr/catalogue/) and deploy it in the `SN-training` group.
5. **Open it in the browser:** the VM takes a few minutes to start. Then, in the [**myVM**](https://biosphere.france-bioinformatique.fr/cloud/) tab, click the HTTP/S link in the **Access** column. If Jupyter asks for credentials, they're in the **Params** field of the same column.

That's all you need: JupyterLab gives you a terminal, so you can clone this repo and run `uv sync` from there.

### Optional: SSH access

You only need this if you want to SSH into the VM instead of using the browser.

- Biosphere expects an **RSA** key: `ssh-keygen -t rsa`.
- Paste the public key in your profile (user menu, top right → account parameters → **Edit** → `Pubkey`). It must be on **one line**; the form handles line breaks badly, so copy the file straight to the clipboard rather than from the terminal:
  ```bash
  xclip -sel clip < ~/.ssh/id_rsa.pub   # Linux
  pbcopy < ~/.ssh/id_rsa.pub            # macOS
  ```
- Register the key **before** creating the VM: it's copied in at creation and can't be changed afterwards.
- To connect, open the VM's page (click its `ID` in myVM) and copy the `ssh` command from the **Access** table.

Full documentation: [ifb-elixirfr.github.io/biosphere](https://ifb-elixirfr.github.io/biosphere/).

---

## Vibe-coding with opencode + Albert API

[opencode](https://opencode.ai/) is an open-source coding assistant for the terminal. It runs in the JupyterLab terminal of a Biosphere VM. As its model it can use **[Albert API](https://ia.numerique.gouv.fr/outils-ia/albert-api)**, the French State's sovereign, OpenAI-compatible LLM API. Any other assistant you already use is fine too.

**1. Install opencode** (in the VM terminal or on your laptop):

```bash
curl -fsSL https://opencode.ai/install | bash
# or: npm install -g opencode-ai
```

**2. Get an Albert API key.** State agents get access automatically through ProConnect; see the [Albert API guide](https://guides.ia.numerique.gouv.fr/albert-api). Then list the models your key can use:

```bash
export ALBERT_API_KEY=<your key>
curl -s https://albert.api.etalab.gouv.fr/v1/models -H "Authorization: Bearer $ALBERT_API_KEY"
```

**3. Declare Albert as a provider** in `~/.config/opencode/opencode.json` (or `opencode.json` at the root of your project). Replace `<model-id>` with an `id` from the list above:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "albert": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Albert API",
      "options": {
        "baseURL": "https://albert.api.etalab.gouv.fr/v1",
        "apiKey": "{env:ALBERT_API_KEY}"
      },
      "models": {
        "<model-id>": { "name": "<model-id>" }
      }
    }
  }
}
```

**4. Start it** in your project folder with `opencode`, then choose the Albert model with `/models`.

Don't commit your API key: keep it in an environment variable, as above.

---

## Where to run each model

| Model | Where | Notes |
|---|---|---|
| **Softcite** | Hosted [🤗 Space](https://lfoppiano-softcite-software-mentions.hf.space/) | Nothing to install; see [`models/`](../models/README.md#softcite-software-mentions) |
| **Baguette** | Hosted Modal endpoint | See [`models/`](../models/README.md#lm-inference) |
| **CoPaLink** (paper-text NER) | Your laptop or a Biosphere VM | Uses the GPU if there is one (CUDA or Mac MPS), else CPU at 15–30 s per paper; see [`models/`](../models/README.md#run-the-paper-text-ner-on-the-pepr-corpus) |

Biosphere also has a few **GPU** VMs. Deploying a model on one (for example Softcite, which is a Docker image) is a hackathon topic in itself: see the ideas in the [main README](../README.md#ideas-if-you-dont-know-where-to-start).
