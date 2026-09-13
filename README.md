# CipherNet — Python migration

CipherNet is now a Python-first encrypted chat application: FastAPI serves the API and WebSocket relay, SQLite persists public identities and encrypted envelopes, and Streamlit supplies the UI. No JavaScript, Node.js, npm, React, Vite, or Tailwind runtime is required.

By default, the SQLite database is created at `~/Library/Application Support/CipherNet/ciphernet.db`, avoiding macOS-protected project folders. Override `DATABASE_URL` in `.env` when needed.

## Security model

Each message is encrypted in the Streamlit client using a one-time AES-256-GCM key. The key is encrypted with the recipient's RSA-2048 public key using OAEP/SHA-256. The API cannot decrypt messages or recover private keys.

Private keys live only in the current Streamlit session. In a production deployment, add a client-side encrypted key vault or a deliberate export/import recovery flow; do not upload private keys to the API.

CipherNet stores a password-encrypted private-key recovery envelope alongside the public identity. The API stores no raw private keys; the Streamlit client decrypts the envelope after successful login, allowing new identities to read their message history across restarts.

## Run

```bash
cd /Users/karan/Documents/PROJECTS/ciphernet-python
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
# Set a strong JWT_SECRET in .env
uvicorn app.main:app --reload
```

In another terminal, using the same virtual environment:

```bash
streamlit run app/ui/streamlit_app.py
```

Open `http://localhost:8501`. The API documentation is at `http://localhost:8000/docs`.

## Test

```bash
pytest
```

See [MIGRATION_PLAN.md](MIGRATION_PLAN.md) for the source inventory, feature mapping, and migration decisions.
