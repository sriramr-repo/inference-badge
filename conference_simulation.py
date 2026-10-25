"""Guided, privacy-safe conference-day simulation for the prototype."""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

import streamlit as st

from database import DatabaseError, run_query_on_graph

SIMULATION_MODULE_VERSION = 7
CONFERENCE = "DevConf 2026"
GRAPH_NAME = "InferenceBadgeGraph"
PRIVATE_TOKEN = "Attendee #A-317"
TARGETS = (
    {
        "id": "sarah",
        "name": "Sarah Chen",
        "role": "VP Engineering",
        "company": "Acme Robotics",
        "score": 92,
        "temperature": "HOT",
        "why": "VP Engineering at a 1,200-person company, attending the scaling session, hiring engineers.",
        "facts": "1,200 staff · raised $85M · hiring engineers fast",
        "public_profile": "LinkedIn-style public signal: VP Engineering at Acme Robotics; platform hiring is active.",
        "graph_insight": "FalkorDB links Sarah to the scaling session and the team's AI-infrastructure focus.",
        "opener": "Ask how Acme is scaling engineering without slowing delivery.",
    },
    {
        "id": "tom",
        "name": "Tom Alvarez",
        "role": "Head of Platform",
        "company": "Northwind Health",
        "score": 74,
        "temperature": "WARM",
        "why": "Head of Platform at a 3,000-person company, expanding its platform team.",
        "facts": "3,000 staff · expanding platform team",
        "public_profile": "LinkedIn-style public signal: Head of Platform at Northwind Health; platform team is expanding.",
        "graph_insight": "FalkorDB shows Tom is an uncovered target attending the platform session.",
        "opener": "Ask what is driving Northwind's next platform hire.",
    },
    {
        "id": "lina",
        "name": "Lina Ortiz",
        "role": "CTO",
        "company": "Contoso Energy",
        "score": 81,
        "temperature": "WARM",
        "why": "CTO at a growing engineering organization.",
        "facts": "Demo data · engineering leadership",
        "public_profile": "Public profile preview: CTO at Contoso Energy.",
        "graph_insight": "FalkorDB marks Lina as a warm engineering-leadership match.",
        "opener": "Ask which engineering priority is hardest to staff this year.",
    },
    {
        "id": "eli",
        "name": "Eli Brooks",
        "role": "VP Engineering",
        "company": "Harbor Labs",
        "score": 79,
        "temperature": "WARM",
        "why": "VP Engineering with a growing product team.",
        "facts": "Demo data · product engineering",
        "public_profile": "Public profile preview: VP Engineering at Harbor Labs.",
        "graph_insight": "FalkorDB marks Eli as a warm product-engineering match.",
        "opener": "Ask how Harbor Labs is balancing product speed and platform quality.",
    },
    {
        "id": "noor",
        "name": "Noor Rahman",
        "role": "Head of Platform",
        "company": "Pinecone Health",
        "score": 76,
        "temperature": "WARM",
        "why": "Head of Platform focused on team growth.",
        "facts": "Demo data · platform engineering",
        "public_profile": "Public profile preview: Head of Platform at Pinecone Health.",
        "graph_insight": "FalkorDB marks Noor as a warm platform-engineering match.",
        "opener": "Ask what platform capability the team needs next.",
    },
)
BACKGROUND = (
    ("bg-1", "Mina Park", "Designer", "Studio North"),
    ("bg-2", "Owen Reed", "Operations lead", "Fieldworks"),
    ("bg-3", "Aria Singh", "Researcher", "Brightpath"),
)
CAPTIONS = (
    "Olivia adds Inference Badge to the conference already in use. No new app or spreadsheet.",
    "Permission comes first. Sarah opts in; another attendee chooses private mode.",
    "Nimbus builds a target list from conference sign-ups. Sarah is a strong match, with a clear reason why.",
    "One shared team memory keeps Maya from starting a conversation Sarah is already having with Alex.",
    "Private attendees stay private. Anonymous presence is enough for a team check; off means invisible.",
    "The team ends the conversation, saves a follow-up draft, and sees aggregate results.",
)
EXPLANATIONS = (
    "A conference plugin adds a badge step to sign-up. Only the selected fields are included in this sample.",
    "Sign-ups become the lead source. Sharing, private, and no-badge choices stay separate.",
    "The team's target criteria are compared with sample roles, companies, and sessions.",
    "Simulated walks check whether a teammate is already talking with the same lead before a second hello.",
    "Private mode shares only an anonymous token. Turning a badge off removes that presence from team views.",
    "The team saves a follow-up draft. Organiser results show totals only, never a private attendee or message.",
)


def new_simulation_state() -> dict[str, Any]:
    """Return the single shared world used by every simulation panel."""
    return {
        "phase": 1,
        "free_explore": False,
        "run_complete": False,
        "run_id": uuid4().hex,
        "backend": None,
        "backend_message": "",
        "matched_target_ids": [],
        "plugin_active": False,
        "signup_fields": {
            "Name": True,
            "Company": True,
            "Job title": True,
            "Sessions": True,
        },
        "retention_days": 30,
        "sarah_signed_up": False,
        "no_badge_signup": False,
        "private_badge": False,
        "private_sharing": True,
        "targets_built": False,
        "selected_salesperson": "Alex",
        "phone_card": None,
        "active_talks": {},
        "talks_facilitated": 0,
        "collisions_stopped": 0,
        "alternate_found": False,
        "private_seen": False,
        "talk_ended": False,
        "outcome": "Interested",
        "outcome_saved": False,
        "followup_ready": False,
        "last_talk_lead": "sarah",
        "followup_text": (
            "Hi Sarah — great meeting you at DevConf. Here’s the 2-page note on "
            "how Nimbus cut engineer onboarding from 3 weeks to 4 days, as promised."
        ),
        "activity": [],
    }


