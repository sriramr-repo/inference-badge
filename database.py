"""FalkorDB access layer for Inference Badge.

Uses the graph schema and property names defined in Design.md and Mock_Data.cypher.
Never clears or reseeds an existing graph automatically.
"""
from __future__ import annotations

import os
import time
from functools import lru_cache
from typing import Any

from falkordb import FalkorDB


class DatabaseError(RuntimeError):
    """Raised when FalkorDB cannot be reached or a query fails."""


def _connection_settings() -> dict[str, Any]:
    return {
        "host": os.getenv("FALKORDB_HOST", "localhost"),
        "port": int(os.getenv("FALKORDB_PORT", "6379")),
        "password": os.getenv("FALKORDB_PASSWORD") or None,
        "username": os.getenv("FALKORDB_USERNAME") or None,
        "socket_timeout": float(os.getenv("FALKORDB_SOCKET_TIMEOUT", "3")),
    }


@lru_cache(maxsize=1)
def get_graph():
    """Return the selected FalkorDB graph. Cached per Streamlit process."""
    settings = _connection_settings()
    kwargs = {k: v for k, v in settings.items() if v is not None}
    try:
        db = FalkorDB(**kwargs)
        return db.select_graph(os.getenv("FALKORDB_GRAPH", "inference_badge"))
    except Exception as exc:
        raise DatabaseError(
            "Could not connect to FalkorDB. Confirm Docker is running and "
            "FALKORDB_HOST/FALKORDB_PORT are correct."
        ) from exc


def run_query(cypher: str, params: dict[str, Any] | None = None, retries: int = 1):
    """Execute a parameterized Cypher query with a small bounded retry."""
    last_error = None
    for attempt in range(retries + 1):
        try:
            graph = get_graph()
            return graph.query(cypher, params or {})
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(0.15 * (attempt + 1))
    raise DatabaseError(f"FalkorDB query failed: {last_error}") from last_error


