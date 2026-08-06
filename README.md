# Crypto Screening & DCA System — Phase 1 (Data Pipeline)

## What this is, right now

Phase 1 only: connectors to five free data sources, plus one
orchestrator (`pipeline.py`) that pulls all of them for a single
token and returns one consolidated, clearly-labeled record.

**This phase does not score, filter (beyond the hard-filter
pass/fail check), classify by narrative, or generate any dashboard
output yet.** Those are phases 2–4. Building this in order matters —
scoring logic built on top of unverified data is worse than no
scoring logic at all.

## What's covered

| Source | Covers | Auth needed |
|---|---|---|
| CoinGecko | price, market cap, FDV, supply, category tags | none (optional free demo key raises rate limit) |
| DexScreener | liquidity depth, pair count | none |
| GoPlus | honeypot, mint status, ownership, top-10 holders | none |
| Blockscout | detailed holder list, per chain | none |
| DeFiLlama | TVL trend (alts with a tracked protocol) | none |

Every connector fails independently — if one source is down or a
token isn't listed there, the record notes it under `errors` rather
than the whole pull failing or silently defaulting to a "safe" value.
This matters most in `goplus.py`: missing safety data is treated as a
**filter failure**, never a silent pass.

## What I could not verify from here

This was built and syntax-checked in a sandboxed environment with no
access to the live internet beyond a small set of developer-infra
domains (PyPI, GitHub, etc.) — confirmed directly: a test request to
CoinGecko returned a blocked response, not a real API response. So
this code is structurally sound and internally consistent, but the
actual live API calls have not been run against the real endpoints.
First real deployment needs a live smoke test — run
`python pipeline.py` from an environment with normal internet access
and confirm the output looks right before phase 2 builds on top of it.

## Path to "runs daily, hands you output, zero code interaction"

This part needs a one-time setup, not ongoing involvement:

1. A free GitHub account (if you don't have one) and a private repo
   with this code.
2. GitHub Actions (free for this workload) configured to run the
   pipeline daily on a schedule.
3. Phases 2–4 (scoring, filters/alerts, dashboard generation) get
   built on top of this and wired into the same scheduled job.
4. Output gets published somewhere you just open — most likely
   GitHub Pages (free static hosting) for the generated dashboard.

None of this requires you to touch code day-to-day once it's set up —
but the initial repo/Actions setup is a real step that has to happen
before "daily, no interaction" is true. Let me know when you're ready
for that part and I'll walk it through concretely.
