# Inference Badge — Streamlit prototype

This is a laptop-stage prototype based on `README.md`, `Design.md`, `Skills.md`,
`agents.md`, and `Mock_Data.cypher`.

## Run locally

```bash
docker run --name inference-badge-db -p 6379:6379 -d falkordb/falkordb
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Export any credentials you want to use in this terminal:
export OPENAI_API_KEY="..."
export BRIGHT_DATA_API_TOKEN="..."
export BRIGHT_DATA_WEB_UNLOCKER_ZONE="..."
streamlit run app.py
```

Open the local URL Streamlit prints (usually http://localhost:8501), then click
**Initialize demo data** in the sidebar.

## Important implementation notes

- The dashboard uses the node labels, relationship names, and core properties in
  the supplied seed/schema files. It preserves existing `Company.tier` values.
- It intentionally does not run the seed file's destructive `MATCH (n) DETACH
  DELETE n` statement. Demo setup uses `MERGE` and is safe to run repeatedly.
- Check-ins from the sidebar are simulated dashboard events, not actual BLE/UWB
  scans or a mobile agent.
- Bright Data is optional. The included adapter uses the Bright Data Web Unlocker
  HTTP API when a token and zone are configured; it is not a generic MCP client.
  To use the Bright Data MCP server specifically, connect its documented tools
  in a separate worker and call that worker from `enrichment.py`. No live scrape
  is claimed when credentials are absent.
- OpenAI is optional. Without `OPENAI_API_KEY`, a deterministic, evidence-labeled
  briefing is displayed. The OpenAI path uses the chat completions SDK.
- Public web content is treated as untrusted evidence. Do not use scraped data to
  infer sensitive personal attributes or to deanonymize privacy-shielded attendees.
- For a real deployment, add authentication, network restrictions, observability,
  rate limits, and explicit retention/consent controls before exposing this app
  beyond a trusted demo laptop.
