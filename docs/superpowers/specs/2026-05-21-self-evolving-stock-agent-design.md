# Temporal: The Durable Operating System for Agentic AI — Demo Design

**Date:** 2026-05-21 (revised 2026-05-22 to simplify scope)
**Status:** Approved (v2: drift / Phase-4 / broker-chaos removed)
**Author:** Darshit + Claude (brainstorm)
**Demo context:** Large-scale AI event; 10–15 minute stage slot.

---

## 1. Goal

**Talk title:** Temporal: The Durable Operating System for Agentic AI

**Synopsis (delivered on stage):** Temporal provides the durable OS layer that makes autonomous agents production-ready — preserving state, replaying decisions, simplifying how pluggable components connect, and surviving crashes, restarts, and chaos. We show an autonomous stock-trading agent built with the **Durable Harness Pattern** that runs reliably with safety built in. It uses Temporal's durable workflows, activities, signals, and event history to behave like an **Agentic AI operating system, not just a script runner** — adding autosave, guardrails, observability, and long-lived coordination.

**Demo arc on stage (three acts):**
1. **Discovery** — fan-out N sandboxed parallel backtests, deterministic pick of the winner. (Temporal: child workflows + fan-in.)
2. **Live execution** — tick loop with market + news context, OpenAI trade-intent, deterministic news-aware risk guardrail, human-in-the-loop approval modal for big trades.
3. **Chaos survival** — kill the worker mid-trade → Temporal resumes from the exact line. Inject bad news → guardrail blocks. Fast-forward ticks for pacing.

**The demo must:**
- Look real-life (real ticker, env-switchable real OHLCV mode, realistic UI)
- Stay scriptable for stage demos (full-mock mode for predictable narrative beats)
- Headline the durability story (kill-worker / resume; pause-for-approval at zero cost)
- Make Temporal's event history visible (a tab in Temporal Web UI is shown live)

**Non-goals:** real money trading; production-grade security; multi-user auth; persistent multi-day runs; self-evolution / drift-driven re-planning (cut from v1).

---

## 2. Scope summary (locked, v2 simplification applied)

| Area | Decision |
|---|---|
| Demo length & climax | 10–12 min, climax = Kill-Worker → Temporal resumes mid-trade |
| LLM stack | **OpenAI Agents SDK + `temporalio.contrib.openai_agents` plugin.** Trade-intent `Agent` is defined and run inside the parent workflow; LLM calls auto-dispatched as durable activities. Tools (`fetch_market_snapshot`, `fetch_news_snapshot`) wrapped via `activity_as_tool`. |
| Backtest code | **Deterministic per-strategy templates** (`backtest_template.py`); runs in Docker sandbox; LLM is NOT called per backtest |
| Code-execution sandbox | Docker sandbox spawned via `docker.sock` from the worker (TA-Lib pre-baked image) |
| Data sources | Env-switchable: `DATA_MODE=mock` (Mockoon) or `DATA_MODE=live` (Yahoo Finance) |
| Approval UX | In-app React modal (no Slack/Telegram) |
| Domain DB | Mockoon (`/db/trades`, `/db/strategy`, `/db/audit`) |
| FastAPI DB | SQLite (run registry, idempotency keys, chaos events) |
| Live loop tick | `TICK_SECONDS` env, default `10` |
| Broker MCP server | Dropped — Activity calls Mockoon directly |
| Mockoon runtime | Runs on the host (Mockoon Desktop or `mockoon-cli`); NOT bundled in compose |
| Stage controls | Kill Worker, Restart Worker, Inject Bad News, Fast Forward (4 buttons) |
| Control plane | FastAPI is sole Temporal client; UI talks to FastAPI; SSE for live events |
| **REMOVED in v2** | Phase 4 drift detection, `force_drift` signal, `EVOLVING` phase, Crash/Restart Broker chaos buttons, LLM-generated backtest code |

---

## 3. System architecture

