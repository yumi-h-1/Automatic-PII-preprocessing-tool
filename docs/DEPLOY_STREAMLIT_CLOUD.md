# Deploy the live demo on Streamlit Community Cloud

Streamlit Community Cloud is **fully free with no payment method** — so there is zero risk of a
surprise bill. It gives a clean `https://<app>.streamlit.app` URL straight from this GitHub repo.

## Why this setup
The free tier has ~1 GB RAM, so we ship the **small** spaCy model (`en_core_web_sm`, 91% name recall)
instead of `lg` (100%). This only affects the *live* instance — local runs still use `lg`, and the
numbers quoted in the README were measured with `lg`. `requirements.txt` pins the `sm` model wheel
(Streamlit Cloud can't run `python -m spacy download`), and `build_detector` automatically uses
whichever model is actually installed (see `src/detect.py`), so no config is needed.

## One-time deploy
1. Push this repo to GitHub (already done if you're reading this).
2. Go to <https://share.streamlit.io> → **Create app** → pick this repo/branch.
3. **Main file path:** `streamlit_app.py`  ·  Python 3.10–3.12.
4. Click **Deploy**. First build installs Presidio + spaCy + `sm` (~2–4 min), then serves the app.

