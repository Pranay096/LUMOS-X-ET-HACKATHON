"""
generate_demo_qrcodes.py — Generates QR code images for your physical demo
markers, matching the two flagship demo moments from the pitch deck. Print
these and tape them to your demo equipment (or hold them up to the camera).

Run this on your laptop (not the Pi) — just needs `pip install qrcode[pil]`.
"""

import qrcode
import os

OUTPUT_DIR = "demo_qrcodes"

# Each entry: (filename, QR content, human-readable label for your own reference)
DEMO_SCENARIOS = [
    (
        "1_point_and_fix_pmp204.png",
        "ASK::Why does PMP-204 keep failing?",
        "Point-and-fix demo: RCA pattern-match + stale-SOP catch",
    ),
    (
        "2_compliance_flag_no_faceshield.png",
        "CHECK::PMP-204::Technician is working near the pump without a face shield or safety goggles.",
        "Compliance demo: PPE violation, should FLAG citing APM-SOP-014",
    ),
    (
        "3_compliance_pass_full_ppe.png",
        "CHECK::PMP-204::Technician is wearing safety helmet, goggles, steel-toe boots, high-visibility vest, and face shield.",
        "Compliance demo: full PPE, should PASS (good contrast to scenario 2)",
    ),
    (
        "4_loto_violation_prs088.png",
        "CHECK::PRS-088::Technician is beginning mechanical adjustment work without applying lockout-tagout or verifying zero energy state.",
        "Compliance demo: LOTO violation, should FLAG citing APM-SOP-017",
    ),
    (
        "5_maintenance_question_pmp204.png",
        "ASK::How should I maintain the hydraulic coolant pump PMP-204?",
        "Point-and-fix demo: current SOP + supersession explanation",
    ),
]


def generate():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for filename, content, label in DEMO_SCENARIOS:
        img = qrcode.make(content)
        filepath = os.path.join(OUTPUT_DIR, filename)
        img.save(filepath)
        print(f"  {filename}")
        print(f"    -> {label}")
        print(f"    -> encodes: {content[:60]}{'...' if len(content) > 60 else ''}")
        print()

    print(f"Done. {len(DEMO_SCENARIOS)} QR codes saved to {OUTPUT_DIR}/")
    print("Print these (even on plain paper is fine) and either tape them to")
    print("your demo equipment props, or hold them up to the glasses camera")
    print("directly during the live demo.")


if __name__ == "__main__":
    generate()
