"""
glasses_client.py — Runs ON the Raspberry Pi Zero W.

Loop: camera captures frames -> detect/decode a QR code -> dispatch to the
backend API (/ask or /check-compliance depending on QR content) -> render
the response on the transparent OLED.

QR CODE FORMAT (see generate_demo_qrcodes.py to create physical demo markers):
  "ASK::<question text>"
  "CHECK::<equipment_id>::<observed state text>"

WHY QR-ENCODED SCENARIOS, NOT LIVE CV STATE DETECTION:
A real production system would use computer vision to determine the
"observed state" (e.g. detect PPE presence) automatically from the camera
feed. Building and training that CV model was out of scope for this
timeline. For the demo, the QR marker itself encodes the scenario the camera
is "seeing" — this is an honest, clearly-labeled MVP shortcut: the backend
reasoning (RAG, graph traversal, Ollama compliance check) is 100% real, only
the perception step is simulated via QR content instead of live CV.

HARDWARE ASSUMED (adjust if yours differs):
  - Camera: Pi Camera Module (CSI), via picamera2
  - Display: SSD1309-driver transparent OLED, 128x64, I2C
  If your OLED uses SPI instead of I2C, or a different driver chip
  (SSD1306/SH1106/etc.), see the DISPLAY SETUP section below — luma.oled
  supports all of these, just swap the import and serial() call.

GRACEFUL DEGRADATION: if OLED init fails (not wired yet, wrong pins, etc.),
this falls back to printing to the console instead of crashing — lets you
develop/debug the camera+API logic before the display hardware is working.
"""

import time
import requests
from picamera2 import Picamera2
import cv2

# ── CONFIG ───────────────────────────────────────────────────────────────
# Point this at your backend laptop's IP address on the plant Wi-Fi network.
# Find it with `ipconfig` on Windows (look for IPv4 Address) — must match
# the same value used in mobile_ui.html.
BACKEND_URL = "http://192.168.1.100:8000"

SCAN_INTERVAL_SECONDS = 1.0    # how often to check for a QR code
COOLDOWN_AFTER_SCAN_SECONDS = 5.0  # avoid re-triggering on the same marker repeatedly
REQUEST_TIMEOUT_SECONDS = 15   # backend + local Ollama can take a few seconds

# ── DISPLAY SETUP ───────────────────────────────────────────────────────
try:
    from luma.core.interface.serial import i2c
    from luma.core.render import canvas
    from luma.oled.device import ssd1309

    serial = i2c(port=1, address=0x3C)
    oled = ssd1309(serial, width=128, height=64)
    OLED_AVAILABLE = True
except Exception as e:
    print(f"[WARN] OLED not available ({e}) — falling back to console output.")
    OLED_AVAILABLE = False


def display_text(lines: list[str]):
    """Renders a list of short text lines to the OLED (or console if OLED
    isn't wired up yet)."""
    if not OLED_AVAILABLE:
        print("\n--- OLED (simulated) ---")
        for line in lines:
            print(f"  {line}")
        print("------------------------\n")
        return

    with canvas(oled) as draw:
        y = 0
        for line in lines:
            draw.text((0, y), line, fill="white")
            y += 11  # line height for default small font at 128x64


def wrap_text(text: str, max_chars: int = 21) -> list[str]:
    """Simple word-wrap for the OLED's small character width. 128px wide at
    the default luma.oled font fits roughly 21 characters per line."""
    words = text.split()
    lines, current = [], ""
    for word in words:
        if len(current) + len(word) + 1 <= max_chars:
            current = f"{current} {word}".strip()
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:5]  # cap at 5 lines — roughly what fits on a 64px-tall display


# ── BACKEND CALLS ────────────────────────────────────────────────────────
def call_ask(question: str) -> list[str]:
    try:
        resp = requests.post(
            f"{BACKEND_URL}/ask",
            json={"question": question},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()
        answer = data.get("answer", "(no answer)")
        return wrap_text(answer)
    except requests.exceptions.RequestException as e:
        return wrap_text(f"Connection error: {e}")


def call_check_compliance(equipment_id: str, observed_state: str) -> list[str]:
    try:
        resp = requests.post(
            f"{BACKEND_URL}/check-compliance",
            json={"equipment_id": equipment_id, "observed_state": observed_state},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()
        verdict = data.get("verdict", "UNKNOWN")
        explanation = data.get("explanation", "")
        citation = data.get("citation")
        header = f"[{verdict}]"
        if citation:
            header += f" {citation}"
        return [header] + wrap_text(explanation)
    except requests.exceptions.RequestException as e:
        return wrap_text(f"Connection error: {e}")


# ── QR PARSING ───────────────────────────────────────────────────────────
def parse_and_dispatch(qr_content: str) -> list[str]:
    if qr_content.startswith("ASK::"):
        question = qr_content[len("ASK::"):]
        display_text(["Thinking..."])
        return call_ask(question)

    elif qr_content.startswith("CHECK::"):
        rest = qr_content[len("CHECK::"):]
        parts = rest.split("::", 1)
        if len(parts) != 2:
            return ["Malformed QR", "(expected CHECK::eq::state)"]
        equipment_id, observed_state = parts
        display_text(["Checking..."])
        return call_check_compliance(equipment_id, observed_state)

    else:
        return ["Unrecognized QR", "code format"]


# ── MAIN LOOP ────────────────────────────────────────────────────────────
def main():
    print(f"Lumos AI Glasses client starting. Backend: {BACKEND_URL}")
    print(f"OLED available: {OLED_AVAILABLE}")

    picam2 = Picamera2()
    picam2.configure(picam2.create_video_configuration(main={"format": "XRGB8888", "size": (640, 480)}))
    picam2.start()

    qr_detector = cv2.QRCodeDetector()
    last_scanned = None
    last_scan_time = 0

    display_text(["Lumos AI ready.", "Point at a marker."])

    try:
        while True:
            frame = picam2.capture_array()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)

            data, points, _ = qr_detector.detectAndDecode(gray)

            if data:
                now = time.time()
                if data == last_scanned and (now - last_scan_time) < COOLDOWN_AFTER_SCAN_SECONDS:
                    pass  # ignore repeat scans of the same marker within cooldown
                else:
                    print(f"[QR] Detected: {data}")
                    last_scanned = data
                    last_scan_time = now
                    result_lines = parse_and_dispatch(data)
                    display_text(result_lines)

            time.sleep(SCAN_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        picam2.stop()


if __name__ == "__main__":
    main()
