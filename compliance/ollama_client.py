"""
ollama_client.py — Shared helper for calling local Ollama models via the
official `ollama` Python package (fully local, no cloud API, no API key).

Requires:
  1. Ollama installed and running: https://ollama.com/download
  2. The model pulled once: `ollama pull qwen3-vl:4b`

Uses Ollama's structured outputs feature (v0.5+): passing a JSON schema in
`format` constrains the model's output to match it exactly.
"""

import json
import time
from ollama import chat, ResponseError

GENERATION_MODEL = "qwen3-vl:4b"
CONTEXT_WINDOW = 8192  # Ollama defaults to 2048-4096 and silently truncates
                        # beyond that with no error — our prompts (system +
                        # multiple SOP excerpts) can exceed the default, so
                        # this is set explicitly rather than left to chance


def generate_structured(system_prompt: str, user_prompt: str, json_schema: dict,
                         temperature: float = 0.0, max_retries: int = 3) -> dict:
    """Calls the local Ollama model with a JSON schema constraint.
    Returns the parsed dict. Raises a clear, actionable RuntimeError if
    Ollama isn't running or the model isn't pulled — these are the two
    most likely failure modes for a local setup, so we detect and name
    them specifically rather than letting a raw traceback surface.

    Grammar-constrained JSON decoding on small local models has been
    observed to occasionally return an EMPTY response rather than malformed
    JSON — this is treated as its own retryable case, and the last attempt
    drops the schema constraint entirely (asking for JSON via the prompt
    instead) as a fallback, since an unconstrained generation succeeding is
    better than a constrained one returning nothing."""
    last_error = None

    for attempt in range(1, max_retries + 1):
        use_schema = attempt < max_retries  # last attempt: drop constraint, try plain JSON prompting
        try:
            if use_schema:
                response = chat(
                    model=GENERATION_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    format=json_schema,
                    think=False,  # qwen3-family models can route their whole
                                  # answer into message.thinking and leave
                                  # message.content empty — disable reasoning
                                  # mode so the JSON lands where we read it
                    options={"temperature": temperature, "num_ctx": CONTEXT_WINDOW},
                )
            else:
                print(f"  [FALLBACK] Retrying without schema constraint (plain JSON prompting)...")
                response = chat(
                    model=GENERATION_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt + "\n\nRespond with ONLY the JSON object, no other text."},
                        {"role": "user", "content": user_prompt},
                    ],
                    format="json",
                    think=False,
                    options={"temperature": temperature, "num_ctx": CONTEXT_WINDOW},
                )

            content = response.message.content
            if not content or not content.strip():
                # Defensive fallback: some model builds ignore think=False and
                # still route output into .thinking instead of .content. If
                # that field has something, try to salvage it before giving up.
                thinking = getattr(response.message, "thinking", None)
                if thinking and thinking.strip():
                    print(f"  [NOTE] content was empty but thinking had text — "
                          f"attempting to parse JSON from there instead")
                    content = thinking

            if not content or not content.strip():
                raise json.JSONDecodeError("Empty response from model", "", 0)

            return json.loads(content)

        except ResponseError as e:
            status = getattr(e, "status_code", None)
            if status == 404 or "not found" in str(e).lower():
                raise RuntimeError(
                    f"Model '{GENERATION_MODEL}' is not pulled locally.\n"
                    f"Run this once in a terminal: ollama pull {GENERATION_MODEL}"
                ) from e
            last_error = e
            print(f"  [RETRY {attempt}/{max_retries}] Ollama response error: {e}")
            time.sleep(3)

        except ConnectionError as e:
            raise RuntimeError(
                "Could not connect to Ollama on http://localhost:11434.\n"
                "Is Ollama running? Start it with: ollama serve\n"
                "(On Windows/Mac, the Ollama desktop app usually runs this "
                "automatically in the background — check for its icon in the "
                "system tray / menu bar.)"
            ) from e

        except json.JSONDecodeError as e:
            last_error = e
            reason = "empty response" if "Empty response" in str(e) else f"invalid JSON: {e}"
            print(f"  [RETRY {attempt}/{max_retries}] Model returned {reason}")
            time.sleep(2)

    raise RuntimeError(f"Gave up after {max_retries} attempts. Last error: {last_error}")
