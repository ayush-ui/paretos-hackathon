"""Central Anthropic/Claude client wrapper — the ONLY place the engine talks to an LLM.

Design rules (see docs/ANTI_REWARD_HACKING.md and docs/LLM_INTEGRATION.md):
  - The LLM is OPTIONAL. With no ANTHROPIC_API_KEY (or the `anthropic` package missing), every
    function here returns None and callers fall back to deterministic behavior. The engine's numbers
    are never affected.
  - The LLM only ever (A) PROPOSES candidate beliefs from free-text — which then pass the same
    deterministic curation gate — or (B) NARRATES already-verified numbers. It never computes a plan.

Model: claude-opus-4-8 (the current default; override via ANTHROPIC_MODEL only if you know why).
"""
from __future__ import annotations

import os
from typing import Optional, Type, TypeVar


def _load_dotenv_once() -> None:
    """Load project-root .env into the environment if python-dotenv is installed (no-op otherwise)."""
    try:
        from dotenv import load_dotenv, find_dotenv
        load_dotenv(find_dotenv(usecwd=True))
    except Exception:
        pass


_load_dotenv_once()

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")

_client = None
_checked = False


def _get_client():
    """Lazily construct the Anthropic client. Returns None if unavailable (no key / no package)."""
    global _client, _checked
    if _checked:
        return _client
    _checked = True
    if not os.environ.get("ANTHROPIC_API_KEY"):
        _client = None
        return None
    try:
        import anthropic  # imported lazily so the engine has zero hard dependency on it
        _client = anthropic.Anthropic()
    except Exception:
        _client = None
    return _client


def available() -> bool:
    """True if an LLM call could be made right now (key present + package importable)."""
    return _get_client() is not None


def narrate(prompt: str, system: str = "", max_tokens: int = 320) -> Optional[str]:
    """(B) Turn already-verified facts into plain English. Returns None on any failure → caller
    uses its deterministic template. The prompt MUST contain only values the engine already computed.
    """
    client = _get_client()
    if client is None:
        return None
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system or "You explain warehouse staffing decisions in plain, concise English.",
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in resp.content if b.type == "text").strip() or None
    except Exception:
        return None


T = TypeVar("T")


def _no_additional_props(node) -> None:
    """Recursively set additionalProperties:false on every object (required for strict tool schemas)."""
    if isinstance(node, dict):
        if node.get("type") == "object":
            node["additionalProperties"] = False
        for v in node.values():
            _no_additional_props(v)
    elif isinstance(node, list):
        for v in node:
            _no_additional_props(v)


def parse(prompt: str, schema: Type[T], system: str = "") -> Optional[T]:
    """(A) Parse free text into a validated Pydantic object (a candidate hypothesis). Returns None on
    failure → caller falls back to the structured `claimed_effect`. The returned object is a CLAIM,
    not a fact: it must still earn trust through curation before it influences any decision.

    Uses forced tool-use for structured output (version-robust across anthropic SDK releases).
    """
    client = _get_client()
    if client is None:
        return None
    try:
        json_schema = schema.model_json_schema()
        _no_additional_props(json_schema)
        tool = {"name": "record_result", "description": "Record the single structured result.",
                "input_schema": json_schema}
        resp = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system or "You extract structured, testable hypotheses from messy operational notes.",
            tools=[tool],
            tool_choice={"type": "tool", "name": "record_result"},
            messages=[{"role": "user", "content": prompt}],
        )
        payload = next((b.input for b in resp.content if b.type == "tool_use"), None)
        return schema(**payload) if payload is not None else None
    except Exception:
        return None
