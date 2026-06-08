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


# ---------------------------------------------------------------------------
# In-trace mutations: tags, metadata, scores. No-ops when disabled.
# ---------------------------------------------------------------------------


def _client():
    """Return the Langfuse client if tracing is enabled, else None."""
    if get_langchain_handler() is None:
        return None
    try:
        from langfuse import get_client
        return get_client()
    except Exception as e:
        log.warning("Langfuse get_client failed: %s", e)
        return None


def start_trace_span(name: str, input_data: dict | None = None):
    """Open a Langfuse span and return (span, trace_id). Returns (None, None)
    if tracing is disabled. The returned span must be `.end()`-ed when done.

    Uses the v4+ start_observation API; the returned LangfuseSpan exposes
    `.trace_id` synchronously so we can ship it back to the caller before
    the agent has even started running.
    """
    client = _client()
    if client is None:
        return None, None
    try:
        span = client.start_observation(name=name, as_type="span", input=input_data)
        return span, span.trace_id
    except Exception as e:
        log.warning("Langfuse start_trace_span failed: %s", e)
        return None, None


def end_span(span) -> None:
    """End a span returned by start_trace_span. No-op when span is None."""
    if span is None:
        return
    try:
        span.end()
    except Exception as e:
        log.warning("Langfuse span.end() failed: %s", e)


def tag_trace(tags: list[str] | None = None, metadata: dict | None = None) -> None:
    """Add tags + metadata to whatever trace is currently active.

    Safe to call from anywhere inside a LangChain callback context (the
    Langfuse SDK tracks the active trace via OpenTelemetry-style context).
    No-op when tracing is disabled.
    """
    client = _client()
    if client is None:
        return
    try:
        kwargs: dict = {}
        if tags:
            kwargs["tags"] = tags
        if metadata:
            kwargs["metadata"] = metadata
        client.update_current_trace(**kwargs)
    except Exception as e:
        log.warning("Langfuse tag_trace failed: %s", e)


def get_trace_id() -> str | None:
    """Return the current Langfuse trace id, or None if no trace is active."""
    client = _client()
    if client is None:
        return None
    try:
        return client.get_current_trace_id()
    except Exception:
        return None


def create_score(
    trace_id: str,
    name: str,
    value: float,
    comment: str | None = None,
) -> None:
    """Attach a numeric score to a finished trace.

    Used for two things:
      - /api/v1/feedback: user thumbs → Langfuse score (name='user_feedback')
      - scripts/eval.py: judge faithfulness → score (name='faithfulness')

    Range conventions: 1.0 = thumbs up, -1.0 = thumbs down for feedback;
    0.0-10.0 for judge scores.
    """
    client = _client()
    if client is None:
        return
    try:
        client.create_score(
            trace_id=trace_id,
            name=name,
            value=value,
            comment=comment,
        )
        client.flush()  # short-lived score writes — flush immediately
    except Exception as e:
        log.warning("Langfuse create_score failed: %s", e)
