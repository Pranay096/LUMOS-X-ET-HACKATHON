"""
check_models.py — Tests a list of candidate Gemini models against your actual
API key and reports which ones currently have real (non-zero) free-tier quota.

Run this BEFORE extract.py if you've hit a "limit: 0" 429 error — it tells you
in ~30 seconds which model name to actually use, instead of guessing.

Usage:
    python check_models.py
"""

import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import errors

load_dotenv()

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

# Candidate models, roughly newest/most-likely-free first. Edit this list if
# Google renames or retires models again — check https://aistudio.google.com/rate-limit
# for the authoritative list of what your project currently has access to.
CANDIDATE_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-flash-latest",
]

TEST_PROMPT = "Reply with exactly one word: OK"


def test_model(model_name: str) -> str:
    """Returns 'WORKS', 'QUOTA_ZERO', 'RATE_LIMITED', or 'OTHER_ERROR: <detail>'"""
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=TEST_PROMPT,
        )
        if response.text:
            return "WORKS"
        return "OTHER_ERROR: empty response"
    except errors.ClientError as e:
        msg = str(e)
        if "limit: 0" in msg:
            return "QUOTA_ZERO (no free-tier access to this model on your project)"
        if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
            return "RATE_LIMITED (has quota, but you're temporarily throttled — try again shortly)"
        return f"OTHER_ERROR: {msg[:200]}"
    except Exception as e:
        return f"OTHER_ERROR: {str(e)[:200]}"


def main():
    print(f"Testing {len(CANDIDATE_MODELS)} models against your API key...\n")
    results = {}

    for model_name in CANDIDATE_MODELS:
        print(f"Testing {model_name}...", end=" ", flush=True)
        result = test_model(model_name)
        results[model_name] = result
        print(result)
        time.sleep(3)  # small gap so we don't trip rate limits while just checking

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    working = [m for m, r in results.items() if r == "WORKS"]
    if working:
        print(f"\n✅ Use one of these in extract.py / load_vectors.py:")
        for m in working:
            print(f"   MODEL_NAME = \"{m}\"")
    else:
        print("\n❌ None of the candidate models worked. This likely means your")
        print("   API key's project has zero free-tier quota across the board.")
        print("   Next steps:")
        print("   1. Check https://aistudio.google.com/rate-limit while logged into")
        print("      the same Google account that generated this API key.")
        print("   2. Try generating a brand new key at https://aistudio.google.com/apikey")
        print("      under a fresh/different Google Cloud project.")
        print("   3. As a last resort, linking a billing account (still free to use,")
        print("      just requires a card on file) unlocks the standard free usage")
        print("      allowance — see https://ai.google.dev/gemini-api/docs/billing")

    print("\nFull results:")
    for m, r in results.items():
        print(f"  {m}: {r}")


if __name__ == "__main__":
    main()
