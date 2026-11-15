"""Local API: http://localhost:8000. The dashboard (local or on GitHub Pages) switches
to live mode when this is reachable, which unlocks status edits and 'Run now'."""

import threading

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import export, pipeline
from .config import ROOT
from .db import STATUSES, connect

app = FastAPI(title="GenAI Job Radar")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://[a-z0-9-]+\.github\.io|http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"], allow_headers=["*"],
)


@app.middleware("http")
async def private_network(request: Request, call_next):
    # Chrome asks before a public site (GitHub Pages) calls localhost; this header says yes.
    response = await call_next(request)
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response


_run_lock = threading.Lock()
_run_state = {"running": False, "last": None}


@app.get("/api/health")
def health():
    return {"ok": True, "running": _run_state["running"]}


@app.get("/api/snapshot")
def snapshot():
    data = export.build(personal=True)
    data["live"] = True
    data["run"] = _run_state
    return data


class JobPatch(BaseModel):
    status: str | None = None
    notes: str | None = None


@app.patch("/api/jobs/{job_id:path}")
def patch_job(job_id: str, body: JobPatch):
    if body.status is not None and body.status not in STATUSES:
        raise HTTPException(400, f"status must be one of {STATUSES}")
    with connect() as conn:
        if not conn.execute("SELECT 1 FROM jobs WHERE id=?", (job_id,)).fetchone():
            raise HTTPException(404, "job not found")
        if body.status is not None:
            conn.execute("UPDATE jobs SET status=? WHERE id=?", (body.status, job_id))
        if body.notes is not None:
            conn.execute("UPDATE jobs SET notes=? WHERE id=?", (body.notes, job_id))
    return {"ok": True}


class QuestionPatch(BaseModel):
    practiced: bool


@app.patch("/api/questions/{qid}")
def patch_question(qid: int, body: QuestionPatch):
    with connect() as conn:
        conn.execute("UPDATE questions SET practiced=? WHERE id=?", (int(body.practiced), qid))
    return {"ok": True}


def _run_bg(skip_web: bool):
    try:
        _run_state["last"] = pipeline.run(skip_web=skip_web)
        export.write_snapshot()
    except Exception as ex:
        _run_state["last"] = {"errors": [f"run failed: {ex}"]}
    finally:
        _run_state["running"] = False
        _run_lock.release()


@app.post("/api/run")
def run_now(skip_web: bool = False):
    if not _run_lock.acquire(blocking=False):
        raise HTTPException(409, "a run is already in progress")
    _run_state["running"] = True
    threading.Thread(target=_run_bg, args=(skip_web,), daemon=True).start()
    return {"started": True}


# Serve a built dashboard at / when frontend/dist exists (npm run build).
_dist = ROOT / "frontend" / "dist"
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = _dist / path
        return FileResponse(f if path and f.is_file() else _dist / "index.html")
