# Inference Badge — local prototype

Inference Badge explores how conference sales teams can coordinate around
attendees who opt in at sign-up. This Streamlit prototype combines a product
overview, a phone-shaped interaction preview, a five-step presenter demo, and a
FalkorDB-backed booth dashboard.

## Run locally

```bash
docker run --name inference-badge-db -p 6379:6379 -d falkordb/falkordb
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py --server.address 127.0.0.1 --server.port 8502
```

The app uses `FALKORDB_HOST=127.0.0.1`, `FALKORDB_PORT=6379`, and graph
`inference_badge` by default. Override these with environment variables for a
different local setup. Optional OpenAI and Bright Data integration settings are
listed in `.env.example`; the app reads environment variables and does not load
`.env` automatically.

Open `http://127.0.0.1:8502`. The sidebar has three choices:

- **Marketing** — one scrolling product page.
- **Conference setup** — an interactive, demo-only organizer-to-attendee
  sign-up simulation showing how an attendee can opt in or keep their badge private.
- **Business demo** — one business-facing demo with tabs for the guided
  90-second story, the phone app prototype, and the booth dashboard.
- **Conference day simulation** — a guided six-phase, sample conference-day
  experience for organizers, attendees, and an exhibitor team, with an optional
  Free Explore mode.
- **Log in / Create account** — Coming soon placeholders; authentication is
  not implemented.

The business demo keeps the phone experience and team view together instead of
presenting them as separate destinations.
Use the icon-enabled sidebar page buttons to navigate and the **Dark mode**
switch for a navy/slate palette with light text, gold actions, and brighter,
contrast-adjusted blue, teal, orange, and pink accents. Badge-style line icons
also label feature cards and the FalkorDB, Bright Data, and OpenAI integrations.
FalkorDB’s live connection and graph controls are found in the **Business demo
→ Booth dashboard** tab.

## Demo behavior and limits

- The business demo keeps the guided 90-second story, phone app preview, and
  booth dashboard together. The guided story is session-only and uses clearly
  labeled sample people. Its **Next** button completes every step without
  requiring drag or form interaction.
- Conference setup is a conceptual walkthrough; its interactive sign-up
  simulation does not connect to or change a real conference flow and does not
  save attendee choices.
- The Conference day simulation uses demo people and simulated proximity. When
  FalkorDB is available, each run is isolated with a unique run ID in the
  separate `InferenceBadgeGraph`; Reset removes only that run's sample nodes.
  If it is unavailable, the identical interaction state uses the in-memory
  session graph. Demo progress is saved in the page URL and restored when the
  simulation is reopened after a refresh. The editable follow-up draft is
  deliberately excluded from the URL; it returns to the sample draft after a
  refresh.
- Demo check-ins and proximity are simulated. They are not BLE/UWB scans.
- The phone privacy controls are previews; there is no real device permission,
  identity, location, QR, or retention service.
- The early-access form stores an email in a dedicated `EarlyAccessSignup`
  node in the configured FalkorDB graph only after explicit opt-in. It
  normalizes addresses for duplicate prevention, does not expose the list in
  the app, and does not send email. Ensure the backend is private and access
  controlled before collecting real addresses.
- Follow-up text is a draft only and is never sent.
- The website, phone UI, and booth view are presentation surfaces inside
  Streamlit, not a production marketing site or native mobile application.
- FalkorDB stores shared graph context when connected. The app never clears the
  graph automatically. Use **Initialize demo data** only when you explicitly
  want the sample nodes and links added; it uses `MERGE`.
- OpenAI is optional. Without credentials, a deterministic three-bullet
  evidence-labeled brief is displayed.
- Bright Data is optional. The adapter uses the Bright Data Web Unlocker HTTP
  API when configured; it is not a generic MCP client. Without credentials, no
  live request is performed.
- Seeded company facts are demo examples, not live research. Public web content
  is treated as untrusted evidence. Do not use scraped data to infer sensitive
  personal attributes or deanonymize privacy-shielded attendees.

This is a hackathon prototype. Login and registration, production consent and
retention controls, real proximity capture, mailing-list delivery, and secure
deployment are not implemented.
