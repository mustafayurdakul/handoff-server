"""`python -m handoff` (or `handoff`) starts the API server, which also runs the pipeline."""
import uvicorn

from . import settings


def main() -> None:
    # timeout_graceful_shutdown: open live feeds must not hold up Ctrl+C
    uvicorn.run("handoff.api:app", host=settings.HOST, port=settings.PORT, timeout_graceful_shutdown=1)


if __name__ == "__main__":
    main()
