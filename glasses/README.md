# Day B — Glasses Integration + Mobile UI + Documentation Gap Tracker

## What's in this batch

| File | Runs on | Purpose |
|---|---|---|
| `compliance/gap_tracker.py` | Laptop (backend) | Logs low-confidence `/ask` answers |
| `compliance/api.py` (updated) | Laptop (backend) | Added `/gaps` endpoint + CORS + gap logging |
| `webui/mobile_ui.html` | Any phone/laptop browser | Ask, Compliance Check, and Gaps — the manual fallback UI |
| `glasses/glasses_client.py` | Pi Zero W | Camera → QR → backend → OLED |
| `glasses/generate_demo_qrcodes.py` | Laptop | Generates your physical demo markers |

## Important honest note on scope

The glasses read **QR-encoded demo scenarios**, not live computer-vision
state detection. A QR code on your demo prop encodes the "observed state"
(e.g. "technician without face shield") that a real production system would
eventually detect via CV. **Say this explicitly in your pitch** — it's a
clearly-scoped, honest MVP shortcut. Everything downstream of the QR scan
(the RAG retrieval, the graph traversal, the Ollama compliance reasoning) is
100% real, not mocked.

---

## Setup: Backend (laptop)

1. Copy `gap_tracker.py` into your `compliance/` folder.
2. Replace your existing `compliance/api.py` with the updated version (adds
   CORS + the `/gaps` endpoint + gap logging on every `/ask` call).
3. No new dependencies — `gap_tracker.py` only uses the Python standard
   library.
4. Run the API as before:
   ```
   uvicorn api:app --reload --host 0.0.0.0 --port 8000
   ```
   **`--host 0.0.0.0` matters here** — it makes the server reachable from
   your phone/Pi over Wi-Fi, not just from the laptop itself.
5. **Find your laptop's IP address** (needed for the next two steps):
   ```
   ipconfig
   ```
   Look for "IPv4 Address" under your Wi-Fi adapter, e.g. `192.168.1.100`.

## Setup: Mobile UI

1. Open `webui/mobile_ui.html` in a text editor.
2. Find this line near the top of the `<script>` section:
   ```js
   const API_BASE_URL = "http://192.168.1.100:8000";
   ```
   Replace `192.168.1.100` with your actual laptop IP from above.
3. Open the file directly in a phone browser (AirDrop it, email it to
   yourself, or serve it — simplest is a USB transfer or a quick
   `python -m http.server` in the `webui/` folder and visiting
   `http://<laptop-ip>:8080/mobile_ui.html` from your phone).
4. **Both devices must be on the same Wi-Fi network.**
5. You should see a green "Connected" dot at the top if the backend is
   reachable. If it's red, double-check the IP and that `uvicorn` is running
   with `--host 0.0.0.0`.

This mobile UI **is** your manual-input fallback — if the glasses camera or
QR scan fails live, switch to this and type the equipment ID + observation
by hand. Same backend, same reasoning, just a different input method.

## Setup: Pi Zero W glasses

1. Copy the `glasses/` folder onto the Pi (via `scp`, a USB drive, or `git`).
2. On the Pi:
   ```
   pip install -r requirements.txt
   ```
3. Edit `glasses_client.py` and set the same `BACKEND_URL` you used in the
   mobile UI (same laptop IP).
4. **Check your OLED wiring matches the assumptions in the code** — it
   assumes an I2C-connected SSD1309 at address `0x3C`. If your display uses
   SPI, or a different driver chip (SSD1306, SH1106, etc.), you need to swap:
   ```python
   from luma.core.interface.serial import i2c   # or: spi
   from luma.oled.device import ssd1309          # or: ssd1306, sh1106, etc.
   ```
   in `glasses_client.py`. The rest of the code (canvas, draw.text) is
   identical across all luma.oled-supported displays.
5. Run it:
   ```
   python3 glasses_client.py
   ```
   If the OLED isn't wired up yet or fails to initialize, it automatically
   falls back to printing to the console — you can develop/test the
   camera+QR+API logic before the physical display is working.

## Generate your physical demo QR codes

On your **laptop** (not the Pi):
```
pip install "qrcode[pil]"
cd glasses
python generate_demo_qrcodes.py
```
This creates 5 PNGs in `glasses/demo_qrcodes/` — print them (plain paper is
fine) or display them on a second screen/phone to scan during the live
demo. Each one is labeled with which demo moment it's for.

**Verified**: all 5 were round-trip tested — generated, then decoded with
the exact same `cv2.QRCodeDetector` your Pi will use. They scan correctly.

## Demo run-through checklist

1. Laptop: Neo4j/Qdrant reachable, Ollama running, `uvicorn` running with `--host 0.0.0.0`
2. Phone: mobile UI open, shows green "Connected"
3. Pi: `glasses_client.py` running, console shows "Lumos AI Glasses client starting"
4. Hold QR code `1_point_and_fix_pmp204.png` up to the Pi camera → OLED
   should show "Thinking..." then the answer within a few seconds
5. Hold QR code `2_compliance_flag_no_faceshield.png` → OLED should show
   `[FLAG] APM-SOP-014` plus explanation
6. If anything fails live, switch to the mobile UI and demonstrate the same
   flow manually — this is the fallback working as designed, not a failure.

## If something goes wrong
- **Mobile UI shows red "Cannot reach backend"** → check laptop IP hasn't
  changed (routers sometimes reassign IPs), check `uvicorn` is running with
  `--host 0.0.0.0` not just default.
- **Pi can't reach backend** → same checks, plus confirm the Pi is actually
  on the same Wi-Fi network (not a guest network isolated from your laptop).
- **QR not detected by camera** → check lighting, print size (not too
  small), and that the whole QR code is in frame with good contrast.
- **OLED shows nothing** → check the fallback console output first to
  confirm the logic side is working; then debug wiring/address separately.