def rows(cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    result = run_query(cypher, params)
    columns = list(getattr(result, "header", []) or [])
    data = list(getattr(result, "result_set", []) or [])
    if not columns and data:
        # FalkorDB clients generally expose header as column descriptors.
        columns = [str(x) for x in getattr(result, "header", [])]
    names = []
    for col in columns:
        names.append(str(getattr(col, "name", col)))
    return [dict(zip(names, row)) for row in data]


def health_check() -> tuple[bool, str]:
    try:
        run_query("RETURN 1 AS ok", retries=0)
        return True, "Connected"
    except Exception as exc:
        return False, str(exc)


def seed_demo_data() -> tuple[bool, str]:
    """Idempotently add demo nodes/edges without deleting existing graph data.

    This intentionally does not execute Mock_Data.cypher's destructive
    MATCH (n) DETACH DELETE n statement or overwrite existing tier values.
    """
    statements = [
        """MERGE (a:TeamMember {name:'Alice'})
           ON CREATE SET a.role='Sales Engineer', a.focus='AI Infra'""",
        """MERGE (b:TeamMember {name:'Bob'})
           ON CREATE SET b.role='Product Manager', b.focus='Graph Databases'""",
        """MERGE (c:Company {name:'Stripe'})
           ON CREATE SET c.tier='Enterprise Tier 1', c.marketCapOrFunding='$70B Valuation',
                         c.employeeCount='8,000+', c.scrapedViaBrightData=true""",
        """MERGE (c:Company {name:'Vercel'})
           ON CREATE SET c.tier='Enterprise Tier 1', c.marketCapOrFunding='$3.2B Valuation',
                         c.employeeCount='1,000+', c.scrapedViaBrightData=true""",
        """MERGE (s:Session {id:'sess_1'})
           ON CREATE SET s.title='Scaling Autonomous Agents with Connected Context',
                         s.room='Hub A', s.time='13:00'""",
        """MERGE (s:Session {id:'sess_2'})
           ON CREATE SET s.title='Next-Gen Frontend Architectures',
                         s.room='Stage 3', s.time='14:30'""",
        """MERGE (t:Technology {name:'FalkorDB'})
           ON CREATE SET t.category='Graph Databases'""",
        """MERGE (t:Technology {name:'Next.js'})
           ON CREATE SET t.category='Frontend Frameworks'""",
        """MATCH (s:Session {id:'sess_1'}), (t:Technology {name:'FalkorDB'})
           MERGE (s)-[:FOCUSES_ON]->(t)""",
        """MATCH (s:Session {id:'sess_2'}), (t:Technology {name:'Next.js'})
           MERGE (s)-[:FOCUSES_ON]->(t)""",
        """MERGE (l:Lead {id:'PROX_PING_111'})
           ON CREATE SET l.name='Sarah', l.company='Stripe',
             l.captureMethod='Phone_Auto_Proximity', l.locationShared=true, l.status='Hot Prospect'""",
        """MATCH (c:Company {name:'Stripe'}), (l:Lead {id:'PROX_PING_111'}),
                    (s:Session {id:'sess_1'})
           MERGE (c)-[:EMPLOYS]->(l) MERGE (l)-[:ATTENDING]->(s)""",
        """MATCH (a:TeamMember {name:'Alice'}), (l:Lead {id:'PROX_PING_111'})
           MERGE (a)-[r:MET]->(l)
           ON CREATE SET r.timestamp='11:15', r.tracking='Location_Handshake'""",
        """MERGE (l:Lead {id:'ENCRYPTED_HASH_99X'})
           ON CREATE SET l.name='Anonymous Attendee', l.company='Vercel',
             l.captureMethod='Phone_Privacy_Shield', l.locationShared=false, l.status='Contacted'""",
        """MATCH (c:Company {name:'Vercel'}), (l:Lead {id:'ENCRYPTED_HASH_99X'}),
                    (s:Session {id:'sess_2'})
           MERGE (c)-[:EMPLOYS]->(l) MERGE (l)-[:ATTENDING]->(s)""",
        """MATCH (a:TeamMember {name:'Alice'}), (l:Lead {id:'ENCRYPTED_HASH_99X'})
           MERGE (a)-[r:MET]->(l)
           ON CREATE SET r.timestamp='11:20', r.tracking='Hash_Proximity_Only'""",
    ]
    try:
        for statement in statements:
            run_query(statement)
        return True, "Demo data is ready. Existing company tier values were preserved."
    except Exception as exc:
        return False, str(exc)


def list_leads() -> list[dict[str, Any]]:
    cypher = """
    MATCH (l:Lead)
    OPTIONAL MATCH (c:Company)-[:EMPLOYS]->(l)
    OPTIONAL MATCH (tm:TeamMember)-[m:MET]->(l)
    OPTIONAL MATCH (l)-[:ATTENDING]->(s:Session)
    OPTIONAL MATCH (s)-[:FOCUSES_ON]->(t:Technology)
    RETURN l.id AS id, l.name AS name, l.company AS company,
           l.captureMethod AS captureMethod, l.locationShared AS locationShared,
           l.status AS status, c.tier AS tier, c.marketCapOrFunding AS funding,
           c.employeeCount AS employees, c.scrapedViaBrightData AS enriched,
           tm.name AS teammate, tm.role AS teammateRole, m.timestamp AS metAt,
           m.tracking AS tracking, s.title AS session, s.room AS room,
           s.time AS sessionTime, t.name AS technology
    ORDER BY metAt DESC
    """
    return rows(cypher)


def lead_context(lead_id: str) -> dict[str, Any] | None:
    result = rows("""
    MATCH (l:Lead {id:$lead_id})
    OPTIONAL MATCH (c:Company)-[:EMPLOYS]->(l)
    OPTIONAL MATCH (tm:TeamMember)-[m:MET]->(l)
    OPTIONAL MATCH (l)-[:ATTENDING]->(s:Session)-[:FOCUSES_ON]->(t:Technology)
    RETURN l.id AS id, l.name AS name, l.company AS company,
           l.captureMethod AS captureMethod, l.locationShared AS locationShared,
           l.status AS status, c.tier AS tier, c.marketCapOrFunding AS funding,
           c.employeeCount AS employees, c.scrapedViaBrightData AS enriched,
           tm.name AS teammate, tm.role AS teammateRole, tm.focus AS teammateFocus,
           m.timestamp AS metAt, m.tracking AS tracking,
           s.title AS session, s.room AS room, s.time AS sessionTime,
           t.name AS technology
    LIMIT 1
    """, {"lead_id": lead_id})
    return result[0] if result else None


def create_demo_handshake(name: str, company: str, teammate: str, location_shared: bool):
    """Create a simulated check-in. This is not a real BLE/UWB scanner."""
    lead_id = f"DEMO_{int(time.time() * 1000)}"
    safe_name = name.strip() if location_shared else "Anonymous Attendee"
    if not safe_name:
        raise ValueError("Enter a name when location sharing is enabled.")
    run_query("""
    MERGE (l:Lead {id:$id})
    SET l.name=$name, l.company=$company,
        l.captureMethod=$capture_method, l.locationShared=$shared,
        l.status='New proximity check-in'
    WITH l
    MATCH (tm:TeamMember {name:$teammate})
    MERGE (tm)-[m:MET]->(l)
    SET m.timestamp=$timestamp, m.tracking=$tracking
    WITH l
    MERGE (c:Company {name:$company})
    ON CREATE SET c.tier='Unclassified', c.scrapedViaBrightData=false
    MERGE (c)-[:EMPLOYS]->(l)
    RETURN l.id AS id
    """, {
        "id": lead_id, "name": safe_name, "company": company.strip(),
        "capture_method": "Demo_Proximity_Checkin" if location_shared else "Phone_Privacy_Shield",
        "shared": bool(location_shared), "teammate": teammate,
        "timestamp": time.strftime("%H:%M:%S"),
        "tracking": "Location_Handshake" if location_shared else "Hash_Proximity_Only",
    })
    return lead_id


def update_company_enrichment(company: str, data: dict[str, Any], source: str):
    """Write only returned enrichment fields; never mutate tier unless explicitly provided."""
    # `tier` is seed-controlled and intentionally immutable in enrichment.
    allowed = {
        "marketCapOrFunding": "marketCapOrFunding",
        "employeeCount": "employeeCount",
        "techStack": "techStack",
        "recentTechStackUpdate": "recentTechStackUpdate",
        "companySize": "companySize",
        "fundingStage": "fundingStage",
    }
    clean = {key: str(data[key]) for key in allowed if key in data and data[key] not in (None, "")}
    params = {"company": company, "source": source}
    for key, value in clean.items():
        params[key] = value
    assignments = [f"c.`{key}` = ${key}" for key in clean]
    assignments += ["c.scrapedViaBrightData = true", "c.enrichmentSource = $source",
                    "c.enrichedAt = $enriched_at"]
    params["enriched_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    run_query(
        "MERGE (c:Company {name:$company}) ON CREATE SET c.tier='Unclassified' "
        "SET " + ", ".join(assignments),
        params,
    )