def _world() -> dict[str, Any]:
    existing = st.session_state.get("conference_day_simulation")
    if existing is None:
        world = new_simulation_state()
        serialized = st.query_params.get("ib_simulation")
        if serialized:
            try:
                if len(serialized) > 12000:
                    raise ValueError("Saved simulation state is too large.")
                saved = json.loads(serialized)
                serializable_fields = set(world) - {"followup_text"}
                if not isinstance(saved, dict) or set(saved) not in (
                    serializable_fields,
                    set(world),
                ):
                    raise ValueError("Saved simulation fields do not match.")
                saved_draft = saved.pop("followup_text", None)
                if saved_draft is not None and (
                    not isinstance(saved_draft, str) or len(saved_draft) > 2000
                ):
                    raise ValueError("Saved follow-up draft is invalid.")
                if not isinstance(saved["run_id"], str):
                    raise ValueError("Saved run ID is invalid.")
                UUID(saved["run_id"])
                if type(saved["phase"]) is not int or saved["phase"] not in range(1, 7):
                    raise ValueError("Saved phase is invalid.")
                boolean_fields = (
                    "free_explore",
                    "run_complete",
                    "plugin_active",
                    "sarah_signed_up",
                    "no_badge_signup",
                    "private_badge",
                    "private_sharing",
                    "targets_built",
                    "alternate_found",
                    "private_seen",
                    "talk_ended",
                    "outcome_saved",
                    "followup_ready",
                )
                if any(type(saved[field]) is not bool for field in boolean_fields):
                    raise ValueError("Saved simulation flags are invalid.")
                if saved["selected_salesperson"] not in ("Alex", "Maya"):
                    raise ValueError("Saved salesperson is invalid.")
                if saved["retention_days"] not in (7, 30, 90):
                    raise ValueError("Saved data-retention selection is invalid.")
                valid_leads = {lead["id"] for lead in TARGETS}
                if not isinstance(saved["active_talks"], dict) or any(
                    lead_id not in valid_leads or teammate not in ("Alex", "Maya")
                    for lead_id, teammate in saved["active_talks"].items()
                ):
                    raise ValueError("Saved team activity is invalid.")
                if saved["phone_card"] not in (
                    None,
                    "stop",
                    "sarah",
                    "tom",
                    "lina",
                    "eli",
                    "noor",
                    "talking",
                    "alternate",
                    "private",
                    "after_talk",
                ):
                    raise ValueError("Saved phone state is invalid.")
                if saved["outcome"] not in ("Interested", "Follow up", "Not a fit"):
                    raise ValueError("Saved outcome is invalid.")
                if not isinstance(saved["signup_fields"], dict) or set(
                    saved["signup_fields"]
                ) != set(world["signup_fields"]):
                    raise ValueError("Saved sign-up fields are invalid.")
                if any(
                    type(value) is not bool
                    for value in saved["signup_fields"].values()
                ):
                    raise ValueError("Saved sign-up field choices are invalid.")
                if not isinstance(saved["activity"], list) or any(
                    not isinstance(item, str) for item in saved["activity"]
                ):
                    raise ValueError("Saved activity is invalid.")
                if saved["backend"] not in (None, "FalkorDB", "In-memory"):
                    raise ValueError("Saved backend selection is invalid.")
                if not isinstance(saved["backend_message"], str) or len(
                    saved["backend_message"]
                ) > 200:
                    raise ValueError("Saved backend status is invalid.")
                if not isinstance(saved["matched_target_ids"], list) or any(
                    lead_id not in valid_leads for lead_id in saved["matched_target_ids"]
                ):
                    raise ValueError("Saved target matches are invalid.")
                if any(
                    type(saved[field]) is not int or saved[field] < 0
                    for field in ("talks_facilitated", "collisions_stopped")
                ):
                    raise ValueError("Saved counters are invalid.")
                world.update(saved)
            except (json.JSONDecodeError, TypeError, ValueError, KeyError):
                st.warning(
                    "The saved demo state could not be restored. Starting a fresh simulation."
                )
    else:
        world = new_simulation_state()
        if isinstance(existing, dict):
            world.update(existing)
    st.session_state["conference_day_simulation"] = world
    return world


def _record(world: dict[str, Any], activity: str) -> None:
    world["activity"].insert(0, activity)
    del world["activity"][8:]


def _query_result_ids(result: Any) -> list[str]:
    return [
        str(row[0])
        for row in (getattr(result, "result_set", None) or [])
        if row and row[0] is not None
    ]


