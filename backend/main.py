import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from stages import eazyreach, ocean, prospeo
from stages.brevo import _load_template, _render, _send_one
from utils.logger import logger

TEMPLATE_PATH = Path("templates/email.txt")
_SEND_DELAY = 2.0

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Outreach Pipeline API")

_cors_origins = ["http://localhost:5173"]
if _fe := os.getenv("FRONTEND_URL", ""):
    _cors_origins.append(_fe)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory job store ───────────────────────────────────────────────────────
#
#  Job shape:
#    status:     "running" | "checkpoint" | "sending" | "done" | "error" | "aborted"
#    stage:      0-4  (updated as each stage starts)
#    counts:     { companies, people, contacts }
#    contacts:   list[dict]  — populated after stage 3
#    email_log:  list[dict]  — populated after stage 4
#    emails_sent: int
#    error:      str | None

_jobs: dict[str, dict] = {}
_latest_job_id: str | None = None


def _new_job() -> dict:
    return {
        "status": "running",
        "stage": 0,
        "counts": {"companies": 0, "people": 0, "contacts": 0},
        "contacts": [],
        "email_log": [],
        "emails_sent": 0,
        "error": None,
    }


# ── Pydantic models ───────────────────────────────────────────────────────────

class RunRequest(BaseModel):
    domain: str


class TemplateUpdate(BaseModel):
    subject: str
    body: str


# ── Background tasks (sync → runs in anyio thread pool, won't block event loop)

def _pipeline_task(job_id: str, domain: str) -> None:
    global _latest_job_id
    job = _jobs[job_id]

    try:
        # Stage 1 — Ocean
        job["stage"] = 1
        logger.info("Job %s | Stage 1: find_lookalike_companies(%s)", job_id, domain)
        domains = ocean.find_lookalike_companies(domain)
        job["counts"]["companies"] = len(domains)
        logger.info("Job %s | Stage 1 done: %d domains", job_id, len(domains))

        # Stage 2 — Prospeo
        job["stage"] = 2
        logger.info("Job %s | Stage 2: find_decision_makers (%d domains)", job_id, len(domains))
        people = prospeo.find_decision_makers(domains)
        job["counts"]["people"] = len(people)
        logger.info("Job %s | Stage 2 done: %d people", job_id, len(people))

        # Stage 3 — EazyReach
        job["stage"] = 3
        logger.info("Job %s | Stage 3: resolve_emails (%d people)", job_id, len(people))
        contacts = eazyreach.resolve_emails(people)
        job["counts"]["contacts"] = len(contacts)
        job["contacts"] = contacts
        logger.info("Job %s | Stage 3 done: %d contacts", job_id, len(contacts))

        job["status"] = "checkpoint"
        _latest_job_id = job_id
        logger.info("Job %s | checkpoint — waiting for POST /api/confirm/%s", job_id, job_id)

    except Exception as exc:
        job["status"] = "error"
        job["error"] = str(exc)
        logger.error("Job %s | error at stage %d: %s", job_id, job["stage"], exc)


def _send_task(job_id: str) -> None:
    global _latest_job_id
    job = _jobs[job_id]
    contacts = job["contacts"]

    job["status"] = "sending"
    job["stage"] = 4
    logger.info("Job %s | Stage 4: send_emails (%d contacts)", job_id, len(contacts))

    try:
        subject_tpl, body_tpl = _load_template()
        sent = 0
        failed = 0
        email_log: list[dict] = []

        for i, contact in enumerate(contacts):
            name = contact.get("name", "")
            email = contact.get("email", "")
            company = (
                contact.get("company")
                or contact.get("domain", "").split(".")[0].capitalize()
            )
            subject = _render(subject_tpl, contact)
            body = _render(body_tpl, contact)
            now = datetime.now(timezone.utc).isoformat()

            try:
                _send_one(subject, body, contact)
                logger.info("Job %s | Sent to %s <%s>", job_id, name, email)
                sent += 1
                email_log.append({
                    "name": name,
                    "email": email,
                    "company": company,
                    "status": "sent",
                    "sent_at": now,
                })
            except Exception as exc:
                logger.error("Job %s | Failed for %s <%s>: %s", job_id, name, email, exc)
                failed += 1
                email_log.append({
                    "name": name,
                    "email": email,
                    "company": company,
                    "status": "failed",
                    "sent_at": now,
                })

            if i < len(contacts) - 1:
                time.sleep(_SEND_DELAY)

        job["emails_sent"] = sent
        job["email_log"] = email_log
        job["status"] = "done"
        _latest_job_id = job_id
        logger.info("Job %s | done: %d sent, %d failed", job_id, sent, failed)

    except Exception as exc:
        job["status"] = "error"
        job["error"] = str(exc)
        logger.error("Job %s | send error: %s", job_id, exc)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/api/run", status_code=202)
async def run_pipeline(req: RunRequest, background_tasks: BackgroundTasks):
    domain = req.domain.strip()
    if not domain:
        raise HTTPException(status_code=422, detail="domain must not be empty")

    job_id = str(uuid.uuid4())
    _jobs[job_id] = _new_job()
    background_tasks.add_task(_pipeline_task, job_id, domain)
    logger.info("Job %s | created for domain: %s", job_id, domain)
    return {"job_id": job_id}


@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "status": job["status"],
        "stage": job["stage"],
        "counts": job["counts"],
        "error": job["error"],
    }


@app.get("/api/contacts")
async def get_contacts():
    if not _latest_job_id:
        return []
    return _jobs[_latest_job_id]["contacts"]


@app.get("/api/emails")
async def get_emails():
    if not _latest_job_id:
        return []
    return _jobs[_latest_job_id]["email_log"]


@app.get("/api/template")
async def get_template():
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    first_line, _, rest = text.partition("\n")
    subject = first_line.removeprefix("Subject:").strip()
    body = rest.strip()
    return {"subject": subject, "body": body}


@app.post("/api/template")
async def update_template(update: TemplateUpdate):
    TEMPLATE_PATH.write_text(
        f"Subject: {update.subject}\n\n{update.body}\n",
        encoding="utf-8",
    )
    logger.info("Template updated — subject: %s", update.subject)
    return {"message": "Template saved"}


@app.post("/api/confirm/{job_id}")
async def confirm_send(job_id: str, background_tasks: BackgroundTasks):
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "checkpoint":
        raise HTTPException(
            status_code=400,
            detail=f"Job is not at checkpoint (status: {job['status']})",
        )
    background_tasks.add_task(_send_task, job_id)
    logger.info("Job %s | confirm received — queuing send", job_id)
    return {"message": "Sending started"}


@app.post("/api/abort/{job_id}")
async def abort_job(job_id: str):
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    job["status"] = "aborted"
    logger.info("Job %s | aborted", job_id)
    return {"message": "Aborted. No emails sent."}


@app.get("/health")
async def health():
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
