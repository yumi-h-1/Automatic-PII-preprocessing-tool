# Deploy the live demo on Hugging Face Spaces

The repo ships everything an HF **Docker Space** needs (HF's create API only accepts
`gradio | docker | static`, so the Streamlit app runs via Docker):

1. **`Dockerfile`** — installs the package (`pip install ".[app]"`) + `en_core_web_lg`, then runs
   `streamlit run streamlit_app.py` on port 8501.
2. **`README.md` front-matter** — `sdk: docker`, `app_port: 8501` (the Space card config).

The Space downloads the NHS dataset from Hugging Face at first run; if that fails it falls back to
paste-only mode.

## One-time deploy

```bash
# 1) log in (HF token with WRITE scope: https://huggingface.co/settings/tokens)
hf auth login

# 2) create the Space (Docker SDK, free cpu-basic) — or use https://huggingface.co/new-space
hf repos create <HF_USERNAME>/noteguard --repo-type space --space-sdk docker

# 3) push main to the Space's main branch
git remote add space https://huggingface.co/spaces/<HF_USERNAME>/noteguard
git push space main
```

> Uses the `hf` CLI from `huggingface_hub` >= 1.0 (`huggingface-cli` still works as a deprecated alias).

The Space builds the image (Presidio + spaCy + `en_core_web_lg`, ~3–5 min the first time), then serves
the app at `https://huggingface.co/spaces/<HF_USERNAME>/noteguard`.

## Updating an existing Space

After any change on `main`:

```bash
git push space main      # the Space rebuilds automatically
```

The `Dockerfile` is the single source of truth for the entry point (`streamlit_app.py`) and the model,
so renames in the repo never require changing Space settings — just push.

## Notes
- **Resource-constrained?** If the build is slow or the Space OOMs, change `en_core_web_lg` to
  `en_core_web_sm` in the `Dockerfile`.
- Front-matter lives at the top of `README.md`; GitHub renders it as a small table — harmless.