def _sync_graph(world: dict[str, Any]) -> None:
    sim_id = world["run_id"]
    run_query_on_graph(
        GRAPH_NAME,
        """
        MERGE (a:SimulationDemo:TeamMember {simId:$sim_id,id:'alex'})
        SET a.name='Alex', a.company='Nimbus', a.role='Salesperson'
        MERGE (m:SimulationDemo:TeamMember {simId:$sim_id,id:'maya'})
        SET m.name='Maya', m.company='Nimbus', m.role='Salesperson'
        MERGE (p:SimulationDemo:TeamMember {simId:$sim_id,id:'priya'})
        SET p.name='Priya', p.company='Nimbus', p.role='Booth manager'
        MERGE (s:SimulationDemo:Session {simId:$sim_id,id:'scaling-session'})
        SET s.title='Scaling Engineering Teams', s.time='10:00 AM'
        """,
        {"sim_id": sim_id},
    )
    for lead in TARGETS:
        params = {
            "sim_id": sim_id,
            "lead_id": lead["id"],
            "name": lead["name"],
            "role": lead["role"],
            "company": lead["company"],
            "score": lead["score"],
            "temperature": lead["temperature"],
            "why": lead["why"],
            "is_target": world["targets_built"],
        }
        run_query_on_graph(
            GRAPH_NAME,
            """
            MERGE (c:SimulationDemo:Company {simId:$sim_id,id:$lead_id})
            SET c.name=$company
            MERGE (l:SimulationDemo:Lead {simId:$sim_id,id:$lead_id})
            SET l.name=$name, l.role=$role, l.company=$company,
                l.score=$score, l.temperature=$temperature,
                l.why=$why, l.isTarget=$is_target, l.locationShared=true
            MERGE (c)-[:EMPLOYS {simId:$sim_id}]->(l)
            """,
            params,
        )
    run_query_on_graph(
        GRAPH_NAME,
        """
        MERGE (l:SimulationDemo:Lead {simId:$sim_id,id:'sarah'})
        MERGE (s:SimulationDemo:Session {simId:$sim_id,id:'scaling-session'})
        MERGE (l)-[:ATTENDING {simId:$sim_id}]->(s)
        """,
        {"sim_id": sim_id},
    )
    for lead_id, name, role, company in BACKGROUND:
        run_query_on_graph(
            GRAPH_NAME,
            """
            MERGE (a:SimulationDemo:Attendee {simId:$sim_id,id:$attendee_id})
            SET a.name=$name, a.role=$role, a.company=$company,
                a.isTarget=false, a.locationShared=true
            """,
            {
                "sim_id": sim_id,
                "attendee_id": lead_id,
                "name": name,
                "role": role,
                "company": company,
            },
        )
    if world["private_badge"]:
        run_query_on_graph(
            GRAPH_NAME,
            """
            MERGE (a:SimulationDemo:Attendee {simId:$sim_id,token:$token})
            SET a.private=true, a.sharing=$sharing
            """,
            {
                "sim_id": sim_id,
                "token": PRIVATE_TOKEN,
                "sharing": world["private_sharing"],
            },
        )
    run_query_on_graph(
        GRAPH_NAME,
        "MATCH ()-[r:CURRENTLY_TALKING_TO {simId:$sim_id}]->() DELETE r",
        {"sim_id": sim_id},
    )
    for lead_id, teammate in world["active_talks"].items():
        run_query_on_graph(
            GRAPH_NAME,
            """
            MATCH (tm:SimulationDemo:TeamMember {simId:$sim_id,id:$team_id}),
                  (l:SimulationDemo:Lead {simId:$sim_id,id:$lead_id})
            MERGE (tm)-[:CURRENTLY_TALKING_TO {simId:$sim_id}]->(l)
            """,
            {
                "sim_id": sim_id,
                "team_id": teammate.lower(),
                "lead_id": lead_id,
            },
        )


def _ensure_graph(world: dict[str, Any]) -> None:
    if world["backend"] is not None:
        return
    try:
        run_query_on_graph(GRAPH_NAME, "RETURN 1 AS ok")
        world["backend"] = "FalkorDB"
        _sync_graph(world)
        world["backend_message"] = "Shared team memory active · sample conference data only."
    except DatabaseError:
        world["backend"] = "In-memory"
        world["backend_message"] = (
            "Shared team memory · in-memory session demo."
        )


def _persist_graph(world: dict[str, Any]) -> None:
    if world["backend"] != "FalkorDB":
        return
    try:
        _sync_graph(world)
    except DatabaseError:
        world["backend"] = "In-memory"
        world["backend_message"] = (
            "Shared team memory · in-memory session demo."
        )


def _teammate_with_lead(world: dict[str, Any], lead_id: str) -> str | None:
    if world["backend"] == "FalkorDB":
        try:
            result = run_query_on_graph(
                GRAPH_NAME,
                """
                MATCH (tm:SimulationDemo:TeamMember {simId:$sim_id})
                      -[:CURRENTLY_TALKING_TO {simId:$sim_id}]->
                      (l:SimulationDemo:Lead {simId:$sim_id,id:$lead_id})
                RETURN tm.name AS name LIMIT 1
                """,
                {"sim_id": world["run_id"], "lead_id": lead_id},
            )
            rows = getattr(result, "result_set", None) or []
            return str(rows[0][0]) if rows and rows[0][0] is not None else None
        except DatabaseError:
            world["backend"] = "In-memory"
            world["backend_message"] = (
                "Shared team memory · in-memory session demo."
            )
    return world["active_talks"].get(lead_id)


def _build_target_list(world: dict[str, Any]) -> list[str]:
    if world["backend"] == "FalkorDB":
        try:
            result = run_query_on_graph(
                GRAPH_NAME,
                """
                MATCH (l:SimulationDemo:Lead {simId:$sim_id})
                WHERE l.isTarget=true
                RETURN l.id AS id ORDER BY l.score DESC
                """,
                {"sim_id": world["run_id"]},
            )
            ids = _query_result_ids(result)
            if ids:
                return ids
        except DatabaseError:
            world["backend"] = "In-memory"
            world["backend_message"] = (
                "Shared team memory · in-memory session demo."
            )
    return [lead["id"] for lead in TARGETS]


def _cleanup_graph(world: dict[str, Any]) -> str:
    if world["backend"] != "FalkorDB":
        return world["backend_message"]
    try:
        run_query_on_graph(
            GRAPH_NAME,
            "MATCH (n:SimulationDemo {simId:$sim_id}) DETACH DELETE n",
            {"sim_id": world["run_id"]},
        )
        return world["backend_message"]
    except DatabaseError:
        return "Could not remove this run's sample graph data; reset only cleared the local view."