```
┌────────────┐         ┌──────────────┐         ┌────────────────┐
│  React UI  │◀───────▶│   FastAPI    │◀──────▶│ Temporal Server │
│ (shadcn,   │  REST   │ (sole TC     │  gRPC  │ (auto-setup +   │
│  tailwind) │  + SSE  │  client)     │        │  Web UI :8233)  │
└────────────┘         └──────┬───────┘         └────────┬───────┘
                              │                          │
                       ┌──────▼───────┐                  │
                       │   SQLite     │                  │
                       │ (FastAPI     │                  │
                       │  metadata)   │                  │
                       └──────────────┘                  │
                                                         │ poll
                                              ┌──────────▼──────────┐
                                              │  Temporal Worker    │
                                              │  (Python, hosts WF  │
                                              │  + Activities)      │
                                              └──┬─────────────────┬┘
                                                 │ HTTP            │ docker.sock
                                          ┌──────▼──────┐   ┌──────▼──────────┐
                                          │  Mockoon    │   │  Sandbox        │
                                          │  (market,   │   │  containers     │
                                          │  news,      │   │  (ta-lib +      │
                                          │  broker,    │   │  python, spawned│
                                          │  db, audit) │   │  per backtest)  │
                                          └─────────────┘   └─────────────────┘
                                                                ▲
                                                                │ OpenAI Agents SDK
                                                                │ Sandbox bridge
                                                                │ (Temporal-aware)
```

### 3.1 Host vs compose

**On the host** (NOT bundled in compose):
- `temporal server start-dev --ip 0.0.0.0` — gRPC `:7233`, Web UI `:8233`
- Mockoon Desktop (or `mockoon-cli`) loaded with `mockoon/demo.json` — `:3001`
- `durable-agent-sandbox:latest` Docker image (built once via `docker build -t durable-agent-sandbox:latest sandbox/`)

**In docker-compose.yml** (3 services on `demo_net` bridge):
1. `fastapi` — Python 3.12, REST + SSE at `:8000`, mounts SQLite volume + `docker.sock`
2. `worker` — Python 3.12, hosts workflows + activities + `OpenAIAgentsPlugin`; mounts `docker.sock` to spawn sibling sandbox containers
3. `frontend` — Vite dev server at `:5173`

Containers reach the host via `host.docker.internal:7233` and `http://host.docker.internal:3001`. The compose worker has IPv6 disabled (`sysctls: net.ipv6.conf.all.disable_ipv6=1`) to force IPv4 lookup of `host.docker.internal`.

### 3.2 Env-switchable data mode

- `DATA_MODE=mock` (default for stage): all market/news/broker calls go to Mockoon
- `DATA_MODE=live`: historical OHLCV from Yahoo Finance (`yfinance` lib); live quote polling from Yahoo; news + broker still Mockoon (no free real news API)

The switch is a single Pydantic settings field consumed by activity-level adapters; workflow code is data-source-agnostic.

---

## 4. Workflow design

### 4.1 Parent: `SelfEvolvingStockAgentWorkflow`

**Input (Pydantic):**
```python
class AgentInput(BaseModel):
    ticker: str
    objective: str                     # e.g. "maximize Sharpe; max drawdown < 10%"
    history_range: str = "3y"
    num_sandboxes: int = 8
    candidate_strategies: list[StrategySpec]
    limits: TradeLimits                # max_notional, max_position_pct, etc.
    approval_threshold: float          # dollar value above which approval required
    tick_seconds: int = 10
    drift_threshold: float = 0.20      # 20% live-ROI vs backtest-ROI gap → re-plan
```

**Durable state (kept in Workflow Event History):**
- `goal`, `limits`, `winning_strategy`, `positions`, `audit_log[]`, `tick_count`, `phase` (enum: `SYNTHESIZING|WATCHING|AWAITING_APPROVAL`)

