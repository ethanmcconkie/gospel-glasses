# Glasses TV Remote

Pick a TV, then a real button grid: power, volume, mute. No gestures, no
tricks — the thing we actually confirmed works.

## Setup

```bash
pip install fastapi uvicorn httpx

# Get a token at https://account.smartthings.com/tokens
export SMARTTHINGS_TOKEN=...
export GLASS_KEY=$(python -c "import secrets;print(secrets.token_urlsafe(32))")

uvicorn tv_remote_proxy:app --host 0.0.0.0 --port 8788
```

Must be reachable over HTTPS for the glasses to load it — same as the Slack
build (Caddy, cloudflared, Tailscale Funnel).

Set `API` in `index.html` to your proxy's HTTPS origin, host it, then open
once at `https://your-host/#k=YOUR_GLASS_KEY` to pair.

## Controls

**TV picker:** ↑↓ move, ⏎ select.
**Remote:** ↑↓←→ move around the 2×2 button grid, ⏎ press. Up from the top
row backs out to the TV list — no separate back button needed.

## Why a proxy at all

Same reason as Slack: SmartThings needs a bearer token, which can't live in
a static page, and its API won't accept direct browser calls with one
anyway. The proxy holds the token and exposes three tiny routes — list TVs,
get status, run an action — and the glasses app never sees SmartThings'
actual device IDs or capability names, just plain actions like `volume_up`.

## Only TVs show up

The device list filters to anything with both `switch` and `audioVolume` (or
`tvChannel`) capabilities, so your lightbulbs and sensors don't clutter the
picker.

## What this deliberately doesn't do

No gesture-driven volume — tested directly on the glasses via two diagnostic
pages (checked the audio element's `volumechange` event, raw `keydown` for
the standard `AudioVolumeUp/Down/Mute` key values, MediaSession handlers,
and the Gamepad API). Nothing fired. The web app has no visibility into
whatever pinch-and-turn is actually doing, so it isn't a browser-reachable
feature — confirmed by testing, not assumed.

No channel or input switching yet — SmartThings exposes `tvChannel` and
`mediaInputSource` capabilities for this if you want to add them later; same
pattern, just two more entries in `ACTIONS` on the proxy side and two more
buttons on the glasses side.