def _act(action: str, lead_id: str | None = None) -> None:
    world = _world()
    phase = world["phase"]
    if action == "activate_plugin":
        world["plugin_active"] = True
        _record(world, "Olivia activated the sample conference badge.")
    elif action == "signup_sarah":
        world["sarah_signed_up"] = True
        _record(world, "Sarah Chen opted in to a demo badge.")
    elif action == "signup_private":
        world["private_badge"] = True
        world["private_sharing"] = True
        _record(world, "An attendee chose private mode.")
    elif action == "signup_no_badge":
        world["no_badge_signup"] = True
        _record(world, "An attendee chose not to use a badge.")
    elif action == "build_targets":
        world["targets_built"] = True
        _persist_graph(world)
        world["matched_target_ids"] = _build_target_list(world)
        _record(world, "Nimbus built a target list from sample sign-ups.")
    elif action in ("walk_sarah", "walk_lead"):
        lead_id = "sarah" if action == "walk_sarah" else lead_id
        if lead_id is None:
            return
        active_with = _teammate_with_lead(world, lead_id)
        if active_with and active_with != world["selected_salesperson"]:
            world["phone_card"] = "stop"
            world["collisions_stopped"] += 1
            _record(world, f"{world['selected_salesperson']} avoided a double pitch.")
        elif active_with:
            world["phone_card"] = "talking"
        else:
            world["phone_card"] = lead_id
            lead = _lead_for_id(lead_id)
            _record(
                world,
                f"{world['selected_salesperson']} walked toward {lead['name'] if lead else 'a target'} (simulated).",
            )
    elif action in ("connect_sarah", "connect_lead"):
        lead_id = "sarah" if action == "connect_sarah" else lead_id
        if lead_id is None:
            return
        active_with = _teammate_with_lead(world, lead_id)
        if active_with and active_with != world["selected_salesperson"]:
            world["phone_card"] = "stop"
            world["collisions_stopped"] += 1
            _record(world, f"{world['selected_salesperson']} avoided a double pitch.")
        else:
            world["active_talks"][lead_id] = world["selected_salesperson"]
            world["talks_facilitated"] += 1
            world["phone_card"] = "talking"
            lead = _lead_for_id(lead_id)
            _record(
                world,
                f"{world['selected_salesperson']} started talking with {lead['name'] if lead else 'a target'}.",
            )
    elif action == "find_alternate":
        world["alternate_found"] = True
        world["phone_card"] = "alternate"
        _record(world, "Maya found Tom Alvarez as an uncovered alternative.")
    elif action == "walk_tom":
        world["phone_card"] = "tom"
        _record(world, f"{world['selected_salesperson']} walked toward Tom (simulated).")
    elif action == "walk_private":
        world["phone_card"] = "private"
        world["private_seen"] = True
        _record(world, "A private badge appeared as an anonymous token.")
    elif action == "toggle_private":
        world["private_sharing"] = not world["private_sharing"]
        _record(
            world,
            "The private badge is visible anonymously."
            if world["private_sharing"]
            else "The attendee turned their badge off.",
        )
    elif action == "end_sarah":
        world["active_talks"].pop("sarah", None)
        world["talk_ended"] = True
        world["last_talk_lead"] = "sarah"
        world["phone_card"] = "after_talk"
        _record(world, "Alex ended the sample conversation with Sarah.")
    elif action == "end_talk":
        lead_id = lead_id or next(
            (
                active_id
                for active_id, teammate in world["active_talks"].items()
                if teammate == world["selected_salesperson"]
            ),
            None,
        )
        if lead_id:
            world["active_talks"].pop(lead_id, None)
            world["last_talk_lead"] = lead_id
            world["talk_ended"] = lead_id == "sarah" or world["talk_ended"]
            lead = _lead_for_id(lead_id)
            if lead:
                world["followup_text"] = (
                    f"Hi {lead['name']} — great meeting you at DevConf. "
                    f"Let’s continue the conversation about {lead['company']}."
                )
                st.session_state.pop("sim_followup", None)
            world["phone_card"] = "after_talk"
            _record(world, f"{world['selected_salesperson']} ended a sample conversation.")
    elif action == "save_outcome":
        world["outcome_saved"] = True
        world["followup_ready"] = world["outcome"] in ("Interested", "Follow up")
        _record(
            world,
            "A follow-up draft is ready for review."
            if world["followup_ready"]
            else "Sarah was marked not a fit; no follow-up was drafted.",
        )
    elif action == "next_phase" and phase < 6:
        world["phase"] += 1
        world["phone_card"] = None
        if world["phase"] == 6:
            world["selected_salesperson"] = "Alex"
            st.session_state["sim_salesperson"] = "Alex"
    elif action == "finish":
        world["run_complete"] = True
    elif action == "free_explore":
        world["free_explore"] = True
    elif action == "reset":
        backend_message = _cleanup_graph(world)
        for widget_key in (
            "sim_plugin_toggle",
            "sim_free_explore",
            "sim_confirm_reset",
            "sim_salesperson",
            "sim_followup",
            "sim_outcome",
            "sim_private_sharing",
            "sim_retention",
            *(f"sim_field_{field}" for field in world["signup_fields"]),
        ):
            st.session_state.pop(widget_key, None)
        new_world = new_simulation_state()
        new_world["backend"] = "FalkorDB" if "could not" not in backend_message.lower() else "In-memory"
        new_world["backend_message"] = backend_message
        st.session_state["conference_day_simulation"] = new_world
        _persist_graph(new_world)
        return
    _persist_graph(world)


def _phase_complete(world: dict[str, Any]) -> bool:
    return {
        1: world["plugin_active"],
        2: world["sarah_signed_up"] and world["private_badge"],
        3: world["targets_built"],
        4: (
            world["active_talks"].get("sarah") == "Alex"
            and world["collisions_stopped"] > 0
            and world["alternate_found"]
        ),
        5: world["private_seen"] and not world["private_sharing"],
        6: world["talk_ended"] and world["outcome_saved"],
    }[world["phase"]]