**Signals:**
- `approve_trade(trade_id: str)` — Phase 3 approval
- `reject_trade(trade_id: str, reason: str)` — Phase 3 rejection
- `fast_forward_tick()` — chaos: wake the timer immediately
- `inject_news(headline: str, sentiment: float)` — chaos: push fake news into next tick
- `stop()` — graceful shutdown

> **v2 simplification:** `force_drift` signal, `drift_threshold` input field, and the `EVOLVING` phase enum value are unused in v1. The workflow exits cleanly after Phase 2+3 instead of looping back to Phase 1.

**Queries:**
- `get_state() -> StateSnapshot` — full current state for UI hydration
- `get_audit_log(since_index: int) -> list[AuditEvent]` — incremental fetch

### 4.2 Child: `BacktestSandboxWorkflow`

**Input:** `BacktestInput { strategy_spec, historical_data_ref, sandbox_image }`
**Returns:** `Scorecard { strategy_id, roi, sharpe, max_drawdown, win_rate, num_trades, generated_code, error? }`

One child per candidate strategy, spawned from parent's Phase 1 fan-out via `workflow.start_child_workflow`. Each child invokes one activity: `run_backtest_in_sandbox`. Activity retry policy: 2 retries; on third failure the child returns a `Scorecard` with `error` populated so the parent's selection step has a deterministic result.

### 4.3 Phase orchestration (parent pseudocode)

```python
@workflow.defn
class SelfEvolvingStockAgentWorkflow:
    @workflow.run
    async def run(self, inp: AgentInput) -> None:
        self.state = State.initial(inp)

        while True:
            # ───── PHASE 1: SYNTHESIZING ─────
            self.state.phase = Phase.SYNTHESIZING
            data_ref = await workflow.execute_activity(
                fetch_historical_data,
                FetchHistInput(ticker=inp.ticker, range=inp.history_range),
                start_to_close_timeout=timedelta(seconds=120),
            )

            # Fan-out: start each child (await returns a handle), then gather all results
            child_handles = await asyncio.gather(*[
                workflow.start_child_workflow(
                    BacktestSandboxWorkflow.run,
                    BacktestInput(strategy_spec=s, historical_data_ref=data_ref),
                    id=f"{workflow.info().workflow_id}-bt-{s.id}",
                )
                for s in inp.candidate_strategies
            ])
            scorecards_raw = await asyncio.gather(*child_handles, return_exceptions=True)
            scorecards = [s for s in scorecards_raw if isinstance(s, Scorecard) and s.error is None]

            self.state.winning_strategy = select_winner(scorecards, inp.objective)
            await workflow.execute_activity(
                persist_strategy, self.state.winning_strategy,
                start_to_close_timeout=timedelta(seconds=10),
            )

            # ───── PHASE 2 + 3: WATCHING / AWAITING_APPROVAL ─────
            self.state.phase = Phase.WATCHING
            drift_detected = False
            while not drift_detected:
                # Sleep or be woken by chaos signal
                try:
                    await workflow.wait_condition(
                        lambda: self._fast_forward_requested or self._stop_requested,
                        timeout=timedelta(seconds=inp.tick_seconds),
                    )
                except asyncio.TimeoutError:
                    pass
                self._fast_forward_requested = False
                if self._stop_requested:
                    return

                self.state.tick_count += 1
                market, news = await asyncio.gather(
                    workflow.execute_activity(fetch_market_snapshot, inp.ticker,
                                              start_to_close_timeout=timedelta(seconds=30)),
                    workflow.execute_activity(fetch_news_snapshot, inp.ticker,
                                              start_to_close_timeout=timedelta(seconds=30)),
                )
                # Apply injected news from chaos panel
                news = apply_injected_news(news, self._injected_news_queue)

                intent = await workflow.execute_activity(
                    call_agent,
                    AgentCallInput(
                        winning_strategy=self.state.winning_strategy,
                        market=market, news=news, positions=self.state.positions,
                    ),
                    start_to_close_timeout=timedelta(seconds=60),
                )

                if intent.action == "HOLD":
                    self.state.audit_log.append(AuditEvent.hold(intent))
                    continue

                risk = await workflow.execute_activity(
                    risk_check,
                    RiskCheckInput(intent=intent, news=news, positions=self.state.positions,
                                   limits=inp.limits, approval_threshold=inp.approval_threshold),
                    start_to_close_timeout=timedelta(seconds=5),
                )
                self.state.audit_log.append(AuditEvent.risk(intent, risk))

                if risk.decision == "block":
                    continue
                elif risk.decision == "allow_requires_approval":
                    self.state.phase = Phase.AWAITING_APPROVAL
                    trade_id = workflow.uuid4().hex
                    await workflow.execute_activity(
                        notify_ui, ApprovalRequest.from_(intent, risk, trade_id),
                        start_to_close_timeout=timedelta(seconds=10),
                    )
                    await workflow.wait_condition(
                        lambda: trade_id in self._approvals or trade_id in self._rejections
                    )
                    self.state.phase = Phase.WATCHING
                    if trade_id in self._rejections:
                        self.state.audit_log.append(AuditEvent.rejected(trade_id))
                        continue

                # Place order (allow OR approved)
                order = await workflow.execute_activity(
                    place_order,
                    PlaceOrderInput(intent=intent,
                                    idempotency_key=f"{workflow.info().workflow_id}:{intent.id}"),
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(maximum_attempts=5),
                )
                await workflow.execute_activity(
                    write_trade_record, order,
                    start_to_close_timeout=timedelta(seconds=10),
                )
                self.state.positions.apply(order)
            # v1: workflow exits cleanly when self._stop is signalled.
            # (Phase 4 drift detection and re-synthesis loop-back are deferred.)
```

