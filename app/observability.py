"""
Langfuse observability.

Tracing is opt-in: if LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY aren't set,
get_langchain_handler() returns None and call sites pass an empty callbacks
list. No runtime overhead, no behavior change.

When keys are set, every LangGraph node + every Anthropic SDK call gets
captured as a span on the same trace, with token counts and latency.
"""

from __future__ import annotations

import logging

from app.config import settings

log = logging.getLogger(__name__)

_handler = None
_initialized = False


def get_langchain_handler():
    """Return a Langfuse CallbackHandler instance, or None if keys aren't set.

    Lazy + memoized — first call constructs the handler, subsequent calls
    return the same instance so spans share a trace.
    """
    global _handler, _initialized
    if _initialized:
        return _handler
    _initialized = True

    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        log.info("Langfuse keys not configured — tracing disabled")
        return None

    try:
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler

        # The Langfuse SDK reads its keys from the singleton client.
        # Initialize once so both LangChain and direct-SDK traces land in
        # the same project.
        Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        _handler = CallbackHandler()
        log.info("Langfuse tracing enabled (host=%s)", settings.langfuse_host)
    except Exception as e:
        log.warning("Langfuse init failed (%s) — tracing disabled", e)
        _handler = None
    return _handler


def callbacks() -> list:
    """Convenience for the common LangChain call site:

        await llm.ainvoke(messages, config={"callbacks": observability.callbacks()})
    """
    handler = get_langchain_handler()
    return [handler] if handler is not None else []


def flush() -> None:
    """Drain pending events before shutdown — call from FastAPI lifespan."""
    if _handler is None:
        return
    try:
        from langfuse import get_client
        client = get_client()
        client.flush()
    except Exception as e:
        log.warning("Langfuse flush failed: %s", e)