def _phase_caption(world: dict[str, Any]) -> str:
    card = world["phone_card"]
    if card == "stop":
        return "Alex is already talking with Sarah. Maya gets a clear stop and an uncovered alternative."
    if card == "private":
        return "This badge shares only a token. The attendee's identity is not available to the team."
    if world["phase"] == 4 and world["alternate_found"]:
        if card == "tom":
            return "Maya found Tom, an uncovered target, instead of repeating Alex's conversation."
        return "Tom is an uncovered target. Walk over to see the alternate lead card."
    return CAPTIONS[world["phase"] - 1]


def _clock(world: dict[str, Any]) -> str:
    return ("9:00 AM", "9:20 AM", "9:45 AM", "11:15 AM", "11:25 AM", "2:10 PM")[
        world["phase"] - 1
    ]


def _journey_frame(world: dict[str, Any]) -> None:
    stage = min(world["phase"], 5)
    stages = ("Setup", "Attendees", "Team prep", "Conference day", "Results")
    actors = (
        ("Olivia", "Conference organizer", "Connect the sample conference setup."),
        ("Sarah + private attendee", "Conference attendees", "Choose what each badge shares."),
        ("Alice + Bob", "Business field team", "Prepare the lead list and team context."),
        ("Alice + Bob", "Business field team", "Use the phone to coordinate live conversations."),
        ("Olivia + field team", "Conference outcomes", "Review clear results and privacy outcomes."),
    )
    actor, role, instruction = actors[stage - 1]
    chips = "".join(
        f'<span class="ib-journey-chip {"current" if index == stage else "done" if index < stage else "locked"}">{index} · {label}</span>'
        for index, label in enumerate(stages, 1)
    )
    st.markdown(
        f'<div class="ib-journey-frame"><div class="ib-journey-stepper">{chips}</div>'
        f'<div class="ib-journey-actor"><strong>{actor}</strong><span> · {role}</span></div>'
        f'<div class="ib-journey-instruction">{instruction}</div></div>',
        unsafe_allow_html=True,
    )


def _organiser_counters(world: dict[str, Any]) -> None:
    private_active = bool(world["private_badge"] and world["private_sharing"])
    badge_count = int(world["sarah_signed_up"]) + int(private_active)
    sharing = int(world["sarah_signed_up"]) + int(
        private_active
    )
    private_count = int(private_active)
    st.metric("Badges ready", badge_count)
    st.metric("Sharing on", sharing)
    st.metric("Private", private_count)
    st.metric("Meetings happening now", len(world["active_talks"]))
    st.metric("Double pitches stopped", world["collisions_stopped"])


def _render_conference(world: dict[str, Any]) -> None:
    st.markdown(f"### Conference · {CONFERENCE}")
    st.caption(f"Day 1 · {_clock(world)} · Organizer Olivia")
    organiser_tab, signup_tab = st.tabs(("Organiser Console", "Attendee Sign-Up"))
    with organiser_tab:
        st.markdown("**Add Inference Badge to this conference**")
        st.toggle(
            "Enable the optional badge plugin",
            key="sim_plugin_toggle",
            value=world["plugin_active"],
            disabled=world["plugin_active"],
        )
        if st.session_state.get("sim_plugin_toggle") and not world["plugin_active"]:
            st.button(
                "Activate badges",
                type="primary",
                on_click=_act,
                args=("activate_plugin",),
                use_container_width=True,
            )
        if world["plugin_active"]:
            st.caption("Choose sign-up fields")
            for field in world["signup_fields"]:
                world["signup_fields"][field] = st.checkbox(
                    field,
                    key=f"sim_field_{field}",
                    value=world["signup_fields"][field],
                )
            st.info("Only inside the venue, during conference hours.")
            st.selectbox(
                "Delete attendee badge data after the event",
                (7, 30, 90),
                index=(7, 30, 90).index(world["retention_days"]),
                key="sim_retention",
                format_func=lambda days: f"{days} days",
            )
            world["retention_days"] = st.session_state["sim_retention"]
            _organiser_counters(world)
            if world["phase"] == 6 and world["run_complete"]:
                st.markdown("#### Organiser results · totals only")
                st.metric("Meetings facilitated", world["talks_facilitated"])
                st.metric(
                    "Badges active",
                    int(world["sarah_signed_up"])
                    + int(world["private_badge"] and world["private_sharing"]),
                )
                st.caption(
                    f"Privacy choices: {int(world['sarah_signed_up'])} sharing · "
                    f"{int(world['private_badge'] and world['private_sharing'])} private · "
                    f"{int(world['private_badge'] and not world['private_sharing'])} off"
                )
                st.info(
                    "Exhibitors never saw private attendee identities. "
                    f"Badge data will be deleted in {world['retention_days']} days."
                )

    if world["phase"] == 6 and world["run_complete"]:
        st.markdown("#### Organiser closeout · aggregate results only")
        closeout = st.columns(4)
        closeout[0].metric(
                "Badges active",
                int(world["sarah_signed_up"])
                + int(world["private_badge"] and world["private_sharing"]),
        )
        closeout[1].metric("Meetings facilitated", world["talks_facilitated"])
        closeout[2].metric("Double pitches stopped", world["collisions_stopped"])
        closeout[3].metric("Follow-ups ready", int(world["followup_ready"]))
        st.caption(
                "Exhibitors never saw private attendee identities. "
                f"Badge data will be deleted in {world['retention_days']} days."
        )
    with signup_tab:
        if not world["plugin_active"]:
            st.info("Activate the plugin to preview its sign-up step.")
        else:
            st.markdown("#### Sample attendee sign-up")
            st.caption("Sarah Chen · VP Engineering · Acme Robotics")
            st.info(
                "Activate your digital badge? Exhibitor teams can recognise you at the "
                "conference and suggest a hello. You choose what is shared, and you "
                "can pause or delete it anytime."
            )
            st.button(
                "Share with exhibitors · Sarah",
                disabled=world["sarah_signed_up"],
                on_click=_act,
                args=("signup_sarah",),
                use_container_width=True,
            )
            if world["sarah_signed_up"]:
                st.success("Sarah's sample badge is ready · Demo data")
                st.markdown(
                    '<div class="ib-phone"><div class="ib-phone-notch"></div>'
                    '<div class="ib-label">SAMPLE DIGITAL BADGE</div>'
                    '<h3>Sarah Chen</h3><p>VP Engineering · Acme Robotics</p>'
                    '<div class="ib-chip">DEVCONF 2026 · DEMO</div></div>',
                    unsafe_allow_html=True,
                )
            st.markdown("---")
            st.markdown("#### Next attendee")
            st.caption("Attendee (details hidden in this demo)")
            st.button(
                "Private mode · attendee",
                disabled=world["private_badge"],
                on_click=_act,
                args=("signup_private",),
                use_container_width=True,
            )
            if world["private_badge"]:
                st.caption(f"Private badge token · {PRIVATE_TOKEN}")
                st.toggle(
                    "Private badge is visible anonymously",
                    key="sim_private_sharing",
                    value=world["private_sharing"],
                    on_change=_act,
                    args=("toggle_private",),
                )
            st.button(
                "No badge · sample attendee",
                disabled=world["no_badge_signup"],
                on_click=_act,
                args=("signup_no_badge",),
                use_container_width=True,
            )
            if world["no_badge_signup"]:
                st.caption("No badge created · not visible to the exhibitor team.")


