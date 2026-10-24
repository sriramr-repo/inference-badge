"""Inference Badge local product prototype."""
from __future__ import annotations

import os
import importlib
from typing import Any

import pandas as pd
import streamlit as st

import database as database_layer

if not hasattr(database_layer, "add_early_access_signup"):
    importlib.reload(database_layer)

from database import (
    DatabaseError,
    create_demo_handshake,
    health_check,
    lead_context,
    list_leads,
    add_early_access_signup,
    seed_demo_data,
    update_company_enrichment,
)
from demo_flow import (
    STEP_COUNT,
    advance_demo,
    log_demo_talk,
    new_demo_state,
    set_dave_sharing,
)
from enrichment import EnrichmentError, enrich_company, generate_strategy_brief
import conference_simulation as conference_simulation_module

if getattr(conference_simulation_module, "SIMULATION_MODULE_VERSION", 0) < 7:
    importlib.reload(conference_simulation_module)

render_simulation = conference_simulation_module.render_simulation


PAGES = (
    "Marketing",
    "Conference setup",
    "Business demo",
)
DEMO_STEPS = (
    "The sign-up list",
    "A badge is nearby",
    "Stop a double talk",
    "Privacy stays visible",
    "Connect and follow up",
)


def _go_to_demo() -> None:
    st.session_state["page"] = "Business demo"


def _go_to_marketing() -> None:
    st.session_state["page"] = "Marketing"


def _go_to_setup() -> None:
    st.session_state["page"] = "Conference setup"


def _go_to_login() -> None:
    st.session_state["page"] = "Login"


def _go_to_signup() -> None:
    st.session_state["page"] = "Sign up"


def _go_to_conference_day() -> None:
    st.session_state["page"] = "Conference day"


def _show_setup_preview() -> None:
    st.session_state["conference_setup_previewed"] = True


def _complete_setup_simulation() -> None:
    st.session_state["conference_setup_result"] = st.session_state[
        "conference_setup_sharing"
    ]


def _restart_setup_simulation() -> None:
    st.session_state["conference_setup_previewed"] = False
    st.session_state.pop("conference_setup_result", None)


def _set_page(page: str) -> None:
    st.session_state["page"] = page


def _advance_demo() -> None:
    st.session_state["demo_state"] = advance_demo(st.session_state["demo_state"])


def _restart_demo() -> None:
    st.session_state["demo_state"] = new_demo_state()


def _log_demo_talk() -> None:
    st.session_state["demo_state"] = log_demo_talk(st.session_state["demo_state"])


def _set_demo_sharing(value: bool) -> None:
    st.session_state["demo_state"] = set_dave_sharing(
        st.session_state["demo_state"], value
    )


def _set_phone_action(message: str) -> None:
    st.session_state["phone_action"] = message


def _pause_phone_sharing() -> None:
    st.session_state["phone_sharing"] = False
    st.session_state["phone_action"] = (
        "Sharing is paused in this demo preview; no real timer or device setting changed."
    )


def _clear_phone_profile() -> None:
    st.session_state["phone_sharing"] = False
    st.session_state["phone_profile_deleted"] = True
    st.session_state["phone_action"] = (
        "The local demo profile is hidden for this browser session only."
    )


def _approve_phone_summary() -> None:
    st.session_state["phone_summary_approved"] = True