### 4.4 Determinism guarantees

- Workflow code only consumes typed activity return values; no direct HTTP, no `random`, no `time.time()` (uses `workflow.now()` and `workflow.uuid4()`)
- All LLM variation lives inside `call_agent` activity — its JSON return becomes a single `ActivityTaskCompleted` event
- Hyperparameter exploration in Phase 1 is parametric (the `candidate_strategies` list is built deterministically by FastAPI before `start_workflow`)
- Sandbox container IDs, paths, and timings stay inside activities — workflow sees only `Scorecard` Pydantic models

---

## 5. Activities

All activities live in `backend/worker/activities/`. All accept Pydantic inputs, return Pydantic outputs, and classify exceptions into retryable vs `non_retryable=True` `ApplicationError`s per Temporal AI patterns.

| Activity | Inputs | Output | Retry policy | Notes |
|---|---|---|---|---|
| `fetch_historical_data` | ticker, range | `HistoricalDataRef` | max 3 | DATA_MODE switch: yfinance vs Mockoon `/market/prices`; writes to a shared volume; returns a path |
| `run_backtest_in_sandbox` | strategy_spec, data_ref | `Scorecard` | max 2 | Uses OpenAI Agents SDK SandboxAgent + Docker bridge (see §6) |
| `fetch_market_snapshot` | ticker | `{price, indicators}` | max 5 | Yahoo or Mockoon `/market/quote` + `/market/indicators`. **Also exposed as an Agent tool** via `activity_as_tool`. |
| `fetch_news_snapshot` | ticker | `{headlines[], sentiment}` | max 5 | Always Mockoon. **Also exposed as an Agent tool** via `activity_as_tool`. |
| _LLM call_ | _Agent input_ | _`TradeIntent`_ | _plugin-managed_ | _The trade-intent Agent runs inside the workflow (`_run_trade_agent`). The `OpenAIAgentsPlugin` auto-dispatches each Agent LLM call as a Temporal activity with its own retry policy. No `call_agent` activity._ |
| `risk_check` | intent, positions, news, limits | `{decision, reason}` | max 0 (pure) | Deterministic checks: notional caps, sentiment threshold, restricted-term blocklist |
| `notify_ui` | event payload | `ok` | max 5 | POSTs to FastAPI `/internal/events` (shared-token auth) |
| `place_order` | intent, idempotency_key | `OrderResult` | max 5 | Mockoon `POST /broker/orders`; idempotency on header `X-Idempotency-Key` |
| `write_trade_record` | order_result | `ok` | max 5 | Mockoon `POST /db/trades` |
| `persist_strategy` | winning_strategy | `ok` | max 5 | Mockoon `POST /db/strategy` |