def _lead_for_id(lead_id: str) -> dict[str, Any] | None:
    return next((lead for lead in TARGETS if lead["id"] == lead_id), None)


def _render_phone(world: dict[str, Any]) -> None:
    with st.container(key="sim-phone-shell"):
        _render_phone_panel(world)


def _render_phone_panel(world: dict[str, Any]) -> None:
    st.markdown("### Salesperson Phone")
    selected = st.selectbox(
        "Phone user",
        ("Alex", "Maya"),
        index=("Alex", "Maya").index(world["selected_salesperson"]),
        key="sim_salesperson",
    )
    world["selected_salesperson"] = selected
    st.markdown(
        '<div class="ib-phone-notch"></div>'
        '<div class="ib-label">SIMULATED WALK · DEMO DATA</div>',
        unsafe_allow_html=True,
    )
    st.caption(f"{CONFERENCE} · {_clock(world)}")
    active_lead = next(
        (
            lead_id
            for lead_id, teammate in world["active_talks"].items()
            if teammate == selected
        ),
        None,
    )
    if active_lead == "sarah":
        st.success("You’re talking with Sarah Chen.")
        st.caption("Conversation started 4 minutes ago · Main hall")
        if world["phase"] == 6 or world["free_explore"]:
            st.button(
                "End talk with Sarah",
                on_click=_act,
                args=("end_talk", "sarah"),
            )
    elif active_lead:
        active_target = _lead_for_id(active_lead)
        st.success(
            f"You’re talking with {active_target['name']}."
            if active_target
            else "You’re in a sample conversation."
        )
        if world["phase"] == 6 or world["free_explore"]:
            st.button(
                f"End talk with {active_target['name'] if active_target else 'lead'}",
                on_click=_act,
                args=("end_talk", active_lead),
            )
    elif (
        world["phone_card"] == "sarah"
        and world["active_talks"].get("sarah")
        and world["active_talks"].get("sarah") != selected
    ):
        st.warning("Sarah is already talking with Alex.")
        st.button(
            "Walk to Sarah · simulated",
            on_click=_act,
            args=("walk_sarah",),
        )
    elif world["phone_card"] == "stop":
        st.error("Stop · Alex is talking with Sarah right now.")
        st.caption("Find another lead before starting a conversation.")
        st.button(
            "Find another lead",
            on_click=_act,
            args=("find_alternate",),
            type="primary",
        )
    elif world["phone_card"] == "private":
        st.info("Attendee (private)")
        st.markdown(f'<div class="ib-chip">{PRIVATE_TOKEN}</div>', unsafe_allow_html=True)
        st.caption("A teammate has not met this person yet.")
    elif world["phone_card"] == "after_talk":
        last_lead = _lead_for_id(world["last_talk_lead"]) or TARGETS[0]
        st.markdown("**After-talk summary · Demo data**")
        if last_lead["id"] == "sarah":
            st.write(
                "Sarah runs a 40-person engineering org, scaling fast; "
                "asked about onboarding time."
            )
        else:
            st.write(
                f"{last_lead['name']} from {last_lead['company']} shared a platform-team priority."
            )
        st.radio(
            "Outcome",
            ("Interested", "Follow up", "Not a fit"),
            key="sim_outcome",
            horizontal=True,
            on_change=lambda: _update_outcome(),
        )
        st.text_area(
            "Follow-up draft · Demo data",
            key="sim_followup",
            value=world["followup_text"],
            on_change=_update_followup,
        )
        st.button(
            "Save outcome",
            type="primary",
            on_click=_act,
            args=("save_outcome",),
            disabled=world["outcome_saved"],
        )
        if world["followup_ready"]:
            st.success("Follow-up draft ready for review · Nothing was sent.")
    elif world["phone_card"] in tuple(lead["id"] for lead in TARGETS):
        lead = _lead_for_id(world["phone_card"])
        if lead:
            st.markdown(f"**{lead['temperature']} · {lead['score']} · {lead['name']}**")
            st.write(f"{lead['role']} · {lead['company']}")
            st.caption("Conference badge details · role, company, session, and opted-in proximity")
            with st.expander("Why reach this lead", expanded=True):
                st.write(lead["why"])
                st.caption(f"Badge signals · {lead['facts']}")
            with st.expander("Public profile · Bright Data", expanded=True):
                st.write(lead["public_profile"])
                st.caption("Demo public signal · no live scrape is performed in this simulation.")
            with st.expander("Team analysis · FalkorDB", expanded=True):
                st.write(lead["graph_insight"])
                st.caption("Graph path: attendee → session → technology focus → teammate coverage")
            st.markdown("**Best opener**")
            st.write(lead["opener"])
            st.button(
                "Start conversation",
                type="primary",
                on_click=_act,
                args=("connect_lead", lead["id"]),
                disabled=bool(world["active_talks"].get(lead["id"])),
            )
    elif not world["targets_built"]:
        st.info("No target list yet · waiting for the team to build one.")
    else:
        st.markdown("**Radar · DevConf 2026**")
        st.caption("5 target leads · 1 hot lead near the hall")
        st.write("● Sarah Chen · HOT · a few steps away")
        st.write("● Tom Alvarez · WARM · available")
        st.write("● Other opted-in attendees · Demo data")
        if world["private_badge"] and world["private_sharing"]:
            st.write(f"● {PRIVATE_TOKEN} · private")
        leads_to_walk = TARGETS if world["free_explore"] else TARGETS[:2]
        for lead in leads_to_walk:
            st.button(
                f"Walk to {lead['name']} · simulated",
                on_click=_act,
                args=("walk_lead", lead["id"]),
                disabled=not world["targets_built"],
                key=f"sim_walk_{lead['id']}",
            )
        if world["private_badge"] and world["private_sharing"]:
            st.button(
                f"Walk to {PRIVATE_TOKEN} · simulated",
                on_click=_act,
                args=("walk_private",),
            )
        if world["phone_card"] == "alternate":
            st.success("Tom Alvarez is an uncovered target.")
