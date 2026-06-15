"""Governance node — thin adapter that wires `agent-governance` to this app.

The reusable policy + sink machinery lives in the standalone
[agent-governance](https://github.com/odanree/agent-governance) package. This
module:

  1. Picks the checks this agent needs (disclaimer + URL allowlist + injection).
  2. Configures the canonical disclaimer text for the synthetic-owner story
     (see ADR-0004 and ADR-0007).
  3. Adapts our Langfuse observability functions into the package's
     `ObservabilityAdapter` Protocol.
  4. Builds an `IncidentSink` from settings (LogSink by default;
     GitHubIssueSink opt-in via env).
  5. Exposes the resulting `governance_node` for the LangGraph supervisor.

When this list of checks (or the sink config, or the trace adapter) needs to
change, edit this file. The agent-governance package itself stays generic.
"""

from __future__ import annotations

from agent_governance import (
    DisclaimerCheck,
    NullObservabilityAdapter,
    ObservabilityAdapter,
    PromptInjectionCheck,
    URLAllowlistCheck,
    build_governance_node,
    build_sink,
)

from app import observability as _obs
from app.config import settings

# Re-exported for places (e.g. summarize prompt rule documentation) that
# want the exact disclaimer string without round-tripping through provenance.
CANONICAL_DISCLAIMER = (
    "*Owner and title-chain data shown are synthetic and illustrative only — "
    "not from authoritative OC assessor records.*"
)


class _LangfuseAdapter(NullObservabilityAdapter):
    """Bridge agent-governance's ObservabilityAdapter Protocol to our
    Langfuse helpers in `app.observability`."""

    def get_trace_id(self) -> str | None:
        return _obs.get_trace_id()

    def tag_trace(self, tags: list[str], metadata: dict | None = None) -> None:
        _obs.tag_trace(tags=tags, metadata=metadata)

    def create_score(
        self, trace_id: str, name: str, value: float, comment: str | None = None
    ) -> None:
        _obs.create_score(trace_id=trace_id, name=name, value=value, comment=comment)


def _build_node():
    allowlist = [
        a.strip()
        for a in (settings.governance_url_allowlist or "").split(",")
        if a.strip()
    ]
    checks = [
        DisclaimerCheck(canonical=CANONICAL_DISCLAIMER),
        URLAllowlistCheck(allowlist=allowlist),
        PromptInjectionCheck(),
    ]
    sink = build_sink(
        settings.governance_incident_sink,
        github_repo=settings.governance_github_repo,
        github_token=settings.github_token,
        extra_labels=["oc-realestate-intel"],
    )
    obs: ObservabilityAdapter = _LangfuseAdapter()
    return build_governance_node(checks=checks, sink=sink, observability=obs)


# Lazy singleton — settings are read at first call, not import.
_node = None


async def governance_node(state: dict) -> dict:
    global _node
    if _node is None:
        _node = _build_node()
    return await _node(state)


__all__ = ["CANONICAL_DISCLAIMER", "governance_node"]
