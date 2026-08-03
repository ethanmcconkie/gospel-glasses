"""
TV Remote proxy — SmartThings backend for the glasses TV remote web app.

Same reasoning as the Slack proxy: SmartThings requires a bearer token,
so a static web page can't hold it safely and can't call the API directly
from the browser anyway (CORS). This sits in between.

Run:
    pip install fastapi uvicorn httpx
    export SMARTTHINGS_TOKEN=<personal access token from account.smartthings.com/tokens>
    export GLASS_KEY=$(python -c "import secrets;print(secrets.token_urlsafe(32))")
    uvicorn tv_remote_proxy:app --host 0.0.0.0 --port 8788

Needs to be reachable over HTTPS for the glasses to load it, same as before
(Caddy/nginx with a cert, or a tunnel).

The client never sees SmartThings device IDs or capability names — it just
says "power_on" or "volume_up" for a given TV, and this translates that into
the actual SmartThings command shape.
"""

import os
import time
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

ST_TOKEN = os.environ["SMARTTHINGS_TOKEN"]
GLASS_KEY = os.environ["GLASS_KEY"]
ST_BASE = "https://api.smartthings.com/v1"

CACHE_TTL = 30

app = FastAPI(title="TV Remote Glass")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization"],
)

_cache: dict[str, tuple[float, Any]] = {}

# Simple action -> SmartThings (capability, command, args) mapping.
# Keeping this on the server means the glasses app never has to know
# SmartThings' vocabulary, and it's the one place to fix things if
# a particular TV model names capabilities slightly differently.
ACTIONS = {
    "power_on": ("switch", "on", []),
    "power_off": ("switch", "off", []),
    "volume_up": ("audioVolume", "volumeUp", []),
    "volume_down": ("audioVolume", "volumeDown", []),
    "mute": ("audioMute", "mute", []),
    "unmute": ("audioMute", "unmute", []),
}


def auth(header: str | None):
    if header != f"Bearer {GLASS_KEY}":
        raise HTTPException(401, "bad key")


def cached(key: str, ttl: int, producer):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    val = producer()
    _cache[key] = (time.time(), val)
    return val


async def st_request(method: str, path: str, json: dict | None = None) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.request(
            method,
            f"{ST_BASE}{path}",
            headers={"Authorization": f"Bearer {ST_TOKEN}"},
            json=json,
            timeout=10,
        )
    if r.status_code >= 400:
        raise HTTPException(502, f"SmartThings {r.status_code}: {r.text[:200]}")
    return r.json() if r.content else {}


@app.get("/tv/devices")
async def list_devices(authorization: str | None = Header(None)):
    """TVs only, so the picker isn't cluttered with lightbulbs and sensors."""
    auth(authorization)

    async def build():
        data = await st_request("GET", "/devices")
        tvs = []
        for d in data.get("items", []):
            caps = {
                c["id"]
                for comp in d.get("components", [])
                for c in comp.get("capabilities", [])
            }
            if "switch" in caps and ("audioVolume" in caps or "tvChannel" in caps):
                tvs.append({"id": d["deviceId"], "name": d.get("label") or d["name"]})
        return {"devices": tvs}

    return await cached("devices", CACHE_TTL, lambda: build())


@app.get("/tv/status/{device_id}")
async def status(device_id: str, authorization: str | None = Header(None)):
    """Power + volume + mute, enough for the remote screen to show real state."""
    auth(authorization)
    data = await st_request("GET", f"/devices/{device_id}/status")
    main = data.get("components", {}).get("main", {})
    return {
        "power": main.get("switch", {}).get("switch", {}).get("value"),
        "volume": main.get("audioVolume", {}).get("volume", {}).get("value"),
        "muted": main.get("audioMute", {}).get("mute", {}).get("value") == "muted",
    }


@app.post("/tv/command/{device_id}/{action}")
async def command(
    device_id: str, action: str, authorization: str | None = Header(None)
):
    auth(authorization)
    if action not in ACTIONS:
        raise HTTPException(400, f"unknown action: {action}")
    capability, cmd, args = ACTIONS[action]
    await st_request(
        "POST",
        f"/devices/{device_id}/commands",
        json={
            "commands": [
                {
                    "component": "main",
                    "capability": capability,
                    "command": cmd,
                    "arguments": args,
                }
            ]
        },
    )
    return {"ok": True}