def _update_outcome() -> None:
    st.session_state["conference_day_simulation"]["outcome"] = st.session_state[
        "sim_outcome"
    ]
    st.session_state["conference_day_simulation"]["followup_text"] = st.session_state[
        "sim_followup"
    ]


def _update_followup() -> None:
    st.session_state["conference_day_simulation"]["followup_text"] = st.session_state[
        "sim_followup"
    ]


def _render_booth(world: dict[str, Any]) -> None:
    st.markdown("### Booth Dashboard · Nimbus")
    st.caption(f"{CONFERENCE} · Day 1 · {_clock(world)} · Priya")
    st.caption(world["backend_message"])
    if world["phase"] == 3 and not world["targets_built"]:
        st.markdown("**Team setup · Alex and Maya joined**")
        st.caption("Target roles: VP Engineering · Head of Platform · CTO")
        st.caption("Company size: 500+ · Topics: engineering scale, platform, AI tools")
        st.button(
            "Build today's target list",
            type="primary",
            on_click=_act,
            args=("build_targets",),
            use_container_width=True,
        )
    active = world["active_talks"]
    covered = len(active)
    total = len(TARGETS)
    columns = st.columns(2)
    columns[0].metric("Coverage", f"{covered} of {total}")
    columns[1].metric("Double pitches stopped", world["collisions_stopped"])
    columns = st.columns(2)
    columns[0].metric("Meetings happening now", len(active))
    columns[1].metric("Follow-ups ready", int(world["followup_ready"]))
    st.markdown("**Floor view · sample attendees**")
    if not world["targets_built"]:
        st.info("Build today's target list to see the sample floor.")
    else:
        for lead in TARGETS:
            teammate = active.get(lead["id"])
            status = f" · talking with {teammate}" if teammate else " · available"
            st.write(f"● {lead['name']} · {lead['temperature']}{status}")
        for lead_id, name, role, company in BACKGROUND:
            del lead_id
            st.write(f"○ {name} · {role} · {company} · not a target")
        if world["private_badge"] and world["private_sharing"]:
            st.write(f"○ {PRIVATE_TOKEN} · private")
        if world["followup_ready"]:
            st.success("Sarah Chen · follow-up draft ready")
    st.markdown("**Live feed**")
    if world["activity"]:
        for item in world["activity"][:4]:
            st.caption(f"· {item}")
    else:
        st.caption("No activity yet · sample conference")


