"""
extract.py — Reads each document, calls Gemini to extract entities/relationships
matching schema.py, returns structured JSON. This is Step 1 of the Day 2 pipeline.

Uses the current `google-genai` SDK (NOT the deprecated `google-generativeai` package).
"""

import os
import json
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types, errors
from schema import EXTRACTION_SYSTEM_PROMPT

load_dotenv()

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

# gemini-2.5-flash currently has real free-tier quota (gemini-2.0-flash's free
# allowance has been reduced to 0 for many projects as of mid-2026 — check
# https://aistudio.google.com/rate-limit for your project's current per-model limits
# if you hit a 429 with "limit: 0" again).
# gemini-2.5-flash-lite has a meaningfully higher free-tier daily request cap
# than gemini-2.5-flash on most projects (Flash-Lite is built for higher-volume,
# lower-cost usage). If you ever hit "limit: 0" or a tight daily cap again, run
# check_models.py to see your project's current live numbers — they do shift
# over time and vary by project/region, so don't treat any single number as fixed.
MODEL_NAME = "gemini-2.5-flash-lite"
RATE_LIMIT_DELAY_SECONDS = 5  # spacing between documents; per-day is the real constraint, not per-minute
MAX_RETRIES = 2  # with a daily cap in play, don't burn excessive retries on one document
RETRY_BACKOFF_SECONDS = 15  # wait time before retry, doubles each attempt
OUTPUT_PATH = "extracted_graph.json"


def extract_from_document(filepath: str) -> dict:
    """Reads one document and returns {"nodes": [...], "relationships": [...]}.
    Retries automatically on transient server errors (503) and rate limits (429)."""
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    filename = os.path.basename(filepath)
    prompt = f"Document filename: {filename}\n\nDocument text:\n{text}"

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=EXTRACTION_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                ),
            )
            raw = response.text.strip()
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as e:
                print(f"  [WARN] Failed to parse JSON for {filename}: {e}")
                print(f"  Raw response (first 500 chars): {raw[:500]}")
                return {"nodes": [], "relationships": []}

            parsed.setdefault("nodes", [])
            parsed.setdefault("relationships", [])
            return parsed

        except errors.ServerError as e:
            # 503 / model overloaded — transient, just retry with backoff
            last_error = e
            wait = RETRY_BACKOFF_SECONDS * attempt
            print(f"  [RETRY {attempt}/{MAX_RETRIES}] Server unavailable (503). "
                  f"Waiting {wait}s before retry...")
            time.sleep(wait)

        except errors.ClientError as e:
            msg = str(e)
            if "PerDay" in msg or "RequestsPerDay" in msg:
                # Daily quota exhausted — retrying within the same day is pointless,
                # this only resets at midnight Pacific Time. Fail fast instead of
                # burning more attempts (and more of tomorrow's quota patience).
                print(f"  [DAILY QUOTA EXHAUSTED] Your free-tier daily limit for "
                      f"{MODEL_NAME} is used up. This resets at midnight Pacific Time. "
                      f"Stopping — re-run this script after the reset.")
                raise SystemExit(
                    f"\nStopped: daily quota exhausted for {MODEL_NAME}.\n"
                    f"Progress so far is already saved in {OUTPUT_PATH} — "
                    f"just re-run this script after the quota resets (midnight Pacific Time) "
                    f"and it will resume from where it stopped.\n"
                    f"Original error: {msg[:300]}"
                )
            elif "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                # Per-minute rate limit — this one genuinely is worth retrying
                last_error = e
                wait = RETRY_BACKOFF_SECONDS * attempt
                print(f"  [RETRY {attempt}/{MAX_RETRIES}] Rate limited (429, per-minute). "
                      f"Waiting {wait}s before retry...")
                time.sleep(wait)
            else:
                # Not a transient error (bad request, auth issue, etc.) — don't retry blindly
                raise

    print(f"  [FAILED] Gave up on {filename} after {MAX_RETRIES} attempts: {last_error}")
    return {"nodes": [], "relationships": []}


