# UI Plan — Drag-and-Drop Backtesting Platform

This doc is UI-first: it focuses on getting a usable, coherent product experience in the frontend even while backend backtesting endpoints are still evolving.

## 0) Status (Updated 2026-01-08)

### Done
- `/app` scaffold + shared layout shell (`AppShell`) with nav.
- Builder MVP: drag blocks onto canvas, move blocks, connect blocks (directed edges with `sourceHandle`/`targetHandle`), inspector editing.
- Demo template: `SMA(10) > SMA(50)` flow (`OnBar → SMA10/SMA50 → IfAbove → Buy/Sell`).
- Canvas navigation: pan + zoom + reset.
- Builder validation: visible error list + per-block issues; “Run” disabled until the flow is valid.
- Export/Import strategy JSON (copy/download + paste import) to share graphs and align UI→backend payload.
- Save/Load Draft (localStorage) and real “Duplicate in Builder” flow from results.
- Mock run + mocked results page reads stored `graph` (nodes + edges) and shows basic KPIs + placeholders.
- Locale + tooling stability fixes (lucide import, valid `zh.json`, dev/check commands).
- Edge rendering fix: allow SVG overflow so arrows aren’t clipped at canvas edges.

### Next (UI-only, backend-friendly)
1) Typed ports expansion (`boolean`, `series`, etc) + more condition nodes (e.g. Cross Above).
2) Results page upgrades: show run config snapshot + add basic equity/trades mock data (until backend wires real outputs).
3) Backtest history page: list saved runs/drafts (UI-only now; later from backend).

## 1) Current State (What’s Already Done)

### Development notes (to avoid startup/tooling errors)
- If your terminal `cwd` is `frontend/`, run `npm run dev` / `npm run check` (don’t add `-C frontend`).
- If your terminal `cwd` is repo root, run `npm -C frontend run dev` / `npm -C frontend run check`.
- If you see `Cannot find package '@sveltejs/adapter-auto'`, install frontend deps first: `cd frontend && npm install`.
- Locale JSON files must be valid JSON (empty `zh.json` can break startup when the browser locale is `zh`).
- Lucide icons in this repo should be imported from `@lucide/svelte` (not `lucide-svelte`) to match the installed packages.

### Theme + colors (change once, reuse everywhere)
This frontend is set up with shadcn-style **semantic design tokens** (CSS variables) so we don’t hardcode colors per-component.

- Source of truth: `frontend/src/routes/layout.css`
  - Light mode tokens are under `:root` (e.g. `--primary`, `--background`, `--muted-foreground`).
  - Dark mode overrides are under `.dark`.
- How to use in UI: prefer semantic Tailwind classes that map to tokens:
  - Backgrounds: `bg-background`, `bg-card`, `bg-muted`, `bg-accent`
  - Text: `text-foreground`, `text-muted-foreground`
  - Borders: `border-border`, inputs `border-input`
  - Brand/CTA: `bg-primary text-primary-foreground`, focus ring `ring-ring`
- Rule of thumb: don’t use `text-blue-500`/`bg-red-500` etc for product UI unless it’s truly semantic (e.g. errors). If you stick to token-based classes, re-theming is usually a `layout.css` edit only.

### Repo shape
- `frontend/`: SvelteKit (Svelte 5) + Tailwind v4 + shadcn-svelte components.
- `backend/`: FastAPI backend with authentication endpoints (register/login/verify/me). No backtest API routes yet.

### Frontend: foundations
- Global layout initializes i18n and blocks rendering until the locale is ready: `frontend/src/routes/+layout.svelte`.
- Tailwind + shadcn theme tokens wired via `frontend/src/routes/layout.css`.
- shadcn components exist under `frontend/src/lib/components/ui/*` (button/card/input/checkbox/label/etc).
- Toast notifications via `svelte-sonner` are in use.

### Frontend: routes that exist today
- `/` is still the Svelte template placeholder: `frontend/src/routes/+page.svelte`.
- `/home` exists as a temporary hub page: `frontend/src/routes/home/+page.svelte`.
- Auth UI:
  - `/login` has a fairly complete UI (shadcn + lucide icons + i18n strings): `frontend/src/routes/login/+page.svelte`.
  - `/forget-password` has a polished UI and uses a mocked `resetPassword()` util: `frontend/src/routes/forget-password/+page.svelte`.
  - `/signup` has the surrounding Card layout, but the actual form is stubbed: `frontend/src/routes/signup/SignupForm.svelte`.
- Backtest UI:
  - `/backtest/input` is a simple HTML form and server action that simulates a `job_id` and redirects: `frontend/src/routes/backtest/input/+page.svelte`, `frontend/src/routes/backtest/input/+page.server.ts`.
  - `/backtest/results` currently redirects back to input: `frontend/src/routes/backtest/results/+page.svelte`.
  - `/backtest/results/[id]` exists but is empty: `frontend/src/routes/backtest/results/[id]/+page.svelte`.