> **v2 simplification:** `check_drift` activity is dropped from v1.

---

## 6. The Sandbox bridge

For stage reliability, v1 uses **deterministic hand-written backtest templates** (one per strategy family) instead of LLM-generated code. The script still executes inside an isolated Docker sandbox (TA-Lib pre-baked, network disabled, mem-capped) so the "isolated code execution" story stays intact. The generated script is included in the `Scorecard.generated_code` field and shown in the War Room UI.

```python
# backend/worker/activities/backtest.py (v2 — deterministic)
from temporalio import activity
import docker
from worker.activities.backtest_template import build_backtest_code

@activity.defn
async def run_backtest_in_sandbox(inp: BacktestInput) -> Scorecard:
    code = build_backtest_code(inp.strategy_spec, inp.historical_data_ref.path)
    # ...spawn sibling docker container, mount `sandbox-data` volume, run `python -c <code>`,
    #    parse the last JSON line of stdout as a Scorecard.
```

Failure semantics:
- Worker crash mid-activity → Temporal retries the *whole* activity; a fresh sandbox spawns; clean state recovery
- Sandbox crash (OOM, bad code) → activity raises retryable `ApplicationError`; Temporal retries up to 2 times; on third failure returns a Scorecard with `error` populated so the parent selection step still has a deterministic result

---

## 7. Data layer

### 7.1 Mockoon endpoints (`mockoon/demo.json`)

| Method | Path | Returns / behaviour |
|---|---|---|
| GET | `/market/prices?ticker=X&range=3y` | OHLCV array fixture per ticker (NVDA, AAPL, TSLA seeded) |
| GET | `/market/quote?ticker=X` | `{price, ts}` — price drifts with templated random walk per call |
| GET | `/market/indicators?ticker=X` | `{rsi, ema12, ema26, macd, bb_upper, bb_lower}` |
| GET | `/news/headlines?ticker=X` | Rotating headlines from a curated list |
| GET | `/news/sentiment?ticker=X` | `{score: -1..1, rationale}` — chaos panel can override |
| POST | `/broker/orders` | `{orderId, status, filledQty, avgPrice}` — idempotent on `X-Idempotency-Key` |
| POST | `/db/trades` | `{stored: true}` |
| POST | `/db/strategy` | `{stored: true}` |
| POST | `/db/audit` | `{stored: true}` |
| GET | `/db/trades?workflowId=X` | List |

### 7.2 SQLite schema (FastAPI `db.sqlite3`)

```sql
CREATE TABLE runs (
  workflow_id TEXT PRIMARY KEY,
  ticker      TEXT NOT NULL,
  started_at  TIMESTAMP NOT NULL,
  status      TEXT NOT NULL,
  last_phase  TEXT,
  params_json TEXT NOT NULL
);
CREATE TABLE idempotency_keys (
  key            TEXT PRIMARY KEY,
  workflow_id    TEXT NOT NULL,
  action         TEXT NOT NULL,
  response_json  TEXT,
  created_at     TIMESTAMP NOT NULL
);
CREATE TABLE chaos_events (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  workflow_id  TEXT NOT NULL,
  kind         TEXT NOT NULL,
  payload_json TEXT,
  ts           TIMESTAMP NOT NULL
);
```

### 7.3 Event stream (FastAPI SSE)

