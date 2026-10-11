"""JSON over HTTP for the Jira and GitLab clients: standard library only, proxies from http(s)_proxy."""
import json
import urllib.error
import urllib.request


def request(method: str, url: str, headers: dict[str, str], body=None, timeout: int = 30):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Accept": "application/json", **({"Content-Type": "application/json"} if data else {}), **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {url}: HTTP {e.code} {e.read()[:500].decode(errors='replace')}") from None
    return json.loads(raw) if raw.strip() else None
