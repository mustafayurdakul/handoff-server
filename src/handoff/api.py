"""HTTP API for the UI (handoff-ui). Starting the app also starts the pipeline threads."""
import asyncio
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from . import pipeline, sandbox, settings, store
from .integrations import jira


@asynccontextmanager
async def lifespan(_app: FastAPI):
    sandbox.check()
    settings.INBOX.mkdir(parents=True, exist_ok=True)
    stop = threading.Event()
    threads = [(pipeline.worker_loop, (stop,)), (pipeline.intake_loop, (stop,))]
    if settings.CONFIG.get("jira", {}).get("enabled"):
        threads.append((jira.loop, (stop, settings.CONFIG["jira"], pipeline.project_error)))
    for target, args in threads:
        threading.Thread(target=target, args=args, daemon=True).start()
    yield
    stop.set()
    sandbox.kill_all()


app = FastAPI(title="handoff", lifespan=lifespan)


class Answer(BaseModel):
    text: str


def get(tid: str) -> dict:
    if not store.ID_RE.match(tid) or not (store.path(tid) / "state.json").exists():
        raise HTTPException(404, "Ticket not found")
    return store.load(tid)


@app.get("/api/tickets")
def list_tickets() -> list[dict]:
    keys = ("id", "title", "project", "stage", "round", "tokens", "since", "updated")
    return [{k: t.get(k) for k in keys} for t in store.all_tickets()]


@app.get("/api/tickets/{tid}")
def ticket(tid: str) -> dict:
    t = get(tid)
    jira_url = settings.CONFIG.get("jira", {}).get("url", "").rstrip("/")
    extra = {"jira_url": f"{jira_url}/browse/{t['jira']}"} if t.get("jira") and jira_url else {}
    return {**t, "text": store.text(t), "rounds": settings.CONFIG["limits"]["rounds"],
            "agent": settings.CONFIG["agent"], **extra}


@app.get("/api/tickets/{tid}/events")
async def events(tid: str, request: Request) -> StreamingResponse:
    """The live feed over SSE. The event id is a byte offset, so a reconnecting browser resumes where it stopped."""
    get(tid)
    f = store.path(tid) / "events.jsonl"
    try:
        pos = int(request.headers.get("last-event-id", 0))
    except ValueError:
        pos = 0

    async def stream():
        nonlocal pos
        while not await request.is_disconnected():
            data = b""
            if f.exists():
                with open(f, "rb") as fh:
                    fh.seek(pos)
                    data = fh.read()
            end = data.rfind(b"\n") + 1  # a half-written last line waits for the next poll
            if end:
                pos += end
                lines = data[:end].rstrip(b"\n").decode().split("\n")  # not splitlines(): it also splits on U+2028
                yield f"id: {pos}\ndata: [{','.join(lines)}]\n\n"
            await asyncio.sleep(0.3)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.post("/api/tickets/{tid}/answer")
def answer(tid: str, body: Answer) -> dict:
    t = get(tid)
    if t["stage"] != "question":
        raise HTTPException(409, "Ticket is not waiting for an answer")
    if not body.text.strip():
        raise HTTPException(422, "Answer must not be empty")
    store.answer(t, body.text)
    return {"ok": True}


@app.post("/api/tickets/{tid}/retry")
def retry(tid: str) -> dict:
    t = get(tid)
    if t["stage"] not in ("failed", "rejected"):
        raise HTTPException(409, "Only failed or rejected tickets can be retried")
    store.requeue(t, "Re-queued manually")
    return {"ok": True}
