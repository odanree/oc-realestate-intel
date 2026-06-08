"""
Langfuse observability.

Tracing is opt-in: if LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY aren't set,
get_langchain_handler() returns None and call sites pass an empty callbacks
list. No runtime overhead, no behavior change.

When keys are set, every LangGraph node + every Anthropic SDK call gets
captured as a span on the same trace, with token counts and latency.
"""

from __future__ import annotations

import contextvars
import logging
from contextlib import contextmanager

from app.config import settings

# Per-trace tag accumulator. tag_trace() appends here; trace_span() flushes
# the accumulated set onto the root span as a JSON list at exit. We can't
# accumulate via OTel attributes alone because set_attribute overwrites.
_tag_acc: contextvars.ContextVar[list[str] | None] = contextvars.ContextVar(
    "trace_tag_acc", default=None,
)

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


@contextmanager
def trace_span(name: str, input_data: dict | None = None):
    """Context manager that opens a Langfuse span AS THE ACTIVE OTel context
    and yields its trace_id. Yields None when tracing is disabled.

    Why as-current matters: subsequent `update_current_trace` calls (tags +
    metadata stamped from inside LangGraph nodes) and the LangChain callback
    handler both look up the active OTel context. If the outer span isn't
    current, tags vanish and the callback creates a *separate* trace —
    which is exactly what happened the first time around.

    Usage:
        with observability.trace_span("oci.query", {"query": q}) as trace_id:
            result = await graph.ainvoke(state, config=...)
    """
    client = _client()
    if client is None:
        yield None
        return
    try:
        import json

        from opentelemetry.trace import get_current_span
        with client.start_as_current_observation(
            name=name, as_type="span", input=input_data,
        ) as span:
            token = _tag_acc.set([])
            try:
                yield span.trace_id
            finally:
                tags = _tag_acc.get() or []
                if tags:
                    cur = get_current_span()
                    if cur is not None and cur.is_recording():
                        cur.set_attribute(
                            "langfuse.trace.tags", json.dumps(tags),
                        )
                _tag_acc.reset(token)
    except Exception as e:
        log.warning("Langfuse trace_span failed: %s", e)
        yield None


def tag_trace(tags: list[str] | None = None, metadata: dict | None = None) -> None:
    """Add tags + metadata to the currently active trace.

    Langfuse v4 doesn't expose a Python `update_current_trace`, so we write
    OTel span attributes on the active span; the Langfuse exporter maps
    `langfuse.trace.tags` / `langfuse.trace.metadata.<k>` onto the trace
    when the span is flushed. Tags accumulate across calls.

    No-op when tracing is disabled.
    """
    client = _client()
    if client is None:
        return
    try:
        import json

        from opentelemetry.trace import get_current_span
        if tags:
            # Accumulate — the actual OTel attribute is written once on span exit
            # by trace_span(). set_attribute overwrites, so we can't append here.
            acc = _tag_acc.get()
            if acc is not None:
                for t in tags:
                    if t not in acc:
                        acc.append(t)
        if metadata:
            span = get_current_span()
            if span is None or not span.is_recording():
                return
            for k, v in metadata.items():
                if v is None:
                    continue
                payload = v if isinstance(v, (str, int, float, bool)) else json.dumps(v, default=str)
                span.set_attribute(f"langfuse.trace.metadata.{k}", payload)
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
