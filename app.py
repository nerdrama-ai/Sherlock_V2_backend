import asyncio
import json
import os
import re
import subprocess
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from utils import fetch_profile_pic_async, safe_json_loads

APP_NAME = "sherlock-backend"

# --- Config via env ---
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*")
INCLUDE_PROFILE_PICS = os.getenv("INCLUDE_PROFILE_PICS", "true").lower() == "true"
PYTHON_BIN = os.getenv("PYTHON_BIN", "python3")
SHERLOCK_PATH = os.getenv("SHERLOCK_PATH", "sherlock/sherlock.py")

app = FastAPI(title=APP_NAME, version="1.0.0")

# CORS
allowed_origins = [o.strip() for o in ALLOWED_ORIGINS.split(",")] if ALLOWED_ORIGINS else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/healthz")
def healthz():
    return {"status": "ok", "app": APP_NAME}

def build_icon_url(site_name: str) -> Optional[str]:
    """
    Try to map a site name to a Simple Icons SVG on jsDelivr.
    Note: Names aren't always 1:1; we send a best-effort guess.
    The frontend can fall back to its own icon if this 404s.
    """
    slug = re.sub(r"[^a-z0-9]+", "", site_name.lower())
    if not slug:
        return None
    return f"https://cdn.jsdelivr.net/gh/simple-icons/simple-icons/icons/{slug}.svg"

async def run_sherlock(username: str) -> str:
    """
    Execute Sherlock and return raw JSON string from stdout.
    """
    cmd = [PYTHON_BIN, SHERLOCK_PATH, username, "--json"]
    # Use asyncio to avoid blocking the event loop
    # (Render/Railway containers handle this fine).
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(stderr.decode("utf-8", errors="ignore") or "Sherlock failed")
    return stdout.decode("utf-8", errors="ignore")

def normalize_results(sherlock_json: Dict[str, Any], username: str) -> List[Dict[str, Any]]:
    """
    Convert Sherlock output to the exact shape your frontend expects.
    """
    out: List[Dict[str, Any]] = []
    for site, data in sherlock_json.items():
        # Sherlock marks found profiles as "Claimed"
        if str(data.get("status", "")).lower() != "claimed":
            continue

        url = data.get("url_user") or data.get("url") or ""
        if not url:
            continue

        out.append({
            "site": site,
            "url": url,
            "username": username,
            "icon": build_icon_url(site),
            "profilePic": None,  # filled later (optional)
        })
    return out

@app.get("/search")
async def search(
    username: str = Query(..., min_length=1, description="Username to search for")
):
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")

    # 1) Run Sherlock
    try:
        raw = await run_sherlock(username)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sherlock error: {e}")

    # 2) Parse JSON
    data = safe_json_loads(raw)
    if data is None:
        raise HTTPException(status_code=500, detail="Failed to parse Sherlock JSON")

    # 3) Normalize
    results = normalize_results(data, username)

    # 4) (Optional) grab profile pictures concurrently
    if INCLUDE_PROFILE_PICS and results:
        # limit concurrency so we don't hammer sites
        sem = asyncio.Semaphore(8)

        async def fill_pic(item: Dict[str, Any]):
            async with sem:
                pic = await fetch_profile_pic_async(item["url"])
                if pic:
                    item["profilePic"] = pic

        await asyncio.gather(*(fill_pic(r) for r in results))

    return {"results": results}