def render_simulation() -> None:
    world = _world()
    _ensure_graph(world)
    phone_background = "#202E42" if st.session_state.get("dark_mode", False) else "#FFFBEA"
    st.markdown(
        """
        <style>
        .ib-sim-pill { display:inline-block; border-radius:999px; padding:5px 10px;
          background:#FFE500; color:#0B1F3A; border:1px solid #0B1F3A;
          font-size:.76rem; font-weight:900; letter-spacing:.04em; }
        .ib-sim-caption { position:sticky; bottom:0; z-index:50; padding:12px 16px;
          background:#FFFBEA; border:2px solid #0B1F3A; border-radius:14px;
          box-shadow:4px 4px 0 #0B1F3A; }
        .ib-sim-step-active { border:2px solid #F5B73E; background:#FFF4D6;
          color:#0B1F3A; border-radius:12px; padding:8px; text-align:center;
          font-weight:850; }
        .st-key-simulation-caption { position:sticky; bottom:0; z-index:49;
          background:#FFFBEA; padding:8px 4px; }
        .ib-journey-frame { margin:16px 0 20px; padding:16px; background:#FFFDF6; border:2px solid #E2D5B8; border-radius:16px; }
        .ib-journey-stepper { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px; }
        .ib-journey-chip { padding:6px 10px; border-radius:999px; font-size:.78rem; font-weight:800; border:1px solid #E2D5B8; color:#5A6472; background:#F3EAD8; }
        .ib-journey-chip.current { background:#F5B73E; color:#0B1F3A; border-color:#0B1F3A; }
        .ib-journey-chip.done { background:#D8F4EA; color:#00755C; }
        .ib-journey-chip.locked { opacity:.72; }
        .ib-journey-actor { color:#0B1F3A; font-size:1rem; }
        .ib-journey-instruction { margin-top:4px; color:#5A6472; }
        @media (max-width: 1100px) {
          .st-key-sim-stage > [data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"] {
            display:flex; flex-direction:column; gap:1rem;
          }
          .st-key-sim-stage > [data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
            width:100% !important; flex:1 1 100% !important; min-width:100% !important;
          }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<style>.st-key-sim-phone-shell {{ background:{phone_background}; "
        "border:3px solid #0B1F3A; border-radius:30px; padding:16px; "
        "box-shadow:8px 8px 0 #2440FF; }}</style>",
        unsafe_allow_html=True,
    )
    st.markdown("## Inference Badge · Conference day")
    st.markdown(
        '<span class="ib-sim-pill">SIMULATION · Demo conference · No real data</span>',
        unsafe_allow_html=True,
    )
    _journey_frame(world)
    controls = st.columns([1, 1, 1])
    controls[0].toggle(
        "Free Explore",
        key="sim_free_explore",
        value=world["free_explore"],
    )
    world["free_explore"] = st.session_state["sim_free_explore"]
    reset_confirmed = True
    mid_run = 1 < world["phase"] < 6 and not world["run_complete"] and not world["free_explore"]
    if mid_run:
        reset_confirmed = controls[1].checkbox("Confirm reset", key="sim_confirm_reset")
    reset_clicked = controls[1].button(
        "Reset",
        disabled=not reset_confirmed,
        use_container_width=True,
    )
    controls[2].button(
        "Exit",
        on_click=lambda: st.session_state.update({"page": "Marketing"}),
        use_container_width=True,
    )
    if reset_clicked:
        _act("reset")
        st.rerun()
    st.progress(
        world["phase"] / 6,
        text=f"Phase {world['phase']} of 6 · {('Organiser setup', 'Attendee choices', 'Team target list', 'Live floor', 'Privacy', 'Follow-up and results')[world['phase'] - 1]}",
    )

    with st.container(key="sim-stage"):
        conference, phone, booth = st.columns([1.12, 1, 1.12], gap="medium")
        with conference:
            _render_conference(world)
        with phone:
            _render_phone(world)
        with booth:
            _render_booth(world)

    if world["phase"] == 1 and world["plugin_active"]:
        ready = True
    else:
        ready = _phase_complete(world)
    with st.container(key="simulation-caption"):
        st.markdown(
            f'<div class="ib-sim-caption"><div class="ib-label">SIMULATION · {_clock(world)}</div>'
            f'<strong>{_phase_caption(world)}</strong></div>',
            unsafe_allow_html=True,
        )
        if world["run_complete"]:
            st.success(
                "That’s Inference Badge: conferences plug it in, attendees choose, "
                "and teams stop double-pitching and follow up while it’s warm."
            )
            again, explore = st.columns(2)
            again.button("Run it again", on_click=_act, args=("reset",), use_container_width=True)
            explore.button(
                "Explore freely",
                on_click=_act,
                args=("free_explore",),
                use_container_width=True,
            )
        elif world["phase"] < 6:
            if world["free_explore"]:
                st.button(
                    "Next phase",
                    on_click=_act,
                    args=("next_phase",),
                    disabled=not ready and not world["free_explore"],
                    type="primary",
                    use_container_width=True,
                )
            else:
                if world["phase"] in (2, 4, 5) and not ready:
                    st.caption(
                        "Use the highlighted action in the panels above, then continue."
                    )
                st.button(
                    "Next",
                    on_click=_act,
                    args=("next_phase",),
                    disabled=not ready,
                    type="primary",
                    use_container_width=True,
                )
        elif not world["outcome_saved"]:
            st.button(
                "Finish the conference day",
                on_click=_act,
                args=("finish",),
                disabled=not ready,
                type="primary",
                use_container_width=True,
            )
        else:
            st.button(
                "Finish the conference day",
                on_click=_act,
                args=("finish",),
                type="primary",
                use_container_width=True,
            )
        with st.expander("How did that work?"):
            st.write(EXPLANATIONS[world["phase"] - 1])
            steps = st.columns(4)
            for col, item in zip(
                steps,
                (
                    "Badge senses",
                    "Sign-up list checked",
                    "Team memory checked",
                    "Prompt / follow-up written",
                ),
            ):
                index = steps.index(col)
                active_step = (
                    (world["phase"] in (1, 2) and index == 1)
                    or (world["phase"] == 3 and index in (1, 2))
                    or (world["phase"] == 4 and index in (0, 2))
                    or (world["phase"] == 5 and index == 0)
                    or (world["phase"] == 6 and index == 3)
                )
                css_class = "ib-sim-step-active" if active_step else "ib-proof"
                col.markdown(f'<div class="{css_class}">{item}</div>', unsafe_allow_html=True)
            if world["backend"] == "FalkorDB":
                st.caption(
                    "FalkorDB holds this run’s shared sample memory. Bright Data and OpenAI are not called; "
                    "company facts, prompts, and drafts use demo text."
                )
            else:
                st.caption(
                    "FalkorDB is unavailable, so this run uses an in-memory session graph. "
                    "Bright Data and OpenAI are not called; company facts, prompts, and drafts use demo text."
                )
    url_state = {key: value for key, value in world.items() if key != "followup_text"}
    st.query_params["ib_simulation"] = json.dumps(url_state, separators=(",", ":"))
