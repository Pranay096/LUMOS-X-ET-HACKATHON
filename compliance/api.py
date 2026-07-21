"""
api.py — One FastAPI app, three endpoints:
  POST /ask               — general knowledge questions (Day 3 RAG pipeline)
  POST /check-compliance  — compliance check (Day A Compliance Agent, local Ollama)
  GET  /gaps                — Documentation Gap tracker: low-confidence questions
  GET  /health             — quick check the server is up

Both /ask and /check-compliance are called identically whether the request
came from the Lumos glasses (automatic, QR-triggered) or a manual web/mobile
form. There is no separate "fallback mode" in this API — both flows POST the
same shape of request; only where the equipment_id/question came from
differs, and the frontend (glasses firmware or web form) is what decides
that upstream.

Run with:  uvicorn api:app --reload --host 0.0.0.0 --port 8000
"""

import sys
import os

# Day 3's RAG pipeline (retrieve.py, synthesize.py) lives in the sibling
# rag/ folder — import it directly rather than duplicating that code here.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "rag"))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from retrieve import retrieve
from synthesize import synthesize_answer
from compliance_agent import check_compliance
import gap_tracker

app = FastAPI(title="Lumos AI Backend", version="0.1")

# CORS: the mobile web UI is a plain HTML file (opened directly in a browser,
# not served from this same origin), so without this the browser blocks its
# fetch() calls to this API entirely — allow all origins, fine for a demo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str


class ComplianceRequest(BaseModel):
    equipment_id: str
    observed_state: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask")
def ask(req: AskRequest):
    try:
        retrieval_result = retrieve(req.question)
        result = synthesize_answer(retrieval_result)
        result.pop("_context_used", None)  # internal debug field, not for API consumers
        gap_tracker.log_if_gap(req.question, result)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/check-compliance")
def check_compliance_endpoint(req: ComplianceRequest):
    try:
        return check_compliance(req.equipment_id, req.observed_state)
    except RuntimeError as e:
        # RuntimeErrors from ollama_client are already clear, actionable
        # messages (Ollama not running, model not pulled) — surface as-is.
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/gaps")
def get_gaps():
    return {"gaps": gap_tracker.get_gaps()}
