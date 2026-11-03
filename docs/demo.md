# Demo Data & Demo Script

## Synthetic demo dataset

`app/services/demo_service.py` (CLI: `scripts/seed_demo.py`, API:
`POST /api/demo/ensure`, UI: "Load demo workspace" on the home page)
generates a synthetic repository history (no network access required, no
GitHub credentials needed) with these deliberately engineered properties:

- **Team** — 10 developers: Rahul, Priya, Akash, Bob, Divya, Kiran, Meera,
  Arjun, Sana, Vikram.
- **Modules (8)** — `payment`, `billing`, `checkout`, `auth`,
  `notifications`, `reporting`, `search`, `deployment`.
- **`payment` module** — high risk: concentrated commits from one developer
  (`Rahul`, ~80%+ knowledge share), sparse documentation, high complexity
  files, frequent recent changes, and downstream dependents (`billing`,
  `checkout`, `notifications`) so risk propagation has somewhere to go.
- **`search` module** — second bus-factor-1 area: `Vikram` owns ~90% of the
  ranking code, with `Sana` as the only backup candidate.
- **`auth` module** — low risk: knowledge spread across 6+ developers, good
  documentation coverage, low change frequency.
- **`reporting` module** — healthy shared ownership (`Divya` + `Sana`) with
  good docs; depends on both `billing` and `checkout` (diamond dependency).
- **Hidden secondary expert** — a developer (`Priya`) with low commit share
  on `payment` but prior work in `billing` (a related, dependent module) —
  surfaces via the hidden-expert algorithm rather than raw commit count, and
  is ranked as the top backup candidate for `payment`.
- **Documentation gaps** — `deployment` module intentionally has minimal
  README/comment coverage despite moderate complexity.
- **Module dependency graph** — `payment → billing → checkout`,
  `payment → notifications`, `billing → notifications`,
  `billing + checkout → reporting`, `auth + reporting → search`; every edge
  is a real `from src.… import …` statement the import resolver detects, and
  drives the risk-propagation tree on the Simulation page.
- **Historical knowledge drift** — `payment`'s concentration is generated as
  a rising series over several months so the drift detector has a genuine
  trend to flag.

Every field in the UI is explicitly labeled "Demo data (synthetic)" when a
project was created from the seed path, so it's never mistaken for a real
analysis. The demo bootstrap is idempotent: `POST /api/demo/ensure`
(reused by the seed script) returns the existing fully-analyzed demo project
when one is available instead of creating duplicates, and never touches
non-demo projects — so the demo workspace is always one click away.

## Demo script (acceptance scenario)

1. Open the home page → **Load demo workspace** (or `python scripts/seed_demo.py`).
2. Open dashboard → project resilience score, `payment` (and `search`) listed
   as top risk modules.
3. Open Module page for `payment` → concentrated knowledge, bus factor 1,
   factor breakdown visible.
4. Simulation page → select `Rahul` → Run. Results: resilience drops,
   affected modules listed, **risk propagation tree** shows impact radiating
   `payment → billing → checkout` (with decay per hop), backup candidates
   ranked with `Priya` surfaced with compatibility score and *why*.
5. Recommendations page → CRITICAL: assign secondary owner to `payment`;
   HIGH: document `deployment`.
6. AI Analyst → ask "Why is Payment the highest-risk module?" → answer cites
   the exact stored metrics, not invented figures.