def _badge_svg(
    size: int = 54,
    *,
    badge: str = "#0B1F3A",
    offset: str = "#FFE500",
    slot: str = "#FFFBEA",
    salesperson: str = "#FFFBEA",
    lead: str = "#FFE500",
) -> str:
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 80 80" role="img"
         aria-label="Inference Badge logo" xmlns="http://www.w3.org/2000/svg">
      <rect x="17" y="15" width="52" height="60" rx="14" fill="{offset}"/>
      <rect x="12" y="10" width="52" height="60" rx="14" fill="{badge}"/>
      <rect x="28" y="15" width="20" height="5" rx="2.5" fill="{slot}"/>
      <path d="M27 47 C37 35 45 58 55 42" fill="none" stroke="{lead}"
            stroke-width="4" stroke-linecap="round"/>
      <circle cx="27" cy="47" r="5" fill="{salesperson}"/>
      <circle cx="55" cy="42" r="5" fill="{lead}"/>
      <circle cx="55" cy="42" r="10" fill="none" stroke="{lead}" stroke-width="2"/>
      <circle cx="55" cy="42" r="15" fill="none" stroke="{lead}" stroke-width="1.5"/>
    </svg>
    """


def _icon(name: str) -> str:
    paths = {
        "home": '<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
        "demo": '<path d="m8 5 11 7-11 7z"/>',
        "phone": '<rect x="6" y="2.5" width="12" height="19" rx="2.5"/><path d="M10 18.5h4"/>',
        "booth": '<path d="M3 21V8l9-5 9 5v13"/><path d="M7 21v-8h10v8M9 9h.01M15 9h.01"/>',
        "radar": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><path d="m12 12 6-6"/>',
        "spark": '<path d="m12 2 1.8 6.2L20 10l-6.2 1.8L12 18l-1.8-6.2L4 10l6.2-1.8z"/><path d="m19 14 1 3 3 1-3 1-1 3-1-3-3-1 3-1z"/>',
        "team": '<circle cx="9" cy="8" r="3"/><circle cx="17" cy="9" r="2.5"/><path d="M3 20c0-3 2.5-5 6-5s6 2 6 5M15 15c3.5-.3 6 1.5 6 4"/>',
        "chat": '<path d="M4 5h16v12H9l-5 4z"/><path d="M8 9h8M8 13h5"/>',
        "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
        "database": '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v7c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12v7c0 1.7 3.6 3 8 3s8-1.3 8-3v-7"/>',
        "lock": '<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2"/>',
        "check": '<path d="m4 12 5 5L20 6"/>',
        "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l4 2"/>',
    }
    drawing = paths.get(name, paths["spark"])
    return (
        '<span class="ib-icon" aria-hidden="true">'
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        f"{drawing}</svg></span>"
    )


def _install_styles(*, dark_mode: bool = False) -> None:
    st.markdown(
        """
        <style>
        :root { color-scheme: light; }
        .stApp { background: #FFFBEA; color: #2B2B2B; }
        [data-testid="stHeader"] { background: rgba(255,251,234,.94); }
        [data-testid="stSidebar"] { background: #F3EAD8; width:17rem !important; min-width:17rem !important; }
        [data-testid="stSidebar"] * { color: #2B2B2B; }
        [data-testid="stMainBlockContainer"] { max-width:1440px; padding:1rem clamp(1.1rem,2.6vw,2.4rem) 3rem !important; }
        [data-testid="stMainBlockContainer"] > div[data-testid="stVerticalBlock"] { gap:.7rem; }
        html { scroll-behavior:smooth; scroll-padding-top:94px; }
        section[id], div[id] { scroll-margin-top:94px; }
        h1, h2, h3, h4 { color: #0B1F3A; font-family: ui-rounded, "Arial Rounded MT Bold", system-ui, sans-serif; font-weight: 850; letter-spacing: -.035em; }
        h1 { font-size:clamp(2.25rem,4.2vw,3.7rem); line-height:1.08; }
        h2 { font-size:clamp(1.7rem,3vw,2.45rem); line-height:1.14; }
        h3 { font-size:1.35rem; line-height:1.22; }
        p, li, label { line-height: 1.55; }
        .ib-brand { display:flex; align-items:center; gap:12px; color:#0B1F3A; font-weight:900; font-size:1.1rem; }
        .ib-icon { display:inline-grid; place-items:center; width:30px; height:30px; flex:0 0 30px; color:#2440FF; background:transparent; border:0; box-shadow:none; vertical-align:middle; }
        .ib-icon svg { width:22px; height:22px; }
        .ib-nav-button { display:flex; align-items:center; gap:9px; }
        .ib-nav-button .ib-icon { width:30px; height:30px; flex-basis:30px; border-radius:10px; box-shadow:none; border-width:1.5px; }
        .ib-integrations { margin-top:12px; padding:12px 12px; border:1px solid #D5C8B2; border-radius:14px; background:#FFFBEA; }
        .ib-integrations-title { margin:0 0 10px; color:#0B1F3A; font-size:.9rem; font-weight:850; line-height:1.3; }
        .ib-integration-row { display:grid; grid-template-columns:22px minmax(0,1fr); align-items:start; gap:8px; padding:8px 0; border-top:1px solid #E8DECE; }
        .ib-integration-row:first-of-type { border-top:0; }
        .ib-integration-row .ib-icon { width:22px; height:22px; flex-basis:22px; color:#2440FF; }
        .ib-integration-row .ib-icon svg { width:19px; height:19px; }
        .ib-integration-name { color:#0B1F3A; font-size:.83rem; font-weight:800; line-height:1.25; }
        .ib-integration-status { color:#536176; font-size:.72rem; line-height:1.35; margin-top:3px; overflow-wrap:anywhere; }
        .ib-feature-heading { display:flex; align-items:center; gap:12px; margin-bottom:10px; }
        .ib-step-heading { display:flex; align-items:center; gap:10px; }
        .ib-setup-row { display:grid; grid-template-columns:30px minmax(0,1fr); align-items:center; gap:10px; padding:10px 14px; margin:5px 0; background:#FFFBEA; border:1px solid #D8E9DE; border-left:5px solid #00C896; border-radius:14px; }
        .ib-setup-row .ib-icon { color:#008B70; }
        .ib-setup-row > div:last-child { display:grid; grid-template-columns:minmax(145px,.8fr) minmax(0,1.2fr); align-items:center; gap:2px 12px; }
        .ib-setup-row .ib-label { grid-column:1 / -1; }
        .ib-setup-row h3 { font-size:1rem; line-height:1.22; margin:0; }
        .ib-setup-row p { font-size:.9rem; line-height:1.35; margin:0; color:#425166; }
        .ib-home-cta { min-height:100%; padding:18px; border:2px solid #0B1F3A; border-radius:18px; background:#FFFBEA; }
        .ib-home-cta h3 { margin:0 0 6px; font-size:1.15rem; }
        .ib-home-cta p { min-height:3em; margin:0 0 12px; color:#425166; font-size:.92rem; }
        .ib-account-actions { display:flex; justify-content:flex-end; gap:10px; margin:4px 0 10px; }
        .ib-coming-soon { max-width:680px; margin:4vh auto; }
        .ib-site-nav { position:sticky; top:0; z-index:20; display:flex; align-items:center; justify-content:space-between; gap:14px; padding:9px 16px; margin:0 0 18px; background:rgba(255,251,234,.97); border-bottom:2px solid #0B1F3A; }
        .ib-site-nav a { color:#2440FF; font-weight:800; text-decoration:underline; text-underline-offset:3px; }
        .ib-site-nav .ib-brand { color:#0B1F3A; text-decoration:none; flex-shrink:0; }
        .ib-site-links { display:flex; flex-wrap:wrap; justify-content:center; gap:12px; }
        .ib-site-nav .ib-nav-demo { color:#0B1F3A; background:#FFE500; border:2px solid #0B1F3A; border-radius:8px; padding:10px 12px; box-shadow:4px 4px 0 #0B1F3A; text-decoration:none; white-space:nowrap; }
        .ib-hero { background:#FFE500; color:#0B1F3A; border-radius:24px; padding:clamp(24px,5vw,58px); border:3px solid #0B1F3A; box-shadow:10px 10px 0 #0B1F3A; margin:8px 8px 28px 0; overflow:hidden; }
        .ib-hero h1 { font-size:clamp(2.2rem,5vw,4.7rem); line-height:1.02; margin:.5rem 0 1rem; max-width:850px; }
        .ib-label { text-transform:uppercase; letter-spacing:.1em; font-weight:850; font-size:.76rem; color:var(--accent,#2440FF); }
        .ib-card { background:#FFFBEA; border:2px solid #0B1F3A; border-radius:20px; padding:clamp(16px,1.7vw,22px); box-shadow:4px 4px 0 #0B1F3A; height:100%; }
        .ib-card h3 { font-size:clamp(1.12rem,1.45vw,1.4rem); line-height:1.2; letter-spacing:-.02em; margin:.55rem 0 .65rem; overflow-wrap:normal; }
        .ib-card p { font-size:.96rem; line-height:1.5; }
        .ib-panel { background:#F3EAD8; border-radius:20px; border:2px solid #0B1F3A; padding:clamp(16px,1.7vw,22px); }
        .ib-dark { background:#0B1F3A; color:#FFFBEA; border-radius:20px; padding:22px; }
        .ib-dark h2, .ib-dark h3, .ib-dark p { color:#FFFBEA; }
        .ib-honesty { background:#FFFBEA; color:#0B1F3A; padding:12px 18px; margin:14px 0; border:2px solid #0B1F3A; border-radius:14px; font-weight:850; text-align:center; }
        .ib-chip { display:inline-block; border-radius:999px; padding:5px 11px; background:#E7E9FF; color:#2440FF; font-size:.8rem; font-weight:800; }
        .ib-hot { display:inline-block; border-radius:999px; padding:5px 11px; background:#FFE500; color:#0B1F3A; font-size:.8rem; font-weight:900; }
        .ib-phone { max-width:410px; margin:auto; padding:18px; border:3px solid #0B1F3A; border-radius:34px; background:#FFFBEA; box-shadow:8px 8px 0 #2440FF; }
        .ib-phone-notch { width:92px; height:9px; border-radius:99px; background:#0B1F3A; margin:0 auto 16px; }
        .ib-mini { border:2px solid #0B1F3A; border-radius:16px; padding:14px; background:#FFFBEA; margin:10px 0; }
        .ib-collage { position:relative; min-height:220px; display:grid; place-items:center; }
        .ib-phone-pair { position:relative; min-height:330px; display:flex; justify-content:center; align-items:center; gap:14px; padding:16px; background-image:radial-gradient(#0B1F3A 1px,transparent 1px); background-size:22px 22px; }
        .ib-mock-phone { width:min(43%,205px); min-height:260px; padding:14px; border:3px solid #0B1F3A; border-radius:26px; background:#FFFBEA; box-shadow:7px 7px 0 #0B1F3A; }
        .ib-mock-phone:last-child { transform:translateY(34px) rotate(3deg); }
        .ib-mock-phone:first-child { transform:translateY(-16px) rotate(-3deg); }
        .ib-mock-notch { width:55px; height:7px; border-radius:10px; background:#0B1F3A; margin:0 auto 13px; }
        .ib-mock-avatar { width:42px; height:42px; border-radius:50%; display:grid; place-items:center; background:#F3EAD8; color:#0B1F3A; font-weight:900; }
        .ib-mock-pill { display:inline-block; background:#FFE500; color:#0B1F3A; border-radius:99px; padding:4px 9px; font-weight:900; font-size:.72rem; }
        .ib-mock-stop { border:2px solid #FF4A00; border-radius:14px; padding:10px; margin-top:12px; box-shadow:3px 3px 0 #FF4A00; }
        .ib-brand-kit { padding:22px; background:#F3EAD8; border:2px solid #0B1F3A; border-radius:22px; box-shadow:5px 5px 0 #0B1F3A; height:100%; }
        .ib-swatch { min-height:76px; border:2px solid #0B1F3A; border-radius:14px; padding:10px; font-weight:800; }
        .ib-store { display:inline-block; min-width:190px; background:#FFFBEA; border:2px solid #0B1F3A; border-radius:12px; padding:12px 16px; margin:6px 10px 6px 0; font-weight:850; box-shadow:4px 4px 0 #0B1F3A; }
        .ib-social-card { aspect-ratio:1200/630; background:#FFE500; color:#0B1F3A; border:3px solid #0B1F3A; border-radius:22px; padding:clamp(16px,3vw,30px); box-shadow:7px 7px 0 #0B1F3A; display:flex; flex-direction:column; justify-content:space-between; }
        .ib-social-card h3 { font-size:clamp(1rem,2vw,1.8rem); margin:8px 0; }
        .ib-architecture-step { border:1px solid #E8CFE0; border-left:6px solid var(--accent,#2440FF); padding:20px 22px; margin:14px 0; background:#FFF8FC; border-radius:14px; box-shadow:3px 3px 0 #F2C8E2; }
        .ib-architecture-step h3 { margin:.1rem 0 .55rem; }
        .ib-architecture-step p { margin:.25rem 0; }
        .ib-badge-large { width:150px; height:180px; border-radius:30px; border:5px solid #0B1F3A; background:#0B1F3A; box-shadow:12px 12px 0 #2440FF; display:grid; place-items:center; }
        .ib-sticky { position:absolute; right:1%; top:5%; width:145px; padding:13px; background:#FFFBEA; border:2px solid #0B1F3A; border-radius:12px; box-shadow:4px 4px 0 #0B1F3A; transform:rotate(4deg); font-weight:800; }
        .ib-lead-float { position:absolute; left:0; bottom:4%; background:#FFFBEA; border:2px solid #0B1F3A; border-radius:16px; padding:12px; box-shadow:4px 4px 0 #0B1F3A; }
        .ib-stop-float { position:absolute; right:0; bottom:0; background:#FFFBEA; border:2px solid #FF4A00; border-radius:16px; padding:12px; box-shadow:4px 4px 0 #FF4A00; }
        .ib-section { border-radius:24px; padding:clamp(22px,3.4vw,40px); margin:18px 0; }
        .ib-section-cream { background:#FFFBEA; }
        .ib-section-beige { background:#F3EAD8; }
        .ib-section-teal { background:#00CF9E; color:#0B1F3A; }
        .ib-section-teal h2, .ib-section-teal h3 { color:#0B1F3A; }
        .ib-divider { background:#0B1F3A; color:#FFFBEA; padding:18px 24px; border-radius:14px; margin:24px 0; font-weight:800; }
        .ib-feature { min-height:155px; }
        .ib-proof { text-align:center; border-radius:18px; padding:18px; border:2px solid #0B1F3A; box-shadow:4px 4px 0 #0B1F3A; background:#FFFBEA; }
        .ib-proof strong { display:block; font-size:2rem; color:#0B1F3A; }
        .ib-privacy { border-left:7px solid #FF8AD6; padding:12px 16px; background:#FFF0FA; border-radius:8px 16px 16px 8px; }
        .ib-anim { animation: ib-pop .45s ease-out both; }
        .ib-radar { width:12px; height:12px; border:3px solid #FFE500; border-radius:50%; box-shadow:0 0 0 6px rgba(255,229,0,.22); animation:ib-ring .7s ease-out 1 both; margin:8px; }
        @keyframes ib-pop { from { opacity:.3; transform:scale(.92); } to { opacity:1; transform:scale(1); } }
        @keyframes ib-ring { 0% { box-shadow:0 0 0 2px rgba(255,229,0,.65); } 100% { box-shadow:0 0 0 16px rgba(255,229,0,0); } }
        @keyframes ib-fan { 0% { opacity:.3; transform:translate(0,0) scale(.3); } 100% { opacity:1; transform:translate(0,0) scale(1); } }
        @supports (animation-timeline: view()) {
          .ib-collage { view-timeline-name:--hero-scroll; view-timeline-axis:block; }
          .ib-sticky, .ib-lead-float, .ib-stop-float { animation:ib-fan 1s ease-out both; animation-timeline:--hero-scroll; animation-range:entry 0% cover 45%; }
        }
        @media (prefers-reduced-motion: reduce) { *, *::before, *::after { scroll-behavior:auto !important; animation-duration:.01ms !important; animation-iteration-count:1 !important; } }
        div[data-testid="stButton"] > button { min-height:54px; border-radius:10px; border:2px solid #0B1F3A; color:#0B1F3A; background:#FFFBEA; font-weight:850; box-shadow:3px 3px 0 #0B1F3A; }
        div[data-testid="stButton"] > button[kind="primary"] { background:#FFE500; }
        div[data-testid="stButton"] > button:hover { border-color:#2440FF; color:#0B1F3A; }
        [data-testid="stMetric"] { background:#FFFBEA; border:2px solid #0B1F3A; border-radius:16px; box-shadow:4px 4px 0 #0B1F3A; padding:12px; }
        [data-testid="stMetricValue"] { color:#0B1F3A; }
        @media (max-width: 640px) {
          [data-testid="stSidebar"] { width:16rem !important; min-width:16rem !important; }
          [data-testid="stMainBlockContainer"] { padding:.75rem .85rem 2.5rem !important; }
          .ib-setup-row > div:last-child { grid-template-columns:minmax(0,1fr); }
          .ib-setup-row .ib-label { grid-column:auto; }
          .ib-home-cta p { min-height:0; }
          .ib-site-nav { flex-wrap:wrap; }
          .ib-site-links { order:3; width:100%; justify-content:flex-start; gap:8px 14px; }
          .ib-site-links a { font-size:.88rem; }
          .ib-site-nav .ib-nav-demo { margin-left:auto; }
          .ib-phone-pair { min-height:280px; gap:8px; padding:8px; }
          .ib-mock-phone { min-height:230px; padding:10px; }
          .ib-mock-phone:last-child { transform:translateY(22px) rotate(2deg); }
          .ib-mock-phone:first-child { transform:translateY(-10px) rotate(-2deg); }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    if dark_mode:
        st.markdown(
            """
            <style>
            :root { color-scheme:dark; }
            body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"],
            [data-testid="stHeader"], [data-testid="stSidebar"] {
              background-color:#101827 !important;
              color:#F3F4F6 !important;
            }
            [data-testid="stSidebar"] { background-color:#172235 !important; }
            [data-testid="stMainBlockContainer"] { background:#101827 !important; }
            .stApp p, .stApp li, .stApp label, .stApp span, .stApp div,
            .stApp small, .stApp strong, .stApp h1, .stApp h2, .stApp h3, .stApp h4 {
              color:#F3F4F6;
            }
            [data-testid="stSidebar"] * { color:#F3F4F6 !important; }
            .ib-site-nav { background:#172235 !important; border-color:#536780 !important; }
            .ib-site-nav a, .ib-site-nav .ib-brand { color:#A9BFFF !important; }
            .ib-site-nav .ib-nav-demo { background:#FFE500 !important; color:#0B1F3A !important; }
            .ib-integrations, .ib-home-cta { background:#202E42 !important; border-color:#536780 !important; }
            .ib-setup-row { background:#202E42 !important; border-color:#40516A !important; border-left-color:#66E6C5 !important; }
            .ib-setup-row h3, .ib-setup-row p { color:#F3F4F6 !important; }
            .ib-setup-row .ib-icon { color:#66E6C5 !important; }
            .ib-integrations-title, .ib-integration-name { color:#F3F4F6 !important; }
            .ib-integration-status { color:#C4D0DF !important; }
            .ib-integration-row { border-color:#40516A !important; }
            .ib-integration-row .ib-icon { background:transparent !important; border:0 !important; box-shadow:none !important; color:#A9BFFF !important; }
            .ib-icon { color:#A9BFFF !important; background:transparent !important; border:0 !important; box-shadow:none !important; }
            [data-testid="stSidebar"] button[kind="primary"] .ib-icon { color:#0B1F3A !important; }
            .ib-feature-heading .ib-icon { color:#C6D2FF !important; background:transparent !important; }
            .ib-section-teal .ib-icon { color:#D7FFF2 !important; background:#15554D !important; }
            .ib-section-teal .ib-label { color:#D7FFF2 !important; }
            [data-testid="stSidebar"] button[kind="primary"],
            [data-testid="stSidebar"] button[kind="primary"] * {
              background:#FFE500 !important; color:#0B1F3A !important;
            }
            .ib-hero, .ib-social-card { background:#FFE500 !important; color:#0B1F3A !important; }
            .ib-hero *, .ib-social-card *, .ib-hot, .ib-mock-pill {
              color:#0B1F3A !important;
            }
            .ib-section-cream, .ib-section-beige {
              background:#172235 !important; color:#F3F4F6 !important;
            }
            .ib-section-teal { background:#103D38 !important; color:#D7FFF2 !important; }
            .ib-section-teal h2, .ib-section-teal h3 { color:#D7FFF2 !important; }
            .ib-card, .ib-panel, .ib-brand-kit, .ib-phone, .ib-mock-phone, .ib-home-cta,
            .ib-architecture-step, .ib-proof, .ib-privacy, .ib-mini, .ib-store,
            [data-testid="stMetric"] {
              background:#202E42 !important; color:#F3F4F6 !important;
              border-color:#536780 !important;
            }
            .ib-architecture-step { border-left-color:#FFACE2 !important; box-shadow:3px 3px 0 #5C3B58 !important; }
            .ib-card *, .ib-panel *, .ib-brand-kit *, .ib-phone *, .ib-mock-phone *, .ib-home-cta *,
            .ib-architecture-step *, .ib-proof *, .ib-privacy *, .ib-mini *, .ib-store *,
            [data-testid="stMetric"] * { color:#F3F4F6 !important; }
            .ib-label { color:#A9BFFF !important; }
            .ib-label[style*="#2440FF"] { color:#A9BFFF !important; }
            .ib-label[style*="#FF4A00"] { color:#FF9A75 !important; }
            .ib-label[style*="#00C896"], .ib-label[style*="#00CF9E"] { color:#66E6C5 !important; }
            .ib-label[style*="#FF8AD6"] { color:#FFACE2 !important; }
            .ib-label[style*="#FFE500"] { color:#FFE500 !important; }
            .ib-chip { background:#2C3D58 !important; color:#C6D2FF !important; }
            .ib-hot, .ib-mock-pill { background:#FFE500 !important; color:#0B1F3A !important; }
            .ib-divider, .ib-dark, footer.ib-dark {
              background:#0B1F3A !important; color:#F3F4F6 !important;
            }
            .ib-dark *, footer.ib-dark * { color:#F3F4F6 !important; }
            .ib-honesty { background:#202E42 !important; color:#F3F4F6 !important; }
            .ib-sticky, .ib-lead-float, .ib-stop-float {
              background:#202E42 !important; color:#F3F4F6 !important;
            }
            .ib-mock-avatar { background:#34445D !important; color:#F3F4F6 !important; }
            .ib-mock-stop { border-color:#FF8A65 !important; }
            .ib-radar { border-color:#FFE500 !important; }
            div[data-testid="stButton"] > button {
              background:#202E42; color:#F3F4F6; border-color:#7185A3;
            }
            div[data-testid="stButton"] > button[kind="primary"] {
              background:#FFE500; color:#0B1F3A;
            }
            [data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea,
            [data-testid="stSelectbox"] div[data-baseweb="select"] {
              background:#202E42 !important; color:#F3F4F6 !important;
            }
            [data-testid="stAlert"] { background:#202E42 !important; color:#F3F4F6 !important; }
            </style>
            """,
            unsafe_allow_html=True,
        )


def _render_brand() -> None:
    st.markdown(
        f'<div class="ib-brand">{_badge_svg(46)}<span>Inference Badge</span></div>',
        unsafe_allow_html=True,
    )


def _render_website() -> None:
    st.markdown(
        f"""
        <nav class="ib-site-nav" aria-label="Page sections">
          <a href="#hero" class="ib-brand">{_badge_svg(42)}<span>Inference Badge</span></a>
          <div class="ib-site-links">
        <a href="#how-it-works">How it works</a>
        <a href="#for-sales-teams">For sales teams</a>
        <a href="#for-organisers">For organisers</a>
        <a href="#privacy">Privacy</a>
        <a href="#faq">FAQ</a>
          </div>
          <a class="ib-nav-demo" href="#try-demo">▶ Try the Demo</a>
        </nav>
        <section id="hero" class="ib-hero">
          <div class="ib-collage">
        <div class="ib-phone-pair" aria-label="Paired demo phone screens">
          <div class="ib-mock-phone">
            <div class="ib-mock-notch"></div>
            <span class="ib-mock-pill">HOT LEAD · DEMO</span>
            <div class="ib-mock-avatar" style="margin-top:12px">S</div>
            <strong>Sarah Demo</strong><br><small>Head of AI Platform</small>
            <hr><strong>3 things to say</strong>
            <p><small>Ask about her AI platform plans.</small></p>
            <div class="ib-mock-pill">CONNECT · DEMO</div>
              </div>
          <div class="ib-mock-phone">
            <div class="ib-mock-notch"></div>
            <span class="ib-mock-pill">TEAM CHECK</span>
            <div class="ib-mock-stop">
              <strong>Stand down</strong>
              <p><small>Alex is already talking to Sarah.</small></p>
            </div>
            <p><small>Find another lead or come back later.</small></p>
            <div class="ib-mock-avatar">A</div>
            <small>Attendee choice stays visible.</small>
          </div>
        </div>
        <div class="ib-sticky">3 THINGS<br>TO SAY<br><small>Ready for this lead</small></div>
        <div class="ib-lead-float">HOT · Sarah<br><small>Demo lead card</small></div>
        <div class="ib-stop-float">Stand down<br><small>Demo stop card</small></div>
          </div>
          <div class="ib-label" style="color:#0B1F3A">A digital badge plugin + phone app for conferences</div>
          <h1>Find your leads. Never pitch the same person twice.</h1>
          <p style="font-size:1.15rem;max-width:760px">The lead list comes from conference sign-ups. When an opted-in attendee is nearby, the badge checks your team’s shared memory and gives you useful words to connect.</p>
          <p><strong>Prototype preview: proximity is simulated. Demo people are not real attendees.</strong></p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    sales_cta, organiser_cta = st.columns(2, gap="large")
    with sales_cta:
        st.markdown(
            '<div id="try-demo" class="ib-home-cta"><div class="ib-label">FOR SALES TEAMS</div>'
            '<h3>See the product in action</h3>'
            '<p>Follow a 90-second story across the phone and booth dashboard.</p></div>',
            unsafe_allow_html=True,
        )
        st.button(
            "Start the 90-second business demo",
            type="primary",
            use_container_width=True,
            on_click=_go_to_demo,
        )
    with organiser_cta:
        st.markdown(
            '<div class="ib-home-cta"><div class="ib-label" style="--accent:#008B70">FOR CONFERENCE ORGANISERS</div>'
            '<h3>Try the setup experience</h3>'
            '<p>Configure a sample sign-up and see the attendee opt-in preview.</p></div>',
            unsafe_allow_html=True,
        )
        st.button(
            "Try conference setup simulation",
            type="primary",
            on_click=_go_to_setup,
            use_container_width=True,
        )
    st.button(
        "Experience a full conference day · 3 minutes",
        on_click=_go_to_conference_day,
        use_container_width=True,
        help="Guided simulation for conference organisers, attendees, and exhibitor teams.",
    )
    account_login, account_signup = st.columns(2)
    account_login.button(
        "Log in · Coming soon",
        on_click=_go_to_login,
        use_container_width=True,
    )
    account_signup.button(
        "Create account · Coming soon",
        on_click=_go_to_signup,
        use_container_width=True,
    )
    st.markdown(
        '<div class="ib-honesty">Built at the Patch the Conference Hackathon · FalkorDB · Bright Data · OpenAI</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <section id="problem" class="ib-section ib-section-beige">
          <div class="ib-label" style="--accent:#FF4A00">The problem</div>
          <h2>Busy floors make good teams repeat themselves</h2>
          <p>Sales teams meet potential customers at a busy conference. Without shared context, two teammates can pitch the same person, useful facts get lost, and lead lists go stale.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    problem_cards = st.columns(3)
    for col, title, body in zip(
        problem_cards,
        ("Double talks", "Lost facts", "Old lists"),
        (
        "A teammate may already be in the conversation.",
        "The reason for a meeting can disappear between chats.",
        "A sign-up lead list can be hard to use on a busy floor.",
        ),
    ):
        col.markdown(
        f'<div class="ib-card" style="border-color:#FF4A00;box-shadow:5px 5px 0 #FF4A00"><h3 class="ib-feature-heading">{_icon("team" if title == "Double talks" else "chat" if title == "Lost facts" else "database")}<span>{title}</span></h3><p>{body}</p></div>',
        unsafe_allow_html=True,
        )

    st.markdown(
        """
        <section id="how-it-works" class="ib-section ib-section-cream">
          <div class="ib-label" style="--accent:#2440FF">How it works</div>
          <h2>From sign-up to a better first conversation</h2>
          <div class="ib-divider">SAY YES AT SIGN-UP → BADGE SENSES + TEAM CHECKS → RIGHT WORDS, CONNECT, CONVERT</div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    steps = st.columns(3)
    for col, number, title, body in zip(
        steps,
        ("01", "02", "03"),
        ("Say yes at sign-up", "Badge senses + team checks", "Right words, connect, convert"),
        (
        "The conference sign-up list supplies the lead pool. Attendees control sharing on their phone.",
        "The badge looks for an opted-in lead nearby and checks shared team memory.",
        "See three practical prompts, then decide what to do.",
        ),
    ):
        col.markdown(
        f'<div class="ib-card" style="border-color:#2440FF;box-shadow:5px 5px 0 #2440FF"><div class="ib-label" style="--accent:#2440FF">{number}</div><h3 class="ib-step-heading">{_icon(("lock", "radar", "chat")[int(number) - 1])}<span>{title}</span></h3><p>{body}</p></div>',
        unsafe_allow_html=True,
        )
    with st.expander("The four checks behind the demo"):
        flow = st.columns(4)
        for col, text in zip(
        flow,
        ("BADGE SENSES\n(simulated)", "SIGN-UP LIST\nCHECKED", "TEAM MEMORY\nCHECKED", "PROMPT\nWRITTEN"),
        ):
            col.markdown(f'<div class="ib-proof">{text.replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)
        st.caption("In this prototype, proximity is simulated. The demo does not read a real attendee sign-up database.")
    sponsor_cards = st.columns(3)
    for col, sponsor, accent, icon_name, title, body in zip(
        sponsor_cards,
        ("FALKORDB", "BRIGHT DATA", "OPENAI"),
        ("#2440FF", "#FF4A00", "#00C896"),
        ("database", "globe", "spark"),
        ("Shared team memory", "Fresh public facts", "Short conversation notes"),
        (
        "The booth dashboard can read the local graph when connected.",
        "Optional, user-triggered company lookup. Sample facts remain labeled.",
        "Optional strategy brief generation with a deterministic fallback.",
        ),
    ):
        col.markdown(
        f'<div class="ib-card" style="border-color:{accent};box-shadow:5px 5px 0 {accent}"><div class="ib-label" style="color:{accent}">{sponsor} · HACKATHON TRACK</div><h3 class="ib-feature-heading">{_icon(icon_name)}<span>{title}</span></h3><p>{body}</p></div>',
        unsafe_allow_html=True,
        )
    st.markdown(
        '<p><a href="#try-demo" style="color:#2440FF;font-weight:800;text-decoration:underline">👉 See it live in the demo</a></p>',
        unsafe_allow_html=True,
    )

    st.markdown('<section id="features" class="ib-section ib-section-cream"><div class="ib-label" style="--accent:#2440FF">Features · prototype concepts</div><h2>Small moments, coordinated</h2></section>', unsafe_allow_html=True)
    feature_cols = st.columns(3)
    for col, title, body, icon_name in zip(
        feature_cols * 2,
        (
        "Lead Sense", "Right Prompts", "No Double Talks",
        "Fresh Facts", "One Team Memory", "Follow-up Ready",
        ),
        (
        "A demo badge check-in points out an opted-in lead.",
        "Three prompts help start a relevant conversation.",
        "A stop card warns when a teammate has the lead covered.",
        "Optional public company lookup adds context.",
        "The booth view can share team context through FalkorDB.",
        "Review a follow-up draft after the talk; it is never sent.",
        ),
        ("radar", "chat", "team", "globe", "database", "check"),
    ):
        col.markdown(
        f'<div class="ib-card ib-feature" style="border-color:#2440FF;box-shadow:5px 5px 0 #2440FF"><h3 class="ib-feature-heading">{_icon(icon_name)}<span>{title}</span></h3><p>{body}</p></div>',
        unsafe_allow_html=True,
        )

    st.markdown('<section id="story" class="ib-section ib-section-beige"><div class="ib-label" style="--accent:#FF4A00">The story in three panels</div><h2>Alex spots Sarah. Sam gets the stop. The team follows up.</h2></section>', unsafe_allow_html=True)
    story = st.columns(3)
    for col, title, body, accent, icon_name in zip(
        story,
        ("Alex spots Sarah", "Sam gets the stop", "Sarah is covered"),
        (
        "A hot demo lead and three prompts appear on Alex’s phone.",
        "Alex is already talking to Sarah. The team check says to stand down.",
        "Alex records an outcome. A follow-up draft is ready, not sent.",
        ),
        ("#FF4A00", "#2440FF", "#00C896"),
        ("radar", "team", "check"),
    ):
        col.markdown(
        f'<div class="ib-card" style="border-color:{accent};box-shadow:5px 5px 0 {accent}"><div class="ib-label" style="color:{accent}">DEMO STORY</div><h3 class="ib-feature-heading">{_icon(icon_name)}<span>{title}</span></h3><p>{body}</p></div>',
        unsafe_allow_html=True,
        )
    st.button(
        "▶ Try this story yourself",
        type="primary",
        use_container_width=True,
        on_click=_go_to_demo,
    )

    st.markdown(
        '<section id="for-sales-teams" class="ib-section ib-section-cream"><div class="ib-label" style="--accent:#FFE500">For sales teams</div><h2>Your whole team. One lead list. Zero double pitches.</h2><p>Find leads, connect with the right context, and prepare a useful follow-up.</p></section>',
        unsafe_allow_html=True,
    )
    sales_benefits = st.columns(3)
    for col, title, body, icon_name in zip(
        sales_benefits,
        ("Find leads", "Connect better", "Convert"),
        (
        "See a demo score and why Sarah is a match.",
        "Use three short, person-specific conversation prompts.",
        "Record an outcome and review a draft follow-up.",
        ),
        ("radar", "chat", "check"),
    ):
        col.markdown(
        f'<div class="ib-card" style="border-color:#FFE500;box-shadow:5px 5px 0 #FFE500"><h3 class="ib-feature-heading">{_icon(icon_name)}<span>{title}</span></h3><p>{body}</p></div>',
        unsafe_allow_html=True,
        )
    st.markdown('<div class="ib-dark"><h3>Proof numbers · demo results</h3><p>Illustrative demo counters only — not customer or production metrics.</p></div>', unsafe_allow_html=True)
    proof = st.columns(3)
    for col, number, label in zip(proof, ("1", "1", "1"), ("Double talks stopped", "Lead covered", "Follow-up ready")):
        col.markdown(f'<div class="ib-proof"><strong>{number}</strong>{label}<br><small>Demo result</small></div>', unsafe_allow_html=True)
    st.markdown('<div class="ib-panel"><h3>A day on the floor · demo story</h3><p>Morning list → First hello → Stop warning → Join the conversation → Follow-ups to review</p><p>Each moment above is simulated in the prototype.</p></div>', unsafe_allow_html=True)
    st.button("▶ Try the Demo", type="primary", on_click=_go_to_demo, key="sales_demo_cta")

    st.markdown(
        '<section id="for-organisers" class="ib-section ib-section-teal"><div class="ib-label" style="color:#0B1F3A">For conference organisers · the plugin</div><h2>Add a smart badge to the conference you already run.</h2><p>A future plugin concept for your sign-up flow and event app — with attendee-controlled sharing.</p></section>',
        unsafe_allow_html=True,
    )
    plugin_steps = st.columns(3)
    for col, title, body, icon_name in zip(
        plugin_steps,
        ("Add to sign-up", "Attendees choose", "See floor insight"),
        (
        "Connect the conference lead list to the badge experience.",
        "Attendees set their sharing preference on their own phone.",
        "A team dashboard helps organisers and sales teams see coverage.",
        ),
        ("database", "lock", "booth"),
    ):
        col.markdown(
        f'<div class="ib-card" style="border-color:#00C896;box-shadow:5px 5px 0 #00C896"><h3 class="ib-feature-heading">{_icon(icon_name)}<span>{title}</span></h3><p>{body}</p></div>',
        unsafe_allow_html=True,
        )
    st.markdown('<div class="ib-divider">WORKS WITH YOUR CONFERENCE APP · CONCEPT ONLY</div>', unsafe_allow_html=True)
    organiser_benefits = st.columns(3)
    for col, title, body in zip(
        organiser_benefits,
        ("Privacy by design", "Live floor view", "Better sponsor conversations"),
        (
        "The product is designed around attendee choice.",
        "Team coverage is visible in a booth dashboard.",
        "Sales teams can avoid repeating the same pitch.",
        ),
    ):
        col.markdown(f'<div class="ib-card"><h3>{title}</h3><p>{body}</p></div>', unsafe_allow_html=True)
    attendee_views = st.columns(2)
    attendee_views[0].markdown('<div class="ib-phone"><div class="ib-phone-notch"></div><h3>Choose your setting · Demo</h3><p>Location sharing <strong>ON / OFF</strong></p><p>Pause sharing · Delete my data</p></div>', unsafe_allow_html=True)
    attendee_views[1].markdown('<div class="ib-phone"><div class="ib-phone-notch"></div><h3>Private mode · Demo</h3><p>Attendee (private)</p><p>No name or photo on this preview.</p></div>', unsafe_allow_html=True)
    st.button(
        "Preview conference setup",
        on_click=_go_to_setup,
        help="A simulated organizer walkthrough; no conference data is connected.",
    )
    st.markdown('<p><a href="#get-the-app" style="color:#2440FF;font-weight:800;text-decoration:underline">👉 See the launch information</a></p>', unsafe_allow_html=True)

    st.markdown('<section id="privacy" class="ib-section ib-section-cream"><div class="ib-privacy"><div class="ib-label" style="--accent:#FF8AD6">Privacy · product commitments, not implemented controls</div><h2>Clear choices, in plain words</h2></div></section>', unsafe_allow_html=True)
    privacy_promises = (
        ("Permission comes first", "The product is designed to ask at conference sign-up; permission is never assumed."),
        ("Your choice, on your phone", "The attendee controls sharing and can pause or change it."),
        ("Private mode", "The product concept uses a secret code instead of a private attendee’s name."),
        ("What this prototype stores", "Demo interactions use browser-session state. If you explicitly opt in to early access, your email and consent are stored in the configured FalkorDB backend."),
        ("What the product should never do", "Sell attendee data, track people outside the conference, or share without permission."),
        ("Delete my data", "A real delete control is not implemented here; the phone screen is a preview only."),
    )
    for title, body in privacy_promises:
        icon_name = (
        "lock" if title == "Permission comes first"
        else "phone" if title == "Your choice, on your phone"
        else "team" if title == "Private mode"
        else "database" if title == "What this prototype stores"
        else "check" if title == "What the product should never do"
        else "clock"
        )
        st.markdown(
        f'<div class="ib-architecture-step" style="--accent:#FF8AD6"><h3 class="ib-feature-heading">{_icon(icon_name)}<span>{title}</span></h3><p>{body}</p></div>',
        unsafe_allow_html=True,
        )

    st.markdown('<section id="faq" class="ib-section ib-section-cream"><div class="ib-label" style="--accent:#2440FF">FAQ</div><h2>Good questions, plain answers</h2></section>', unsafe_allow_html=True)
    faqs = (
        ("Where does the lead list come from?", "The intended source is the conference sign-up database. This prototype uses clearly labeled demo people."),
        ("Did attendees agree to this?", "The product is designed for permission at sign-up and attendee-controlled sharing. This prototype does not collect real attendee consent."),
        ("What if someone turns sharing off?", "The demo shows “Attendee (private)” and an example code instead of a name."),
        ("Do I need new hardware?", "The product concept uses a phone and digital badge. This prototype simulates proximity and has no real sensing hardware."),
        ("When can I get it?", "The app is coming soon. You can optionally join the early-access email list below; your address is stored in the configured FalkorDB backend and is not emailed to anyone."),
    )
    for question, answer in faqs:
        st.markdown(f'<div class="ib-panel"><h3>{question}</h3><p>{answer}</p></div>', unsafe_allow_html=True)
    st.markdown('<p>Still curious? Contact details are not configured yet. <a href="#hero" style="color:#2440FF;font-weight:800;text-decoration:underline">👉 Try the demo</a></p>', unsafe_allow_html=True)

    st.markdown(
        """
        <section id="get-the-app" class="ib-section ib-section-teal">
          <div class="ib-label" style="color:#0B1F3A">Get the app · coming soon</div>
          <h2>Inference Badge is coming soon.</h2>
          <div class="ib-store">Apple App Store<br><small>COMING SOON · no download link</small></div>
          <div class="ib-store">Google Play<br><small>COMING SOON · no download link</small></div>
          <p>Join the early-access list for launch updates. Your email is stored in the configured backend only if you opt in.</p>
          <p>Log in and account registration are coming soon.</p>
          <p>A hackathon build — honest, and improving fast.</p>
          <p>Built at the Patch the Conference Hackathon · FalkorDB · Bright Data · OpenAI</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    with st.form("launch_list_form"):
        email = st.text_input("Email address", placeholder="you@example.com")
        consent = st.checkbox(
            "I agree to store this email for Inference Badge early-access updates.",
            key="early_access_consent",
        )
        submitted = st.form_submit_button("Notify me", type="primary")
        if submitted:
            if not consent:
                st.error("Please opt in before joining the early-access email list.")
            else:
                try:
                    add_early_access_signup(email)
                except ValueError as exc:
                    st.error(str(exc))
                except DatabaseError:
                    st.error(
                        "We couldn’t save your signup. Check the FalkorDB connection and try again."
                    )
                else:
                    st.success("You’re on the early-access list. No email has been sent.")
    st.button("▶ Try the business demo", type="primary", on_click=_go_to_demo, key="app_demo_cta")

    st.markdown('<footer class="ib-dark"><h3>Inference Badge</h3><p>Product: <a href="#how-it-works">How it works</a> · <a href="#story">Demo story</a> · <a href="#for-sales-teams">For sales teams</a> · <a href="#for-organisers">For organisers</a></p><p>Trust: <a href="#privacy">Privacy</a> · <a href="#faq">FAQ</a> · Contact details not configured</p><p>Get the app: <a href="#get-the-app">App Store · Coming soon</a> · <a href="#get-the-app">Google Play · Coming soon</a></p><hr><small>Built at the Patch the Conference Hackathon · FalkorDB · Bright Data · OpenAI</small><p><a href="#privacy">Privacy</a> · Terms · Contact</p></footer>', unsafe_allow_html=True)


def _proof_row(state: dict[str, Any]) -> None:
    covered = 1 if state["talk_logged"] else 0
    stopped = 1 if state["collision_stopped"] else 0
    followup = 1 if state["talk_logged"] else 0
    metrics = st.columns(3)
    for col, value, label in zip(
        metrics,
        (covered, stopped, followup),
        ("Lead list covered", "Double talks stopped", "Follow-up ready"),
    ):
        col.markdown(
            f'<div class="ib-proof"><strong>{value}</strong>{label}<br><small>Demo count</small></div>',
            unsafe_allow_html=True,
        )


def _render_demo_phone(step: int, state: dict[str, Any]) -> None:
    phone_user = "Sam" if step == 3 else "Alex"
    st.markdown(
        f'<div class="ib-label" style="--accent:#2440FF">Phone · {phone_user}</div>',
        unsafe_allow_html=True,
    )
    with st.container(border=True):
        st.markdown('<div class="ib-phone-notch"></div>', unsafe_allow_html=True)
        st.caption("DevConf 2026 · Demo data · Simulated proximity")
        if step == 1:
            st.subheader("Conference sign-up list")
            st.markdown('<span class="ib-hot">HOT · 92</span> &nbsp; **Sarah Demo**', unsafe_allow_html=True)
            st.write("Head of AI Platform · Stripe Demo")
            st.caption("Why: right role, right company, going to the AI talk.")
            st.info("The demo lead list represents conference sign-up records.")
        elif step == 2:
            st.subheader("A lead is near you")
            st.markdown('<div class="ib-radar" aria-label="Simulated badge signal"></div>', unsafe_allow_html=True)
            st.markdown('<span class="ib-hot">HOT LEAD · SIMULATED</span>', unsafe_allow_html=True)
            st.write("Sarah Demo · right next to you")
            st.write("Demo facts: 8,000+ staff · ~$70B valuation")
            st.markdown("**3 THINGS TO SAY**")
            for prompt in (
                "How are you connecting AI projects to your platform?",
                "What does your team need to ship agents safely?",
                "Are you going to the AI talk this afternoon?",
            ):
                st.markdown(f"- {prompt}")
            st.button(
                "CONNECT · demo only",
                key="demo_connect",
                type="primary",
                on_click=_set_phone_action,
                args=("Alex chose to connect in the demo.",),
            )
            if st.session_state.get("phone_action"):
                st.caption(st.session_state["phone_action"])
        elif step == 3:
            st.subheader("Give them space")
            st.warning("Alex is already talking to Sarah Demo — stand down.")
            st.write("The shared team memory found an active conversation.")
            c1, c2 = st.columns(2)
            c1.button(
                "Find another lead",
                key="find_other_demo",
                on_click=_set_phone_action,
                args=("Alex chose to find another demo lead.",),
            )
            c2.button(
                "Remind me later",
                key="remind_demo",
                on_click=_set_phone_action,
                args=("Reminder shown for this demo only.",),
            )
            if st.session_state.get("phone_action"):
                st.caption(st.session_state["phone_action"])
        elif step == 4:
            st.subheader("Attendee nearby")
            if state["dave_sharing"]:
                st.write("Dave Demo · sharing is on")
            else:
                st.write("**Attendee (private)**")
                st.caption("Example code: DEMO-7F2A · no name or photo shown")
            st.warning("Sam sees that Alex already met this attendee and stands down.")
            st.caption("The team check still works without revealing the attendee’s private name.")
            st.toggle(
                "Dave's demo location sharing",
                value=state["dave_sharing"],
                key="dave_sharing_widget",
                on_change=lambda: _set_demo_sharing(
                    st.session_state["dave_sharing_widget"]
                ),
            )
        else:
            st.subheader("After the talk")
            st.write("Sarah Demo · choose an outcome")
            outcome = st.radio(
                "Demo outcome",
                ("Interested", "Follow up", "Not a fit"),
                horizontal=True,
                key="demo_outcome",
            )
            st.button(
                "Talk logged" if state["talk_logged"] else "Log demo talk · one tap",
                key="log_demo_talk",
                on_click=_log_demo_talk,
                disabled=state["talk_logged"],
            )
            st.success(f"Draft ready for review · {outcome}")
            st.write("Hi Sarah, great speaking about your AI platform work. Shall we continue the conversation after DevConf?")
            st.caption("Draft only. No message was sent.")


def _render_demo_booth(step: int, state: dict[str, Any]) -> None:
    st.markdown('<div class="ib-label" style="--accent:#00C896">Booth · team view</div>', unsafe_allow_html=True)
    if step == 1:
        st.markdown('<div class="ib-panel"><h3>Lead list</h3><p>1 HOT demo lead · Sarah Demo</p><p>Coverage begins at 0%</p></div>', unsafe_allow_html=True)
    elif step == 2:
        st.markdown('<div class="ib-panel"><h3>New simulated connection</h3><p>Alex Demo → Sarah Demo</p><p>Checked against the demo sign-up list.</p></div>', unsafe_allow_html=True)
    elif step == 3:
        st.markdown('<div class="ib-panel"><h3>Collision stopped</h3><p>Alex Demo is already talking to Sarah Demo.</p><p>Sam Demo receives a stop warning.</p></div>', unsafe_allow_html=True)
    elif step == 4:
        display_name = "Dave Demo" if state["dave_sharing"] else "Attendee (private)"
        st.markdown(f'<div class="ib-panel"><h3>Privacy state checked</h3><p>{display_name}</p><p>Team memory remains useful without exposing a private attendee name.</p></div>', unsafe_allow_html=True)
    else:
        if state["talk_logged"]:
            st.markdown('<div class="ib-panel"><h3>Talk logged · demo</h3><p>Sarah Demo marked covered.</p><p>Follow-up draft is ready; nothing has been sent.</p></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="ib-panel"><h3>Ready to log the demo talk</h3><p>Review the outcome and draft on the phone, then tap Next to complete the demo.</p></div>', unsafe_allow_html=True)
    _proof_row(state)
    st.markdown('<div class="ib-panel"><strong>Live demo feed</strong><p>Alex Demo · proximity simulated</p><p>Sam Demo · collision check</p><p>Sarah Demo · follow-up draft</p></div>', unsafe_allow_html=True)


def _render_business_story() -> None:
    if "demo_state" not in st.session_state:
        st.session_state["demo_state"] = new_demo_state()
    state = st.session_state["demo_state"]
    st.markdown('<div class="ib-label" style="--accent:#2440FF">Business demo · 90 seconds · Demo data</div><h1>One lead. One conversation. One team view.</h1><p>Follow the story below. The phone and booth respond together; all people and proximity are simulated.</p>', unsafe_allow_html=True)
    top = st.columns([3, 1, 1])
    top[0].progress(state["step"] / STEP_COUNT, text=f"Step {state['step']} of {STEP_COUNT} · {DEMO_STEPS[state['step'] - 1]}")
    top[1].button("Restart demo", on_click=_restart_demo, use_container_width=True)
    top[2].button("Exit demo", on_click=_go_to_marketing, use_container_width=True)

    left, right = st.columns(2, gap="large")
    with left:
        _render_demo_phone(state["step"], state)
    with right:
        _render_demo_booth(state["step"], state)

    captions = (
        "Before the conference, attendees signed up and chose their badge preference.",
        "Now walk up to Sarah Demo — the badge connection is simulated.",
        "Sam walks toward Sarah; the shared team memory says Alex already has the conversation.",
        "Dave stays private while the team check can still prevent a repeat approach.",
        "From sign-up list to a useful follow-up draft: find, connect, convert.",
    )
    st.info(captions[state["step"] - 1])
    explanations = (
        "The demo list marks Sarah as a match; no real sign-up records are loaded.",
        "The phone and booth show a simulated proximity connection, not live sensing.",
        "The team-memory check warns Sam before a second salesperson approaches Sarah.",
        "Sharing off hides Dave’s name while the demo still shows the coverage warning.",
        "The demo-only outcome updates the counters and prepares a draft; nothing is sent.",
    )
    st.caption(explanations[state["step"] - 1])
    with st.expander("How did that work?"):
        flow = st.columns(4)
        for col, text in zip(
            flow,
            ("BADGE SENSES\n(simulated)", "SIGN-UP LIST\nCHECKED", "TEAM MEMORY\nCHECKED", "PROMPT\nSHOWN"),
        ):
            col.markdown(f'<div class="ib-proof">{text.replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)

    if state["step"] < STEP_COUNT:
        st.button("Next", type="primary", on_click=_advance_demo, use_container_width=True)
    elif not state["done"]:
        st.button("Next · log the demo talk", type="primary", on_click=_advance_demo, use_container_width=True)
    else:
        st.success("Demo complete · Leads found: 1 · Double talks stopped: 1 · Follow-up ready: 1")
        again, how = st.columns(2)
        again.button("Run it again", on_click=_restart_demo, use_container_width=True, type="primary")
        how.button("Conference setup", on_click=_go_to_setup, use_container_width=True)


def _render_conference_setup() -> None:
    st.markdown(
        '<div class="ib-label" style="--accent:#00C896">Conference setup demo · organizer view</div>'
        '<h1>Add the badge to your conference</h1>'
        '<p>A short preview of how an organizer could introduce the plugin. This is a walkthrough only; it does not connect to an event system or change settings.</p>',
        unsafe_allow_html=True,
    )
    setup_steps = (
        ("01", "database", "Add the plugin", "Place the badge option in your conference sign-up flow."),
        ("02", "globe", "Connect the attendee list", "Use conference sign-ups as the team’s lead pool."),
        ("03", "lock", "Let attendees choose", "Attendees control sharing on their own phone."),
    )
    for number, icon_name, title, body in setup_steps:
        st.markdown(
            f'<div class="ib-setup-row">{_icon(icon_name)}'
            f'<div><div class="ib-label" style="color:#008B70">STEP {number}</div>'
            f'<h3>{title}</h3><p>{body}</p></div></div>',
            unsafe_allow_html=True,
        )
    st.markdown(
        '<div class="ib-panel"><div class="ib-label" style="--accent:#00C896">INTERACTIVE SIMULATION</div>'
        '<h2>Set up a sample attendee sign-up</h2>'
        '<p>Choose what an organizer offers, then experience the attendee’s opt-in choice. Nothing is saved or connected.</p></div>',
        unsafe_allow_html=True,
    )
    offer_badge = st.checkbox(
        "Offer the optional badge during conference sign-up",
        value=True,
        key="conference_setup_offer_badge",
    )
    include_opted_in = st.checkbox(
        "Add opted-in attendees to the participating team’s lead list",
        value=True,
        key="conference_setup_include_opted_in",
        disabled=not offer_badge,
    )
    st.button(
        "Preview attendee sign-up",
        type="primary",
        on_click=_show_setup_preview,
        disabled=not offer_badge,
        use_container_width=True,
    )
    if not offer_badge:
        st.info("The badge option is off, so it won’t appear in the sample sign-up.")
    elif st.session_state.get("conference_setup_previewed"):
        st.markdown(
            '<div class="ib-phone"><div class="ib-phone-notch"></div>'
            '<div class="ib-label">SAMPLE CONFERENCE SIGN-UP</div>'
            '<h3>Would you like to use an event badge?</h3>'
            '<p>Opt in to share your badge with participating sales teams during this event. You can keep your details private and change your choice later.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.checkbox(
            "I choose to share my badge with participating sales teams",
            value=True,
            key="conference_setup_sharing",
        )
        st.button(
            "Complete sample sign-up",
            on_click=_complete_setup_simulation,
            use_container_width=True,
        )
    if "conference_setup_result" in st.session_state:
        if st.session_state["conference_setup_result"]:
            if include_opted_in:
                st.success(
                    "You opted in. In this simulation, your demo badge appears on the participating team’s lead list."
                )
            else:
                st.success(
                    "You opted in, but the organizer did not add opted-in attendees to the team lead list."
                )
        else:
            st.info(
                "You chose not to share. The sample team view keeps you private and does not add you to its lead list."
            )
        st.button("Run the setup simulation again", on_click=_restart_setup_simulation)
    st.markdown(
        '<div class="ib-panel"><strong>Works with your conference app · concept only</strong>'
        '<p>Attendee consent, sign-up integration, and organizer controls are not connected in this prototype.</p></div>',
        unsafe_allow_html=True,
    )
    st.button(
        "See the business demo",
        type="primary",
        on_click=_go_to_demo,
        use_container_width=True,
    )


def _render_demo() -> None:
    story_tab, phone_tab, booth_tab = st.tabs(
        ("90-second story", "Phone app", "Booth dashboard")
    )
    with story_tab:
        _render_business_story()
    with phone_tab:
        _render_phone_prototype()
    with booth_tab:
        _render_booth_dashboard()


def _render_phone_prototype() -> None:
    st.markdown('<div class="ib-label" style="--accent:#2440FF">Phone prototype · simulated · Demo data</div><h1>Your badge, at a glance</h1>', unsafe_allow_html=True)
    status = st.selectbox(
        "Preview state",
        ("Ready demo", "Empty · no one nearby", "Loading · checking the list", "Privacy off"),
        help="Preview empty, loading, and privacy states without saving real data.",
        key="phone_preview_state",
    )
    profile_deleted = st.session_state.get("phone_profile_deleted", False)
    if status == "Empty · no one nearby":
        st.info("No one near you yet.")
    elif status == "Loading · checking the list":
        st.info("Checking the lead list… (preview state)")
    elif status == "Privacy off":
        st.markdown('<div class="ib-privacy"><strong>Location sharing is off.</strong><br>Your name is hidden from this demo screen.</div>', unsafe_allow_html=True)
    if profile_deleted:
        st.info("The demo profile is hidden for this browser session. No real account or graph data was deleted.")

    private_preview = (
        not st.session_state.get("phone_sharing", True) or status == "Privacy off"
    )
    salesperson_label = "You" if profile_deleted else "You · Alex Demo"
    tabs = st.tabs(
        ("My Badge", "Nearby", "Lead Card", "Stop Card", "Join Card", "Private", "After-Talk", "My Day")
    )
    if status in ("Empty · no one nearby", "Loading · checking the list"):
        state_message = (
            "No one near you yet."
            if status == "Empty · no one nearby"
            else "Checking the lead list…"
        )
        for tab in tabs:
            with tab:
                st.info(state_message)
                st.caption("This preview state hides attendee details on every phone screen.")
        return

    with tabs[0]:
        if profile_deleted:
            st.markdown('<div class="ib-phone"><div class="ib-phone-notch"></div><h3>No demo profile</h3><p>The local preview is hidden for this session.</p></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="ib-phone"><div class="ib-phone-notch"></div><span class="ib-chip">DEMO DATA</span><h3>Alex Demo</h3><p>Field sales · Demo Company</p><p>Badge ID: DEMO-ALEX</p></div>', unsafe_allow_html=True)
        sharing = st.toggle("Location sharing on this demo phone", value=st.session_state.get("phone_sharing", True), key="phone_sharing")
        st.caption("This switch is only a session preview; it does not change real device settings.")
        pause, delete = st.columns(2)
        pause.button(
            "Pause sharing for 1 hour",
            key="pause_sharing",
            on_click=_pause_phone_sharing,
        )
        delete.button(
            "Delete my demo data",
            key="delete_demo_profile",
            on_click=_clear_phone_profile,
        )
        if st.session_state.get("phone_action"):
            st.info(st.session_state["phone_action"])
        st.caption("QR preview · DEMO-ALEX")
    with tabs[1]:
        if private_preview:
            st.markdown(f'<div class="ib-phone"><div class="ib-phone-notch"></div><h3>Near you</h3><p>● {salesperson_label}</p><p>Attendee (private) · DEMO-7F2A · right next to you</p><p>● Maya Demo · teammate check available</p></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="ib-phone"><div class="ib-phone-notch"></div><h3>Near you</h3><p>● {salesperson_label}</p><p><span class="ib-hot">● Lead · Sarah Demo</span> · right next to you</p><p>● Attendee Demo · a few steps away</p><p>● Maya Demo covering a lead</p></div>', unsafe_allow_html=True)
        st.caption("Simulated proximity · no real sensing.")
    with tabs[2]:
        if private_preview:
            st.markdown('<div class="ib-phone"><div class="ib-phone-notch"></div><span class="ib-chip">PRIVATE DEMO</span><h3>Attendee (private)</h3><p>Example code: DEMO-7F2A</p><p>No name, photo, company, or location is shown.</p><p>Team interaction check remains available.</p></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="ib-phone ib-anim"><div class="ib-phone-notch"></div><span class="ib-hot">HOT · 92</span><h3>Sarah Demo</h3><p>Head of AI Platform · Stripe Demo</p><p>Why: right role, right company, going to the AI talk.</p><p>Demo facts: 8,000+ staff · ~$70B valuation · Ruby / AWS / PostgreSQL</p><h4>3 things to say</h4><ol><li>How are you connecting AI projects to your platform?</li><li>What does your team need to ship agents safely?</li><li>Are you going to the AI talk this afternoon?</li></ol></div>', unsafe_allow_html=True)
        st.button(
            "CONNECT · human decides",
            type="primary",
            key="phone_connect",
            on_click=_set_phone_action,
            args=("Connect selected in the demo; no message was sent.",),
        )
        if st.session_state.get("phone_action"):
            st.caption(st.session_state["phone_action"])
    with tabs[3]:
        if private_preview:
            st.markdown('<div class="ib-card" style="border-color:#FF4A00"><span class="ib-chip">TEAM CHECK</span><h3>Give them space</h3><p>A teammate has already met this private attendee.</p><small>Silent alert preview · vibration pattern would accompany an alert.</small></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="ib-card" style="border-color:#FF4A00"><span class="ib-chip">TEAM CHECK</span><h3>Give them space</h3><p>Maya Demo is talking to Sarah Demo right now.</p><small>Silent alert preview · vibration pattern would accompany an alert.</small></div>', unsafe_allow_html=True)
        st.button(
            "Find another lead",
            key="phone_find_another",
            on_click=_set_phone_action,
            args=("Find another lead selected in the demo.",),
        )
        st.button(
            "Remind me later",
            key="phone_remind",
            on_click=_set_phone_action,
            args=("Reminder selected in the demo.",),
        )
        if st.session_state.get("phone_action"):
            st.caption(st.session_state["phone_action"])
    with tabs[4]:
        if private_preview:
            st.markdown('<div class="ib-card"><h3>Attendee nearby</h3><p>Invite this private attendee into the conversation?</p><p>The human always decides.</p></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="ib-card"><h3>Hot lead nearby</h3><p>Bring Sarah Demo into this talk?</p><p>The human always decides.</p></div>', unsafe_allow_html=True)
        bring, stay = st.columns(2)
        bring.button(
            "Bring them in",
            type="primary",
            key="phone_bring",
            on_click=_set_phone_action,
            args=("Invite selected in the demo; no attendee was contacted.",),
        )
        stay.button(
            "Stay focused",
            key="phone_stay",
            on_click=_set_phone_action,
            args=("Stay focused selected in the demo.",),
        )
        if st.session_state.get("phone_action"):
            st.caption(st.session_state["phone_action"])
    with tabs[5]:
        if private_preview:
            st.markdown('<div class="ib-privacy"><h3>Attendee (private)</h3><p>Example code: DEMO-7F2A</p><p>No name or photo is shown. Teammate check: a prior interaction is recorded.</p></div>', unsafe_allow_html=True)
        else:
            st.info("Turn off the demo phone sharing switch in My Badge to preview the private state.")
    with tabs[6]:
        if private_preview:
            st.markdown('<div class="ib-phone"><div class="ib-phone-notch"></div><h3>After the talk · 10 seconds</h3><p>Summary: conversation completed with a private attendee.</p><p>Follow-up draft is ready to review; it is not sent.</p></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="ib-phone"><div class="ib-phone-notch"></div><h3>After the talk · 10 seconds</h3><p>Summary: discussed platform needs and the AI session.</p><p>Follow-up draft is ready to review; it is not sent.</p></div>', unsafe_allow_html=True)
        st.radio("Outcome", ("Interested", "Follow up", "Not a fit"), horizontal=True, key="phone_outcome")
        st.button(
            "Summary approved"
            if st.session_state.get("phone_summary_approved")
            else "Approve demo summary",
            key="approve_demo_summary",
            on_click=_approve_phone_summary,
            disabled=st.session_state.get("phone_summary_approved", False),
        )
        if private_preview:
            st.caption("Draft: “Hello, great speaking with you. Shall we continue after the conference?”")
        else:
            st.caption("Draft: “Hi Sarah, great speaking about your AI platform work. Shall we continue after the conference?”")
        if st.session_state.get("phone_summary_approved"):
            st.success("Approved in this demo session. Nothing was sent.")
    with tabs[7]:
        if private_preview:
            st.markdown('<div class="ib-card"><h3>My day · Demo</h3><p>1 conversation with Attendee (private)</p><p>1 team interaction recorded</p><p>1 anonymous follow-up draft to review</p><p>Nothing has been sent.</p></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="ib-card"><h3>My day · Demo</h3><p>1 conversation with Sarah Demo</p><p>1 lead covered</p><p>1 follow-up draft to review</p><p>Nothing has been sent.</p></div>', unsafe_allow_html=True)


def _render_booth_dashboard() -> None:
    st.markdown('<div class="ib-label" style="--accent:#00C896">Booth dashboard · local prototype</div><h1>Team coverage at a glance</h1>', unsafe_allow_html=True)
    state = st.session_state.get("demo_state", new_demo_state())
    _proof_row(state)
    left, right = st.columns([1.2, 1], gap="large")
    with left:
        st.subheader("Live team floor · simulated")
        st.markdown('<div class="ib-panel"><p>● Alex Demo ── Sarah Demo · conversation context</p><p>● Maya Demo ── coverage check</p><p>● Attendee (private) · anonymous demo state</p></div>', unsafe_allow_html=True)
        st.caption("Connections shown here are demo state, not real location sensing.")
    with right:
        st.subheader("Recent demo activity")
        st.markdown('<div class="ib-card"><p>1. Sarah Demo added from sign-up sample</p><p>2. Alex Demo check-in simulated</p><p>3. Repeat approach warning shown to Maya Demo</p><p>4. Follow-up draft ready for review</p></div>', unsafe_allow_html=True)
    st.divider()
    st.markdown("### FalkorDB · graph-backed team memory")
    connected, message = health_check()
    st.write("Connection:", "Connected" if connected else "Unavailable")
    if not connected:
        st.caption(message)
        return

    try:
        leads = list_leads()
    except DatabaseError as exc:
        st.error(str(exc))
        return
    if not leads:
        st.info("The connected graph has no leads yet. Live demo data is not initialized.")
        if st.button("Initialize demo data", type="primary"):
            ok, seed_message = seed_demo_data()
            (st.success if ok else st.error)(seed_message)
            if ok:
                st.rerun()
        return

    df = pd.DataFrame(leads)
    selected_options = {
        (
            f"{lead.get('name') or 'Unknown'} · {lead.get('company') or 'Unknown'}"
            if lead.get("locationShared") is True
            else f"Attendee (private) · {str(lead['id'])[:18]}"
        ): str(lead["id"])
        for lead in leads
    }
    selected_label = st.selectbox("Inspect linked lead", list(selected_options))
    selected_id = selected_options[selected_label]
    selected = next(lead for lead in leads if str(lead["id"]) == selected_id)
    private = selected.get("locationShared") is not True
    safe_leads = df.copy()
    if "locationShared" in safe_leads and "name" in safe_leads:
        safe_leads.loc[safe_leads["locationShared"] != True, "name"] = "Attendee (private)"
        safe_leads.loc[safe_leads["locationShared"] != True, "company"] = "Hidden in private mode"
        safe_leads.loc[safe_leads["locationShared"] != True, "status"] = "Private"
        safe_leads.loc[safe_leads["locationShared"] != True, "teammate"] = "Team interaction recorded"
        safe_leads.loc[safe_leads["locationShared"] != True, "session"] = "Hidden in private mode"
    st.dataframe(
        safe_leads[["name", "company", "status", "teammate", "session"]].rename(
            columns={"name": "Attendee", "company": "Company", "status": "Status", "teammate": "Teammate", "session": "Session"}
        ),
        use_container_width=True,
        hide_index=True,
    )
    st.markdown("#### Evidence path")
    if private:
        st.code(
            f"Attendee code: {selected_id} → team interaction: "
            f"{'recorded' if selected.get('teammate') else 'not recorded'}",
            language="text",
        )
        st.info("Attendee (private) · name, company, session, and location are hidden.")
    else:
        st.code(
            f"TeamMember({selected.get('teammate') or 'Unknown'}) → MET → "
            f"Lead({selected.get('name') or 'Unknown'}) → ATTENDING → "
            f"Session({selected.get('session') or 'Unknown'})",
            language="text",
        )
        st.markdown("#### Company context")
        st.write("Company:", selected.get("company") or "Unknown")
        st.write("Tier:", selected.get("tier") or "Unclassified")
        st.write("Funding:", selected.get("funding") or "Not available")
        st.write("Employees:", selected.get("employees") or "Not available")
        st.caption("Values are those stored in the graph; seeded sample facts are demo data.")
    if not private and st.button("Run optional Bright Data lookup", key="live_enrich"):
        try:
            result = enrich_company(str(selected.get("company") or ""))
            if result.get("live") and result.get("data"):
                update_company_enrichment(str(selected.get("company") or ""), result["data"], result["source"])
                st.success(f"Live response saved from {result['source']}.")
            elif result.get("live"):
                st.info("A live page was fetched; no safe structured fields were detected.")
            else:
                st.info(result.get("evidence", "No live request was made."))
        except EnrichmentError as exc:
            st.error(str(exc))
    if st.button("Generate evidence-based strategy brief", type="primary"):
        try:
            context = lead_context(selected_id)
            if context is None:
                st.error("The selected lead is no longer available in the graph.")
            else:
                if context.get("locationShared") is not True:
                    context.update({
                        "name": "Attendee (private)",
                        "company": None,
                        "tier": None,
                        "funding": None,
                        "employees": None,
                        "session": None,
                        "technology": None,
                        "teammate": "A teammate" if context.get("teammate") else None,
                        "teammateFocus": None,
                        "graph_path": "Private attendee code → team interaction check",
                    })
                else:
                    context["graph_path"] = (
                        f"TeamMember({context.get('teammate') or 'Unknown'}) → MET → "
                        f"Lead({context.get('name') or 'Unknown'}) → ATTENDING → "
                        f"Session({context.get('session') or 'Unknown'})"
                    )
                st.session_state["live_strategy_brief"] = generate_strategy_brief(context)
        except Exception as exc:
            st.error(f"Could not generate the brief: {exc}")
    if st.session_state.get("live_strategy_brief"):
        st.markdown(st.session_state["live_strategy_brief"])


st.set_page_config(
    page_title="Inference Badge",
    page_icon="🎟️",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "page" not in st.session_state:
    st.session_state["page"] = "Marketing"
if "demo_state" not in st.session_state:
    st.session_state["demo_state"] = new_demo_state()
if "dark_mode" not in st.session_state:
    st.session_state["dark_mode"] = False
_install_styles(dark_mode=st.session_state["dark_mode"])

with st.sidebar:
    _render_brand()
    st.caption("Conference coordination · simulated demo")
    st.toggle("Dark mode", key="dark_mode")
    st.caption("Explore")
    nav_icons = {
        "Marketing": ":material/home:",
        "Conference setup": ":material/event:",
        "Business demo": ":material/play_circle:",
    }
    for page in PAGES:
        st.button(
            label=page,
            key=f"nav_{page}",
            type="primary" if st.session_state["page"] == page else "secondary",
            use_container_width=True,
            on_click=_set_page,
            args=(page,),
            icon=nav_icons[page],
        )
    st.button(
        "Conference day simulation",
        key="nav_conference_day",
        type="primary" if st.session_state["page"] == "Conference day" else "secondary",
        use_container_width=True,
        icon=":material/route:",
        on_click=_go_to_conference_day,
    )
    st.divider()
    integrations = (
        ("database", "FalkorDB", "Team memory · Business demo → Booth tab"),
        (
            "globe",
            "Bright Data",
            "Configured"
            if os.getenv("BRIGHT_DATA_API_TOKEN") and os.getenv("BRIGHT_DATA_WEB_UNLOCKER_ZONE")
            else "Not configured · demo fallback",
        ),
        (
            "spark",
            "OpenAI",
            "Configured" if os.getenv("OPENAI_API_KEY") else "Demo fallback",
        ),
    )
    if st.session_state["page"] != "Conference day":
        integration_rows = "".join(
            f'<div class="ib-integration-row">{_icon(icon_name)}'
            f'<div><div class="ib-integration-name">{name}</div>'
            f'<div class="ib-integration-status">{status}</div></div></div>'
            for icon_name, name, status in integrations
        )
        st.markdown(
            f'<section class="ib-integrations"><div class="ib-integrations-title">Inference Badge integrations</div>{integration_rows}</section>',
            unsafe_allow_html=True,
        )

if st.session_state["page"] == "Marketing":
    _render_website()
elif st.session_state["page"] == "Conference setup":
    _render_conference_setup()
elif st.session_state["page"] == "Business demo":
    _render_demo()
elif st.session_state["page"] == "Conference day":
    render_simulation()
elif st.session_state["page"] in ("Login", "Sign up"):
    page_title = "Log in" if st.session_state["page"] == "Login" else "Create your account"
    st.markdown(
        f'<div class="ib-coming-soon ib-panel"><div class="ib-label">ACCOUNT ACCESS</div>'
        f'<h1>{page_title}</h1><p>Coming soon. Account access is not enabled in this prototype.</p>'
        f'<p>You can join the early-access list from the Marketing page. Your login details are not requested or stored here.</p></div>',
        unsafe_allow_html=True,
    )
    back, other = st.columns(2)
    back.button("Back to Marketing", on_click=_go_to_marketing, use_container_width=True)
    if st.session_state["page"] == "Login":
        other.button("Sign up · Coming soon", on_click=_go_to_signup, use_container_width=True)
    else:
        other.button("Log in · Coming soon", on_click=_go_to_login, use_container_width=True)