def extract_all(doc_folder: str) -> dict:
    """Runs extraction across every .md file in doc_folder, merges results.
    Saves progress to OUTPUT_PATH after every document, so a crash never loses
    work already done — just re-run and it picks up where it left off."""
    all_nodes = {}
    all_relationships = []
    already_processed = set()

    # Resume support: if extracted_graph.json already exists with a record of
    # which files were processed, skip those and continue from where we stopped.
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH) as f:
            existing = json.load(f)
        for node in existing.get("nodes", []):
            all_nodes[node["id"]] = node
        all_relationships = existing.get("relationships", [])
        already_processed = set(existing.get("_processed_files", []))

        # Self-healing check: earlier versions of this script could mark a file
        # "processed" even when it returned 0 nodes (a complete extraction failure).
        # Verify every "processed" file actually has at least one node pointing
        # back to it via source_doc — if not, un-mark it so it gets retried below.
        docs_with_real_nodes = {
            n.get("properties", {}).get("source_doc")
            for n in all_nodes.values()
            if n.get("properties", {}).get("source_doc")
        }
        falsely_marked = already_processed - docs_with_real_nodes
        if falsely_marked:
            print(f"[SELF-HEAL] Found {len(falsely_marked)} file(s) marked 'processed' "
                  f"with no actual extracted data — will retry these: "
                  f"{sorted(falsely_marked)}\n")
            already_processed -= falsely_marked

        if already_processed:
            print(f"Resuming: {len(already_processed)} documents already processed "
                  f"({len(all_nodes)} nodes, {len(all_relationships)} relationships so far).\n")

    filenames = sorted(f for f in os.listdir(doc_folder) if f.endswith(".md"))
    remaining = [f for f in filenames if f not in already_processed]
    print(f"Found {len(filenames)} documents total, {len(remaining)} remaining to process.\n")

    for i, filename in enumerate(remaining, 1):
        filepath = os.path.join(doc_folder, filename)
        print(f"[{i}/{len(remaining)}] Extracting: {filename}")

        result = extract_from_document(filepath)

        for node in result["nodes"]:
            node_id = node["id"]
            if node_id in all_nodes:
                all_nodes[node_id]["properties"].update(node.get("properties", {}))
            else:
                all_nodes[node_id] = node

        all_relationships.extend(result["relationships"])

        # Only mark this file as done if it actually produced at least one node.
        # An empty result means every retry attempt failed (see extract_from_document) —
        # leaving it unmarked means the NEXT run will retry it instead of silently
        # treating "gave up" the same as "succeeded".
        if result["nodes"]:
            already_processed.add(filename)
            print(f"    -> {len(result['nodes'])} nodes, {len(result['relationships'])} relationships")
        else:
            print(f"    -> 0 nodes returned — NOT marking as processed, will retry on next run")

        # Save progress after every document — this is what makes the script resumable
        merged = {
            "nodes": list(all_nodes.values()),
            "relationships": all_relationships,
            "_processed_files": sorted(already_processed),
        }
        with open(OUTPUT_PATH, "w") as f:
            json.dump(merged, f, indent=2)

        if i < len(remaining):
            time.sleep(RATE_LIMIT_DELAY_SECONDS)

    print(f"\nTotal after merging: {len(all_nodes)} unique nodes, "
          f"{len(all_relationships)} relationships")

    return {
        "nodes": list(all_nodes.values()),
        "relationships": all_relationships,
        "_processed_files": sorted(already_processed),
    }


if __name__ == "__main__":
    result = extract_all("../plant-docs")
    print(f"\nSaved to {OUTPUT_PATH} — review this before running load_graph.py")
    if len(result["_processed_files"]) < 12:
        print(f"NOTE: only {len(result['_processed_files'])}/12 documents processed. "
              f"Re-run this script to continue from where it stopped.")

