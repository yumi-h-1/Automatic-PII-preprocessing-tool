# Hugging Face Spaces (Docker SDK) — serves the NoteGuard Streamlit app.
# HF's create API only accepts gradio|docker|static, so Streamlit runs via Docker.
FROM python:3.11-slim

# Non-root user (HF Spaces convention) -> gives a writable HOME for model/dataset caches.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

WORKDIR $HOME/app

# Install the package (deps come from pyproject.toml) + the spaCy model. Copy only what pip
# needs first, for Docker layer caching.
COPY --chown=user pyproject.toml README.md ./
COPY --chown=user src ./src
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir ".[app]" && \
    python -m spacy download en_core_web_lg

# App code (data/ and .venv are gitignored, so the app downloads the dataset at runtime).
COPY --chown=user . .

EXPOSE 8501
CMD ["streamlit", "run", "streamlit_app.py", \
     "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
