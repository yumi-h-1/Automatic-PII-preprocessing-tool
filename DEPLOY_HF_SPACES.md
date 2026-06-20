# Deploy the live demo on Hugging Face Spaces

This branch (`feat/hf-spaces-demo`) is the deploy branch. HF's create API only accepts
`gradio | docker | static` as the SDK, so the Streamlit app runs as a **Docker Space**. It adds:

1. **`Dockerfile`** — runs `streamlit run app/streamlit_app.py` on port 8501.
2. **`README.md` front-matter** — `sdk: docker`, `app_port: 8501`.
3. **The spaCy model in `requirements.txt`** — `en_core_web_lg` installs during the image build.

Everything else (the `noteguard/` package, `app/streamlit_app.py`) already works as-is. The Space
downloads the NHS dataset from Hugging Face at first run; if that fails it falls back to paste-only mode.

## One-time deploy

```bash
# 1) Log in (needs a HF token with WRITE scope: https://huggingface.co/settings/tokens)
hf auth login

# 2) Create the Space (Docker SDK, free cpu-basic). Or make it at https://huggingface.co/new-space
hf repos create <HF_USERNAME>/noteguard --repo-type space --space-sdk docker

# 3) Push THIS branch to the Space's main branch
git remote add space https://huggingface.co/spaces/<HF_USERNAME>/noteguard
git push space feat/hf-spaces-demo:main
```

> Uses the `hf` CLI from `huggingface_hub` >= 1.0 (the old `huggingface-cli` still works as a
> deprecated alias). `hf auth login` will prompt for your write token.

The Space builds (installs Presidio + spaCy + `en_core_web_lg`, ~3–5 min the first time), then serves
the app. Your **Live Demo Link** is:

```
https://huggingface.co/spaces/<HF_USERNAME>/noteguard
```

Paste that into the submission form's *Live Demo Link* field.

## Notes
- **Resource-constrained?** If the build is slow or the Space OOMs, swap the model line in
  `requirements.txt` to `en_core_web_sm-3.8.0` (faster, lighter; slightly lower name recall).
- **Updating the demo:** push again with `git push space feat/hf-spaces-demo:main` (the Space rebuilds).
- **Keep this branch deploy-only** — don't merge the README front-matter into `main` (it's only for the
  Space card).