- App scaffold (new UI direction; mocked for now):
  - `/app` redirects to the builder: `frontend/src/routes/app/+page.svelte`.
  - `/app/backtests/new` builder skeleton (palette/canvas/inspector + mock run): `frontend/src/routes/app/backtests/new/+page.svelte`.
  - `/app/backtests/[id]` mocked results/progress view: `frontend/src/routes/app/backtests/[id]/+page.svelte`.
  - `/app/backtests` placeholder history page: `frontend/src/routes/app/backtests/+page.svelte`.

### i18n
- English strings exist: `frontend/src/lib/locales/en.json`.
- Chinese locale file exists (basic coverage): `frontend/src/lib/locales/zh.json`.

### Known gaps/issues (UI-impacting)
- `/` is still placeholder; no landing page yet.
- Signup form UI is unfinished.
- Results are still mostly placeholder (charts/table are stubs; “Duplicate” is not wired).
- No persistence yet (save/load drafts, import/export JSON).
- No typed-port enforcement beyond minimal “event/number” intent; more port types needed for richer flows.

## 2) Product Goal (UI Perspective)

Build a user-friendly backtesting platform where users:
1) assemble a strategy visually (drag-and-drop blocks),
2) configure a backtest (market/timeframe/universe/costs),
3) run it and see progress,
4) explore results (metrics + charts + trades),
5) save/share/iterate.

## 3) Target User Journeys (MVP)

1) **Try it fast (no friction)**
   - Open app → use a strategy template → run backtest → view results.

2) **Build strategy visually**
   - Create strategy → drag blocks → tune params → validate → run.

3) **Iterate**
   - View results → tweak params/logic → rerun → compare runs.

## 4) Information Architecture (Suggested Routes)

Keep routes simple and UI-driven; integrate real API later.

- `/` Landing (explains the product + CTA)
- `/login`, `/signup`, `/forget-password`
- `/app` App shell entry (auth-guarded)
  - `/app/backtests` backtest history
  - `/app/backtests/new` visual builder + configuration (the “main” screen)
  - `/app/backtests/[id]` results detail
  - `/app/strategies` saved strategies/templates
  - `/app/settings` account + preferences (locale/theme)

## 5) UI Architecture (How to Organize the Frontend)

### Layout and navigation
- Create an `AppShell` layout component (top bar + optional left nav + main content).
- Add a consistent page header pattern: title, breadcrumbs, primary action, secondary actions.
- Add a route guard pattern for `/app/*` (token presence now, later real session).

### Strategy state model (UI-first)
Represent the strategy as serializable data so it can:
- render on a canvas,
- validate,
- be saved/loaded,
- be converted to backend payload later.

Recommended minimal model for MVP:
- `nodes[]`: `{ id, type, position, data }`
- `edges[]`: `{ id, source, target, sourceHandle?, targetHandle? }`
- `params`: global strategy settings (symbol universe, timeframe, costs)

### Event-flow builder (what “complete strategy flow” means)
Goal: let users express an event-driven trading strategy as a **directed graph** (flow), not just a code snippet.

- **Triggers (entry points)**: e.g. `OnBar`, `OnTick`, `OnSessionOpen`. These start a flow.
- **Data / Indicators**: e.g. `Price Bars`, `SMA`, `RSI` — produce series/values.
- **Conditions**: e.g. `Crosses Above`, `Greater Than` — produce boolean outputs.
- **Actions**: e.g. `Buy`, `Sell`, `Close` — place orders / change position state.
- **Risk / Sizing** (later): position size, stop loss, take profit, max drawdown guard.

Graph semantics (UI-first, backend later):
- Directed edges define evaluation order (“this feeds into that”).
- Nodes eventually expose **typed ports** (handles) so we can prevent invalid links:
  - example types: `event`, `series`, `number`, `boolean`, `order`.
- Validation should enforce a minimum viable flow before enabling “Run”:
  - at least one trigger,
  - at least one action reachable from a trigger,
  - all required params filled,
  - no dangling required inputs.

### Canvas navigation (pan + zoom)
As strategies grow, the canvas must support:
- **Pan**: drag on empty canvas background to move the view.
- **Zoom**: mouse wheel / trackpad scroll over the canvas to zoom in/out (zoom towards cursor).
- **Reset**: a one-click reset to 100% zoom and origin.

Implementation note: keep node positions in “world coordinates” and apply a viewport transform (`translate + scale`) so we don’t rewrite node data when panning/zooming.

### Draft backend payload (UI contract v0)
We only need to send **configuration**, not computation. A first-pass payload the UI can send when the user clicks “Run”:

```json
{
  "version": 0,
  "settings": {
    "timeframe": "1D",
    "initialCapital": 10000,
    "feesBps": 0,
    "slippageBps": 0
  },
  "graph": {
    "nodes": [
      { "id": "…", "type": "Data", "position": { "x": 120, "y": 80 }, "label": "Data", "params": { "timeframe": "1D" } }
    ],
    "edges": []
  }
}
```

