"""
test_compliance.py — Runs sample compliance scenarios through the local
Ollama-based Compliance Agent to verify it correctly distinguishes PASS from
FLAG, cites the right SOP/regulation, and says UNKNOWN rather than guessing
when the input is too vague.
"""

from compliance_agent import check_compliance, close

TEST_SCENARIOS = [
    {
        "label": "Clear PPE violation — should FLAG (APM-SOP-014)",
        "equipment_id": "PMP-204",
        "observed_state": "Technician is working near the pump without a face shield or safety goggles.",
    },
    {
        "label": "Compliant state — should PASS",
        "equipment_id": "PMP-204",
        "observed_state": "Technician is wearing safety helmet, goggles, steel-toe boots, high-visibility vest, and face shield.",
    },
    {
        "label": "LOTO violation — should FLAG (APM-SOP-017)",
        "equipment_id": "PRS-088",
        "observed_state": "Technician is beginning mechanical adjustment work without applying lockout-tagout or verifying zero energy state.",
    },
    {
        "label": "Ambiguous input — should be UNKNOWN, not a guess",
        "equipment_id": "PMP-204",
        "observed_state": "Someone is standing near the equipment.",
    },
]


def run_tests():
    results = []
    for i, scenario in enumerate(TEST_SCENARIOS, 1):
        print(f"\n{'=' * 70}")
        print(f"[{i}/{len(TEST_SCENARIOS)}] {scenario['label']}")
        print(f"Equipment: {scenario['equipment_id']}")
        print(f"Observed: {scenario['observed_state']}")
        print("=" * 70)

        result = check_compliance(scenario["equipment_id"], scenario["observed_state"])

        print(f"\nVerdict: {result.get('verdict')}")
        print(f"Violated requirement: {result.get('violated_requirement')}")
        print(f"Citation: {result.get('citation')}")
        print(f"Explanation: {result.get('explanation')}")
        print(f"Confidence: {result.get('confidence')}")

        results.append({**scenario, "result": result})

    print(f"\n\n{'=' * 70}")
    print("SELF-CHECK")
    print("=" * 70)
    expectations = ["FLAG", "PASS", "FLAG", "UNKNOWN"]
    for i, (scenario, expected) in enumerate(zip(results, expectations), 1):
        actual = scenario["result"].get("verdict")
        status = "✅ PASS" if actual == expected else f"❌ expected {expected}, got {actual}"
        print(f"[{i}] {scenario['label']}: {status}")

    close()


if __name__ == "__main__":
    run_tests()
