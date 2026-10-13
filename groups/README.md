# Groups

Each group gets its own folder here. Put your code, notebooks and slides in it.

## How to contribute

1. Pick a short, lowercase name for your group, e.g. `software-used-vs-created`.
2. Copy the template: `cp -r groups/_template groups/<your-group>`.
3. Fill in `groups/<your-group>/README.md` as you go: question, people, data, methods.
4. Push to a branch and open a pull request. Small, frequent PRs are fine.

Rules of thumb:

- **No large data in git.** Keep downloads in the top-level [`data/`](../data/) folder, which git ignores. Store small result files (CSV, a few MB at most) in your group folder.
- **No secrets.** API keys go in environment variables or a local `.env`, never in a commit.
- Shared helpers that other groups could reuse can go in [`scripts/`](../scripts/).

## What to present on Wednesday (11:00–12:00)

A short presentation, even if "it didn't work":

- **Question** tackled
- **Data & methods** used
- **Results**: numbers, a visualisation, a demo…
- **Difficulties** and possible **next steps**

The template README follows the same structure, so your write-up doubles as your slide notes.
