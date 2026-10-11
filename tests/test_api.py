"""The API has no login, so other web pages must not reach it: neither by DNS rebinding nor by a cross-site POST."""
import asyncio

from handoff import api


def status(method: str, path: str, headers: dict[str, str]) -> int:
    """Call the app directly (no lifespan, so no pipeline threads) and return the response status."""
    sent = []
    scope = {"type": "http", "http_version": "1.1", "method": method, "scheme": "http", "path": path,
             "raw_path": path.encode(), "root_path": "", "query_string": b"", "client": ("127.0.0.1", 1),
             "server": ("127.0.0.1", 8765), "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()]}

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    asyncio.run(api.app(scope, receive, send))
    return next(m["status"] for m in sent if m["type"] == "http.response.start")


def test_only_this_machine_as_host(runs):
    assert status("GET", "/api/tickets", {"host": "127.0.0.1:8765"}) == 200
    assert status("GET", "/api/tickets", {"host": "localhost:5173"}) == 200, "the Vite proxy keeps the UI's Host"
    assert status("GET", "/api/tickets", {"host": "attacker.example:8765"}) == 400, "DNS rebinding was let in"


def test_cross_site_post_refused(runs):
    local = {"host": "127.0.0.1:8765"}
    assert status("POST", "/api/tickets/T-1/retry", {**local, "sec-fetch-site": "cross-site"}) == 403
    assert status("POST", "/api/tickets/T-1/retry", {**local, "sec-fetch-site": "same-origin"}) == 404, "no ticket"
    assert status("GET", "/api/tickets", {**local, "sec-fetch-site": "cross-site"}) == 200, "reads are not changes"