- Endpoint: `GET /api/runs/{workflow_id}/events` (SSE)
- Activity `notify_ui` → `POST /internal/events` (shared-token auth) → FastAPI fans out to SSE subscribers
- Event shape:
  ```json
  {
    "ts": "2026-05-21T10:23:00Z",
    "kind": "phase_change | backtest_progress | trade_intent | risk_decision | approval_request | order_placed | chaos | audit",
    "payload": { ... }
  }
  ```

---

## 8. Frontend (React + Vite + shadcn + tailwind)

Single-page app, three tabs + persistent chaos panel.

**Tab 1 — Mission Control** (default)
- Hero card: ticker, objective, phase badge
- Phase chips: Synthesizing → Winner Selected → Watching → Awaiting Approval
- Live event log (SSE-driven, color-coded by `kind`)
- Workflow ID + deep-link to Temporal Web UI + ✕ detach button + Start (New) Run button

**Tab 2 — Strategy War Room** (Phase 1)
- Grid of N "sandbox cards"
- Each card live-updates: status badge, Sharpe/ROI/Drawdown on completion
- Winner glows + "WINNER" ribbon
- Expandable "Generated Code" panel per card (shows the deterministic template that ran)

**Tab 3 — Live Trading Floor** (Phases 2/3)
- Price chart (recharts) — last 50 ticks
- Trade intents table (intent → risk decision → order outcome)
- Approval modal pops on `approval_request` event: trade details, news summary, risk rationale, two big buttons (Approve / Reject)

**Persistent Chaos Panel** (right rail / drawer)
- Buttons: `Kill Worker`, `Restart Worker`, `Inject Bad News`, `Fast Forward`
- Each calls `POST /api/chaos/{action}`
- Mockoon stop/start is done in the Mockoon Desktop app directly, not via a UI button

**Aesthetic:** dark slate background, neon (cyan/violet) accents, mono font for code, Framer Motion for phase transitions. shadcn primitives: `Card`, `Badge`, `Dialog`, `Sheet`, `Tabs`, `Button`, `Tooltip`, `Toast`.

---

## 9. Stage demo script (target 10–12 min)

| Time | Action | Audience sees |
|---|---|---|
| 0:00 | Open UI, enter NVDA, click Start Self-Evolving Agent | Phase badge → "Synthesizing"; workflow ID appears in header |
| 0:30 | Switch to War Room | 8 sandbox cards populating; expand one to show the deterministic backtest code (TA-Lib + pandas) that ran inside the sandbox |
| 1:30 | All sandboxes complete | Sharpe / ROI / Drawdown table; winner glows with "WINNER" ribbon |
| 2:00 | Scroll to Trading Floor | First tick fires every 10s; price chart + intent table fill |
| 3:00 | **Chaos: Inject Bad News** | Next tick: news goes negative + restricted-term match, risk_check returns `block`, trade does not place |
| 4:30 | **Chaos: Fast Forward** + clean news returns | Trade intent → BUY → approval modal pops with risk summary |
| 5:00 | Click Approve | `place_order` activity → broker order id appears in intent table, trade record written to Mockoon |
| 6:00 | **Chaos: Kill Worker** | Activity mid-flight; UI freezes mid-tick |
| 6:15 | **Chaos: Restart Worker** | Open Temporal Web UI in a side tab: show the replay continuing from the exact event |
| 7:30 | Walk audience through Event History | Every LLM call, every signal, every order — all in the durable history |
| 9:00 | Recap the OS framing | "This is the agent's autosave, guardrails, observability, and human-loop — all from Temporal primitives" |
| 10:00 | Q&A buffer | — |

---

## 10. Project structure