Notes:
- `position` is UI-only (optional for backend), but keeping it helps reproducibility and sharing.
- `type` + `params` are the essential parts the backend will interpret.
- `edges` define the flow. Prefer including `sourceHandle` / `targetHandle` as soon as we have multi-input/multi-output nodes.

### Demo flow: SMA10 > SMA50
The builder should support a simple canonical strategy flow:
- Trigger: `OnBar` (timeframe `1D`)
- Indicators: `SMA(10)`, `SMA(50)`
- Condition: `IfAbove` (A > B) with `A=SMA(10)`, `B=SMA(50)`
- Actions: `Buy` on `true`, `Sell` on `false`

This produces a payload where edges carry handles, e.g.:
- `OnBar.out -> SMA.in`
- `SMA.out -> IfAbove.a` and `SMA.out -> IfAbove.b`
- `IfAbove.true -> Buy.in`, `IfAbove.false -> Sell.in`

### Validation + errors
Validation should run continuously and show:
- missing required blocks/parameters,
- invalid connections,
- conflicting settings,
- warnings vs errors.

## 6) Core Screen Specs (UI Deliverables)

### A) Builder screen: `/app/backtests/new`

**Layout**
- Left: block palette (search + categories).
- Center: canvas (drag/drop + connect).
- Right: inspector (selected block config + strategy-level config).
- Top: run controls (Run, Save, Duplicate, Reset), plus run status.

**Block categories (start small)**
- Data: “Price Bar”, “Timeframe”, “Universe”
- Indicators: SMA, EMA, RSI
- Conditions: “Crosses Above/Below”, “Greater/Less Than”
- Actions: Buy, Sell, Close
- Risk: Position size, Stop loss, Take profit

**UX details**
- Palette supports drag-to-canvas.
- Inspector shows form fields for the selected block.
- Inline “strategy preview” panel (optional) that shows JSON config to build user trust.
- “Run” disabled until validations pass.

### B) Results screen: `/app/backtests/[id]`

**States**
- Pending/queued (show ETA if available)
- Running (progress + logs)
- Completed (results)
- Failed (error + retry)

**Completed view (MVP)**
- KPI cards: total return, max drawdown, sharpe (or placeholder), win rate, trades count.
- Equity curve chart (can start with a simple line chart).
- Trades table (sortable; filter by symbol/date).
- Parameters + strategy graph snapshot (read-only).
- Export actions: JSON config, CSV trades (later).

### C) History screen: `/app/backtests`
- List/table of runs with: name, date range, timeframe, status, return, drawdown.
- Ability to open results, duplicate a run, or delete (later).

## 7) Milestones (UI-First Roadmap)

### Phase 0 — UI foundations (1–2 days)
- [ ] Replace `/` placeholder with a real landing page + nav.
- [x] Add `AppShell` and route scaffolding under `/app/*`.
- [~] Make auth pages consistent (spacing, button styles, copy).
- [x] Fill `zh.json` with at least the keys already used in UI (or remove zh until ready).

**Definition of done**
- App has consistent navigation and typography.
- Routes exist and render without placeholder content.

### Phase 1 — Builder MVP (3–7 days)
- [x] Implement the builder layout (palette/canvas/inspector).
- [x] Implement a minimal node set (3–6 block types) and serialization.
- [x] Add validation + “Run” gating.
- [x] Add “mock run” backend in the frontend (fake progress + fake results).
- [x] Add connections (edges) with handles + basic event-flow nodes (trigger + condition).
- [x] Add canvas pan/zoom so big flows remain usable.

**Definition of done**
- A user can build a tiny strategy, run it, and reach a results page.

### Phase 2 — Results MVP (3–7 days)
- Add results page states (running/completed/failed).
- Add KPI cards + equity chart + trades table.
- Add “Duplicate run” to go from results → builder prefilled.

**Definition of done**
- Results are readable and comparable across runs (even if mocked).

### Phase 3 — UX polish + real integrations (ongoing)
- Integrate real auth with `backend/auth/*`.
- Integrate real backtest endpoints once available (polling or websocket).
- Add strategy templates, saved strategies, versioning.
- Add accessibility pass and keyboard support for builder.

## 8) Open Questions (Decide Early)

- Builder interaction model: node graph with connections vs “rule list” with draggable rows?
- Strategy output: JSON-only vs generate readable pseudocode?
- Results chart library choice (trade-offs: bundle size vs features).
- Comparison UX: side-by-side runs vs overlay equity curves?

## 9) Suggested Next UI Tasks (If You Want a Concrete First Sprint)

1) Add validation + visible errors (missing trigger/action, missing inputs, invalid links) and disable “Run” until valid.
2) Add Export/Import JSON (copy + paste) for the `graph` payload (nodes + edges + handles).
3) Add Save Draft / Load Draft (localStorage), and wire real “Duplicate” from results to builder.
4) Add one more condition node that users expect (`CrossAbove` / `CrossBelow`) and enforce port typing (`event`/`number`/`boolean`).
