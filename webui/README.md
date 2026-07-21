# Mobile Console (`mobile_ui.html`)

Single-file HTML/CSS/vanilla JS — no build step, no dependencies to install.
Three tabs: **Ask** (with live browser speech-to-text), **Compliance Check**,
and **Documentation Gaps** — all calling the same backend the glasses use.

## Quick setup

1. Open `mobile_ui.html` in a text editor.
2. Find `const API_BASE_URL = "http://192.168.1.100:8000";` near the top of
   the `<script>` section and replace the IP with your backend laptop's
   actual IP address (find it with `ipconfig` / `ifconfig`).
3. Open the file directly in a phone or desktop browser. Chrome (Android) and
   Safari (iOS) support the built-in voice input on the Ask tab; other
   browsers fall back to typing only.
4. Your backend (`compliance/api.py`) must be running with
   `--host 0.0.0.0` so it's reachable from another device on the network.

Full setup context — including how this fits with the glasses hardware and
the backend it depends on — is in [`../glasses/README.md`](../glasses/README.md).

This console **is** the manual-input fallback: if the glasses' camera or QR
scan fails, the same equipment ID and observed-state text can be typed here
by hand, reaching the identical backend reasoning.
