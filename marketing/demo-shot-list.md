# Comply — 2–3 minute demo shot list

A tight, repeatable walkthrough of the core value loop, recorded against the
seeded demo. The whole point is to show **red → green driven by evidence**, with
plain-language gaps in between.

## Before you record

1. Start the stack: `docker compose up -d`, backend on `:8000`, frontend on `:5173`.
2. Seed the realistic scenario: `python scripts/seed_demo.py`
   - Login: `demo@comply.dev` / `ComplyDemo123`
   - It prints the seeded system URL (a HIGH-risk **Resume Screener** at ~67%).
3. Browser at 1280×800, zoom 100%, no extensions/bookmarks bar visible.
4. Have the System Detail page pre-loaded but not scrolled, signed in.

Total target length: **2:30**. Keep the cursor deliberate; pause ~1s after each click.

---

## Shot 1 — The stakes (0:00–0:20)

**On screen:** Title card, then the Dashboard showing the Resume Screener.
**Narration:**
> "The EU AI Act makes high-risk AI — like tools that screen job applicants —
> prove they're compliant. Get it wrong and fines reach 15 million euros or 3%
> of global turnover. Comply turns the evidence your AI already produces into
> that proof."

## Shot 2 — Where you stand, at a glance (0:20–0:45)

**Action:** Open the Resume Screener. Let the summary cards and control table render.
**On screen:** Score **67%**, the SATISFIED/PARTIAL/MISSING counts, the control list
with green and red status pills.
**Narration:**
> "This is a real system's posture. Sixty-seven percent compliant. Every control
> in the EU AI Act, scored against actual evidence — not a questionnaire."

## Shot 3 — Why a control fails, in plain English (0:45–1:15)

**Action:** Click a red control — **DOC_003, "Declaration of Conformity Generated."**
Let the row expand.
**On screen:** The plain-language remediation:
> *Missing a document for declaration of conformity. — No evidence of "declaration
> of conformity" has been provided yet. — Next: Add a document demonstrating
> declaration of conformity.*
**Narration:**
> "Click any gap and it tells you what's missing, why, and what to do next — in
> plain language. The raw audit reason is right there underneath for your
> engineers. No consultant required to read it."

## Shot 4 — The money loop: evidence flips the control (1:15–2:05)

**Action:** Pick a control whose evidence type is easy to satisfy (e.g. a TELEMETRY
control — **LOG_002** or **HUMAN_002**), expand it, click **Add evidence**.
In the modal, keep the prefilled type/source, click **Add evidence & re-assess.**
**On screen:** Modal closes, assessment re-runs, the control flips **red → green**,
the toast shows `… : MISSING → SATISFIED`, the score ticks up.
**Narration:**
> "Here's the loop that matters. Add the evidence — a runtime trace, a signed
> policy, a config record — and Comply re-assesses instantly. The control goes
> green, the score moves, and every result is reproducible and audit-logged."

## Shot 5 — Why it's trustworthy (2:05–2:30)

**On screen:** Slowly scroll the control table; rest on the mix of green/red.
**Narration:**
> "Every score traces back to a specific piece of evidence, with a tamper-evident
> audit trail. Deterministic, explainable, defensible. That's the difference
> between a compliance database and a conformity artifact."
**End card:** Logo + one line + CTA (e.g. "Pilot the EU AI Act module — [email]").

---

## Cutdown (60-second version)

Use **Shot 1** (0:00–0:12, trimmed) → **Shot 2** (score) → **Shot 4** (the flip) →
**End card.** The red→green flip is the single most important 15 seconds; never cut it.

## Recording notes

- The transition toast lasts ~5s — don't rush past the flip in Shot 4.
- If you want a clean slate between takes, re-run `seed_demo.py` for a fresh system.
- Avoid showing the `change-me-in-production` JWT warning in any terminal on screen.
- Optional B-roll: the Day-0 empty-state onboarding (create a second org) to show
  the "create your first system" first-run experience.
