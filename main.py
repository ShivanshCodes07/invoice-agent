
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
import sqlite3
import json

app = FastAPI(title="A2A Invoice Agent")

DB = "invoice_state.db"

AGENT_CARD = {
    "protocolVersion": "0.3.0",
    "name": "A2A Invoice Agent",
    "description": "An agent for invoice processing with approval checks.",
    "url": "https://invoice-agent-cjsi.onrender.com/a2a/",
    "preferredTransport": "JSONRPC",
    "version": "1.0.0",
    "capabilities": {},
    "defaultInputModes": ["application/json"],
    "defaultOutputModes": ["application/json"],
    "skills": [
        {
            "id": "process_invoice",
            "name": "Process Invoice",
            "description": "Evaluate invoice approval status and limits.",
            "tags": ["invoice", "approval"],
            "examples": ["Process an invoice"]
        }
    ]
}

@app.get("/.well-known/agent-card.json")
def agent_card():
    return AGENT_CARD


def init_db():
    with sqlite3.connect(DB) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS invoice_state (
                invoice_id TEXT PRIMARY KEY,
                result TEXT NOT NULL
            )
        """)


init_db()


class Invoice(BaseModel):
    invoice_id: str
    amount: float = Field(gt=0)
    approved: bool
    approval_limit: float = Field(gt=0)
    evidence: list[str] = []


@app.get("/")
def home():
    return {"message": "A2A Invoice Agent is running!"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/a2a/")
def process_invoice(
    invoice: Invoice,
    idempotency_key: str = Header(alias="Idempotency-Key")
):
    if not idempotency_key.strip():
        raise HTTPException(400, "Idempotency-Key is required")

    with sqlite3.connect(DB) as con:
        existing = con.execute(
            "SELECT result FROM invoice_state WHERE invoice_id = ?",
            (invoice.invoice_id,)
        ).fetchone()

        if existing:
            return json.loads(existing[0])

        if not invoice.approved:
            result = {
                "action": "hold",
                "reason": "Approval not confirmed",
                "evidence": invoice.evidence
            }
        elif invoice.amount > invoice.approval_limit:
            result = {
                "action": "request_approval",
                "reason": "Invoice exceeds approval limit",
                "evidence": invoice.evidence
            }
        else:
            result = {
                "action": "pending_payment",
                "reason": "Approval checks passed; payment receipt required",
                "evidence": invoice.evidence
            }

        con.execute(
            "INSERT INTO invoice_state VALUES (?, ?)",
            (invoice.invoice_id, json.dumps(result))
        )

        return result
