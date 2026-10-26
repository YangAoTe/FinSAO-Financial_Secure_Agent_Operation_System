# P4 — Frontend Integration and Demo / 中文联调前端

## Delivered

`frontend/` is a React + TypeScript + Vite application using same-origin development
proxies for Banking Core (`:8000`) and Agent (`:8100`). The UI obtains identity,
accounts, balances, beneficiaries, risk tier, approval and task state only from the
services. It does not contain a user UUID, account UUID, beneficiary UUID, fabricated
receipt or client-selected risk tier.

The implemented demonstration path includes:

- responsive Chinese desktop and mobile shells;
- Core-backed overview, balances, budgets/subscriptions/cards/product counts;
- a transfer form that creates an Agent task and stops at the Core approval boundary;
- task DAG, argument provenance, status, refresh, cancel, takeover, Yellow confirmation,
  Red MFA and post-resume result handling;
- a persistent assistant entry with voice clearly disabled as a preview;
- an experiment dashboard that reads generated files under `evaluation/` and renders
  missing cost as “未提供”.

## Contracts and safety

All requests are centralized in `src/api.ts`, use snake_case JSON, add a UUID trace ID,
and surface non-2xx responses. Vite proxies are explicit; no wildcard CORS was added.
Authorization references exist only in component memory between approval and resume.
The UI displays `COMPLETED` only after the Agent/Core response says so.

The current demo uses JavaScript numeric formatting only for display. Financial truth
and arithmetic remain in Core `Decimal`/PostgreSQL `NUMERIC`; no browser calculation is
submitted as authoritative state.

## Verification and usability evidence

Commands:

```powershell
cd frontend
npm test
npm run build
npm run test:e2e
```

Vitest covers the safe shell and disabled voice affordance. Playwright runs actual
Chromium against the three live local services. The desktop scenario reads two real
seeded accounts, creates a CNY 1.00 transfer draft, observes `WAITING_APPROVAL` and the
Core risk tier, and verifies the plan step. The Pixel 7 scenario verifies the assistant,
all mobile navigation destinations and the live evidence dashboard.

The first mobile run failed because CSS hid destinations six and seven. That finding
was retained in this report; the navigation was changed to seven equally sized,
accessible buttons and the rerun passed. Raw report:
`evaluation/reports/p4_playwright.json`; compact evidence:
`p4_usability_summary.json` and `p4_usability_runs.csv`; visual evidence:
`evaluation/figures/p4_desktop-chromium.png` and
`evaluation/figures/p4_mobile-chromium.png`.

## Honest limitations

This phase establishes the competition demo’s core safe loop, not every product page.
Detailed transaction filtering/category correction, rich budget/card/wealth mutations,
chat-based step editing, approval rejection/expiry, and unknown-outcome browser fixtures
remain follow-up coverage. Voice and savings pots are visibly unavailable/planned. A
browser exposed through the interactive Computer Use layer was unavailable in this
environment, so repeatable Playwright Chromium—not a claimed manual Edge session—is the
browser evidence.
