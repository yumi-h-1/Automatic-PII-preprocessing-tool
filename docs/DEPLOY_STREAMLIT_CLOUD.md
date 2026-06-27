# Deploy the live demo on Streamlit Community Cloud (free, no card)

Streamlit Community Cloud is **fully free with no payment method** — so there is zero risk of a
surprise bill. It gives a clean `https://<app>.streamlit.app` URL straight from this GitHub repo.

## Why this setup
The free tier has ~1 GB RAM, so we ship the **small** spaCy model (`en_core_web_sm`, 91% name recall)
instead of `lg` (100%). This only affects the *live* instance — the committed metrics in
`outputs/results.json` and local/HF runs still use `lg`. `requirements.txt` pins the `sm` model wheel
(Streamlit Cloud can't run `python -m spacy download`), and `build_detector` automatically uses
whichever model is actually installed (see `src/detect.py`), so no config is needed.

## One-time deploy
1. Push this repo to GitHub (already done if you're reading this).
2. Go to <https://share.streamlit.io> → **Create app** → pick this repo/branch.
3. **Main file path:** `streamlit_app.py`  ·  Python 3.10–3.12.
4. Click **Deploy**. First build installs Presidio + spaCy + `sm` (~2–4 min), then serves the app.

## Optional: the LLM assurance pass
It's off and inert unless a free key is provided. In the app's **Settings → Secrets**, add:

```toml
LLM_ASSURE_API_KEY = "your-free-groq-or-gemini-key"
# LLM_ASSURE_BASE_URL = "..."   # optional, OpenAI-compatible base (default: Groq)
# LLM_ASSURE_MODEL = "..."      # optional
```

`streamlit_app.py` automatically bridges these secrets into the environment (`_bridge_secrets_to_env`),
so just adding them in the dashboard is enough — no code change needed.

## Notes
- **Want full 100% name recall?** Set `PII_SPACY_MODEL = "en_core_web_lg"` in secrets **and** swap the
  model wheel in `requirements.txt` to the `lg` wheel — but `lg` may exceed the free RAM. The HF Space
  (`docs/DEPLOY_HF_SPACES.md`, 16 GB free) keeps `lg` without this trade-off.
- The dataset (NHSE synthetic notes) is pulled from Hugging Face on first use; if that fails the app
  still runs in paste/upload mode.
