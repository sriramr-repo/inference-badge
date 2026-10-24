"""Inference Badge — Streamlit stage dashboard."""
from __future__ import annotations

import os
import time

import pandas as pd
import streamlit as st

from database import (
    DatabaseError, create_demo_handshake, health_check, lead_context,
    list_leads, seed_demo_data, update_company_enrichment,
)
from enrichment import EnrichmentError, enrich_company, generate_strategy_brief

st.set_page_config(
    page_title="Inference Badge | Booth Coordination",
    page_icon="IB",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  .stApp { background: #0b1020; color: #eef2ff; }
  [data-testid="stSidebar"] { background: #11182b; }
  [data-testid="stMetric"] { background: #131d33; border: 1px solid #283653; padding: 14px; border-radius: 12px; }
  .hero { padding: 20px 24px; border: 1px solid #2c3b5c; border-radius: 16px; background: linear-gradient(120deg,#172544,#10182b); margin-bottom: 16px; }
  .muted { color: #a7b4cf; }
  .pill { display:inline-block; padding:4px 9px; border-radius:99px; background:#1c3651; color:#a8ddff; font-size:12px; }
  div[data-testid="stDataFrame"] { border: 1px solid #283653; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
  <div class="pill">LIVE GRAPH • HUMAN-IN-THE-LOOP</div>
  <h1 style="margin:10px 0 4px 0;">INFERENCE BADGE</h1>
  <div class="muted">Conference-floor intelligence · proximity coordination · explainable outreach</div>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## Booth control")
    st.caption("Local prototype · FalkorDB + OpenAI + optional Bright Data")
    if st.button("Refresh graph", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    if st.button("Initialize demo data", use_container_width=True, type="primary"):
        ok, message = seed_demo_data()
        (st.success if ok else st.error)(message)
        if ok:
            st.rerun()
    st.divider()
    st.markdown("### Simulate proximity")
    with st.form("handshake_form", clear_on_submit=True):
        name = st.text_input("Attendee name", placeholder="e.g. Jordan")
        company = st.text_input("Company", placeholder="e.g. OpenAI")
        teammate = st.selectbox("Team member", ["Alice", "Bob"])
        location_shared = st.toggle("Location sharing enabled", value=True)
        submitted = st.form_submit_button("Register check-in", use_container_width=True)
        if submitted:
            if not company.strip():
                st.error("Enter a company.")
            elif location_shared and not name.strip():
                st.error("Enter a name when location sharing is enabled.")
            else:
                try:
                    new_id = create_demo_handshake(name, company, teammate, location_shared)
                    st.session_state["selected_lead_id"] = new_id
                    st.success("Demo check-in registered.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not register check-in: {exc}")
    st.divider()
    st.markdown("### Integrations")
    st.write("FalkorDB", "Connected" if health_check()[0] else "Unavailable")
    st.write("OpenAI", "Configured" if os.getenv("OPENAI_API_KEY") else "Fallback brief")
    st.write("Bright Data", "Configured" if (os.getenv("BRIGHT_DATA_API_TOKEN") and os.getenv("BRIGHT_DATA_WEB_UNLOCKER_ZONE")) else "Demo fallback")

try:
    db_ok, db_message = health_check()
    if not db_ok:
        st.error(f"FalkorDB is not reachable: {db_message}")
        st.info("Start FalkorDB, then click **Initialize demo data**. Example: `docker run --name inference-badge-db -p 6379:6379 -d falkordb/falkordb`")
        st.stop()
    leads = list_leads()
except DatabaseError as exc:
    st.error(str(exc))
    st.stop()

if not leads:
    st.warning("The graph is connected but contains no leads. Click **Initialize demo data** in the sidebar.")
    st.stop()

df = pd.DataFrame(leads)
if "selected_lead_id" not in st.session_state or st.session_state["selected_lead_id"] not in set(df["id"].dropna()):
    st.session_state["selected_lead_id"] = str(df.iloc[0]["id"])

total = len(df)
shared = int((df["locationShared"] == True).sum()) if "locationShared" in df else 0
enriched = int((df["enriched"] == True).sum()) if "enriched" in df else 0
hot = int(df["status"].fillna("").str.contains("hot", case=False).sum()) if "status" in df else 0

m1, m2, m3, m4 = st.columns(4)
m1.metric("Graph leads", total)
m2.metric("Location sharing on", shared)
m3.metric("Enriched companies", enriched)
m4.metric("Hot prospects", hot)

left, right = st.columns([1.12, 1], gap="large")
with left:
    st.subheader("Live lead network")
    st.caption("Select a lead to inspect graph lineage and generate an explainable briefing.")
    display = df.copy()
    display["privacy"] = display["locationShared"].map({True: "Shared", False: "Shielded"}).fillna("Unknown")
    display["company"] = display["company"].fillna("Unknown")
    display["status"] = display["status"].fillna("Unclassified")
    view = display[["name", "company", "status", "privacy", "teammate", "session"]].rename(columns={
        "name": "Attendee", "company": "Company", "status": "Status",
        "privacy": "Privacy", "teammate": "Teammate", "session": "Session",
    })
    st.dataframe(view, use_container_width=True, hide_index=True, height=260)
    choices = {
        f"{r.get('name') or 'Anonymous'} · {r.get('company') or 'Unknown'} · {r.get('id')}": str(r["id"])
        for r in leads
    }
    labels = list(choices)
    current_label = next((k for k, v in choices.items() if v == st.session_state["selected_lead_id"]), labels[0])
    selected_label = st.selectbox("Inspect lead", labels, index=labels.index(current_label))
    selected_id = choices[selected_label]
    st.session_state["selected_lead_id"] = selected_id
    selected = next((x for x in leads if str(x.get("id")) == selected_id), leads[0])

    st.markdown("#### Graph lineage")
    privacy_name = selected.get("name") if selected.get("locationShared") else "Anonymous Attendee"
    st.code(
        f"(:TeamMember {{name: '{selected.get('teammate') or 'Unknown'}'}})"
        f"-[:MET {{tracking: '{selected.get('tracking') or 'Unknown'}'}}]->"
        f"(:Lead {{id: '{selected_id}', name: '{privacy_name}'}})"
        f"-[:ATTENDING]->(:Session {{title: '{selected.get('session') or 'No linked session'}'}})"
        f"  Company: {selected.get('company') or 'Unknown'}  →  Technology: {selected.get('technology') or 'Not linked'}",
        language="text",
    )

with right:
    st.subheader("Corporate intelligence")
    st.markdown(f"### {selected.get('company') or 'Unknown company'}")
    c1, c2 = st.columns(2)
    c1.write("**Storage tier**")
    c1.write(selected.get("tier") or "Unclassified")
    c2.write("**Company size**")
    c2.write(selected.get("employees") or "Not available")
    st.write("**Funding / valuation**")
    st.write(selected.get("funding") or "Not available")
    st.write("**Session context**")
    st.write(selected.get("session") or "No linked session")
    st.caption("Seeded graph values are shown as stored. Unknown facts are not fabricated.")
    enrich_clicked = st.button("Run Bright Data enrichment", use_container_width=True)
    if enrich_clicked:
        try:
            with st.spinner("Fetching public company page through configured Bright Data endpoint…"):
                result = enrich_company(str(selected.get("company") or ""))
                if result.get("live") and result.get("data"):
                    update_company_enrichment(
                        str(selected.get("company") or ""), result["data"], result["source"]
                    )
                    st.success("Returned fields saved to FalkorDB.")
                elif result.get("live"):
                    st.info("Live page fetched, but no safe structured fields were detected. Existing values were not overwritten.")
                else:
                    st.info(result["evidence"])
                st.session_state["last_enrichment"] = result
                st.rerun()
        except EnrichmentError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Enrichment could not be saved: {exc}")

    last_enrichment = st.session_state.get("last_enrichment")
    if last_enrichment:
        st.markdown("**Latest enrichment run**")
        st.caption(last_enrichment.get("source", "Unknown source"))
        if last_enrichment.get("data"):
            st.json(last_enrichment["data"])
        with st.expander("Evidence preview"):
            st.write(last_enrichment.get("evidence", "No evidence returned."))

st.divider()
st.subheader("AI strategy card")
st.caption("OpenAI uses graph context and optional enrichment. If no API key is set, a deterministic fallback is shown.")
if st.button("Generate strategy brief", type="primary"):
    try:
        context = lead_context(st.session_state["selected_lead_id"])
        if not context:
            st.error("The selected lead could not be reloaded from FalkorDB.")
        else:
            with st.spinner("Building briefing from graph context…"):
                enrichment = st.session_state.get("last_enrichment")
                if enrichment and enrichment.get("live") is False:
                    enrichment = None
                st.session_state["strategy_brief"] = generate_strategy_brief(context, enrichment)
                st.session_state["brief_for"] = st.session_state["selected_lead_id"]
    except Exception as exc:
        st.error(f"Could not generate strategy brief: {exc}")

if st.session_state.get("strategy_brief") and st.session_state.get("brief_for") == st.session_state["selected_lead_id"]:
    st.markdown(st.session_state["strategy_brief"])
else:
    st.info("Choose a lead and generate a strategy brief to see a suggested opener, coordination warning, and evidence gaps.")

st.caption("Prototype boundary: check-ins are simulated in this dashboard. Real BLE/UWB mobile capture and MCP orchestration require separate device/worker integrations.")
