# Sherlock Backend (FastAPI)

Runs the Sherlock OSINT tool and exposes a simple API for a Next.js frontend.

## Endpoints
- `GET /healthz` → `{ status: "ok" }`
- `GET /search?username=<name>` → `{ results: [ { site, url, username, icon, profilePic } ] }`

## Local Run (Codespaces or local)
```bash
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