```
durable-agentic-harness/
├── AGENTS.md
├── docker-compose.yml
├── .env.example
├── README.md
├── docs/
│   └── superpowers/specs/
│       └── 2026-05-21-self-evolving-stock-agent-design.md
├── frontend/
│   ├── src/
│   │   ├── components/{MissionControl,WarRoom,TradingFloor,ChaosPanel,ApprovalModal,EventLog}.tsx
│   │   ├── hooks/{useSSE,useWorkflow,useChaos}.ts
│   │   ├── lib/api.ts
│   │   └── App.tsx
│   ├── package.json
│   ├── tailwind.config.ts
│   └── Dockerfile
├── backend/
│   ├── pyproject.toml
│   ├── Dockerfile.fastapi
│   ├── Dockerfile.worker
│   ├── shared/
│   │   ├── models.py        # all Pydantic types (AgentInput, Scorecard, TradeIntent, ...)
│   │   ├── prompts.py       # versioned prompt strings
│   │   └── constants.py
│   ├── fastapi_app/
│   │   ├── main.py
│   │   ├── temporal_client.py
│   │   ├── chaos.py         # docker.sock control
│   │   ├── db.py            # SQLite
│   │   └── routes/{runs,events,chaos,approvals}.py
│   └── worker/
│       ├── main.py                                    # OpenAIAgentsPlugin configured here
│       ├── workflows/{parent.py, backtest.py, hello.py}
│       └── activities/{market.py, news.py, backtest.py, backtest_template.py, broker.py, risk.py, ui.py, persist.py}
├── mockoon/
│   └── demo.json                                      # load into Mockoon Desktop on host
└── sandbox/
    ├── Dockerfile           # base sandbox image: python + ta-lib + pandas + pyarrow
    └── runner.py
```

---

## 11. Testing & observability

**Tests (kept lightweight for a demo):**
- Workflow replay tests with `WorkflowEnvironment.from_local` for the parent's happy path + each signal branch
- Activity unit tests (`pytest`) for `risk_check` (pure), `place_order` (httpx mock). The Agent's LLM call is dispatched by `OpenAIAgentsPlugin` — covered indirectly via the e2e smoke test.
- One end-to-end smoke test under `pytest -m e2e` that runs the full compose stack in CI

**Observability:**
- Temporal Web UI at `:8233`, deep-linked from React UI
- `structlog` JSON logs across worker + FastAPI
- LLM activity logs (per call) emitted by `OpenAIAgentsPlugin` — visible in worker stdout and Temporal Web UI activity history
- LangSmith tracing via `temporalio.contrib.langsmith` deferred to v2

---

## 12. Risks & open questions

1. **OpenAI Agents SDK Temporal-aware sandbox client** — depending on release status of `temporalio.contrib.openai_agents`, we may need to wrap `DockerSandboxClient` manually with Temporal's activity-side error mapping. Acceptable: the fallback is well-understood.
2. **Yahoo Finance rate limits in `DATA_MODE=live`** — `yfinance` can be flaky; the env switch lets us fall back to mock on stage.
3. **Sandbox image size** — TA-Lib + numpy + pandas + openai-agents is sizable (~800MB). Pre-pull on the demo machine.
4. **Docker socket exposure** — worker mounts `/var/run/docker.sock` so it can spawn sandboxes and so chaos endpoints can kill containers. Acceptable for a demo; flagged as not-production-safe.

---

## 13. Out of scope for v1

- Real money / live broker connection
- Multi-tenant agents (only one active workflow per UI session)
- Persistent run history beyond SQLite reset on compose-down
- Slack / Telegram approval (env-toggle could be added in v2)
- Broker MCP server (kept in `project_description.md` as v2 enhancement)
- **Phase 4 self-evolution / drift detection** — the "drift triggers re-discovery" loop is deferred. Activities, signal, phase enum value, UI button, and stage moment all removed.
- **Chaos buttons: Crash Broker / Restart Broker** — Mockoon runs on the host now, so stopping/starting it happens in Mockoon Desktop directly.
- **LLM-generated backtest code** — replaced by deterministic `backtest_template.build_backtest_code(...)` for stage reliability. We still execute in a sandbox and display the code in the UI, just don't call OpenAI per backtest.
