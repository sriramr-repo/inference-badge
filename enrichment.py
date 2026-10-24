"""Optional Bright Data company enrichment and OpenAI strategy brief generation.

Bright Data's MCP server is not assumed to be a generic HTTP endpoint. For an
out-of-the-box local prototype this module supports Bright Data's Web Unlocker
API when BRIGHT_DATA_API_TOKEN and BRIGHT_DATA_WEB_UNLOCKER_ZONE are configured.
Without credentials, it returns a clearly labeled demo fallback and never
pretends that a live scrape occurred.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.parse import quote

import requests
from openai import OpenAI


class EnrichmentError(RuntimeError):
    pass


def _bright_data_enabled() -> bool:
    return bool(os.getenv("BRIGHT_DATA_API_TOKEN") and os.getenv("BRIGHT_DATA_WEB_UNLOCKER_ZONE"))


def enrich_company(company: str) -> dict[str, Any]:
    """Fetch a public company homepage through Bright Data Web Unlocker.

    The returned page text is evidence, not structured financial data. We only
    infer fields when a simple, explicit pattern is present, and label the
    source so the UI can distinguish it from seeded values.
    """
    if not _bright_data_enabled():
        return {
            "live": False,
            "source": "Demo fallback (Bright Data credentials not configured)",
            "data": {},
            "evidence": "No live scrape performed. Seed data remains unchanged.",
        }

    domain_map = {
        "stripe": "https://stripe.com",
        "vercel": "https://vercel.com",
        "openai": "https://openai.com",
        "anthropic": "https://anthropic.com",
        "databricks": "https://databricks.com",
        "crusoe": "https://crusoe.ai",
    }
    domain = domain_map.get(company.casefold(), "https://www.google.com/search?q=" + quote(company + " official website"))
    endpoint = os.getenv("BRIGHT_DATA_REQUEST_URL", "https://api.brightdata.com/request")
    payload = {
        "zone": os.environ["BRIGHT_DATA_WEB_UNLOCKER_ZONE"],
        "url": domain,
        "format": "raw",
    }
    try:
        response = requests.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {os.environ['BRIGHT_DATA_API_TOKEN']}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=(5, 25),
        )
        response.raise_for_status()
        body = response.text[:120_000]
        clean = re.sub(r"<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>", " ", body,
                        flags=re.I | re.S)
        clean = re.sub(r"<[^>]+>", " ", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        # Avoid claiming financial facts not found in source text.
        data: dict[str, Any] = {}
        employee = re.search(r"\b(\d[\d,]*(?:\+)?\s+(?:employees|team members|people))\b", clean, re.I)
        if employee:
            data["employeeCount"] = employee.group(1)
        return {
            "live": True,
            "source": f"Bright Data Web Unlocker ({domain})",
            "data": data,
            "evidence": clean[:5000] or "The fetched page contained no readable text.",
        }
    except requests.RequestException as exc:
        raise EnrichmentError(f"Bright Data request failed: {exc}") from exc


def generate_strategy_brief(context: dict[str, Any], enrichment: dict[str, Any] | None = None) -> str:
    """Generate a concise, evidence-grounded brief using OpenAI's chat completion SDK."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return fallback_brief(context, enrichment)

    client = OpenAI(api_key=api_key, timeout=20.0, max_retries=1)
    payload = {
        "graph_context": context,
        "external_enrichment": enrichment or {"live": False, "source": "Not run"},
        "instructions": [
            "Write a concise stage-dashboard briefing with: situation, suggested opener, coordination warning, and evidence gaps.",
            "Use only the supplied facts. Do not invent financial metrics, recent news, relationships, or attendee interests.",
            "Clearly label missing data. If locationShared is false, preserve anonymity and do not infer identity.",
            "If another teammate is already talking to the lead, recommend coordinating rather than interrupting.",
            "Keep it under 130 words and make it immediately usable by a field team.",
        ],
    }
    try:
        completion = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0.2,
            max_tokens=220,
            messages=[
                {"role": "system", "content": "You are Inference Badge's explainable conference coordination assistant."},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
            ],
        )
        text = completion.choices[0].message.content
        return text.strip() if text else fallback_brief(context, enrichment)
    except Exception as exc:
        return fallback_brief(context, enrichment) + f"\n\n_OpenAI unavailable; deterministic fallback used ({type(exc).__name__})._"


def fallback_brief(context: dict[str, Any], enrichment: dict[str, Any] | None = None) -> str:
    name = context.get("name") or "Attendee"
    company = context.get("company") or "Unknown company"
    teammate = context.get("teammate") or "A teammate"
    session = context.get("session") or "No linked session in the graph"
    focus = context.get("teammateFocus") or context.get("technology") or "the team's product focus"
    shared = context.get("locationShared") is True
    identity = name if shared else "Anonymous attendee (privacy shield active)"
    warning = f"Check with {teammate} before approaching; the graph records a prior interaction." if context.get("teammate") else "No teammate interaction was returned by the graph."
    source = (enrichment or {}).get("source", "No external enrichment run")
    return (
        f"**Situation:** {identity} is associated with {company}. Status: {context.get('status') or 'unknown'}. "
        f"Company tier: {context.get('tier') or 'unclassified'}; funding/valuation: {context.get('funding') or 'not available'}; "
        f"employees: {context.get('employees') or 'not available'}.\\n\\n"
        f"**Suggested opener:** “I noticed {company} is connected to {session}. What are you focused on there?” "
        f"Keep the conversation aligned to {focus}.\\n\\n"
        f"**Coordination:** {warning}\\n\\n"
        f"**Evidence:** Graph context plus: {source}. Verify any missing firmographic facts before presenting them as current."
    )
