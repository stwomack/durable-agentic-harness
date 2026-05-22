# Self-Evolving Stock Agent — Demo Design

**Date:** 2026-05-21
**Status:** Approved
**Author:** Darshit + Claude (brainstorm)
**Demo context:** Large-scale AI event; 15+ minute stage slot; "wow" moment is full self-evolution (Phases 1→4 visible on stage)

---

## 1. Goal

Build a demo application that proves **Temporal is the production-grade harness for agentic AI** by running an autonomous, self-evolving stock-trading agent on stage. The demo must:

- Look real-life (real ticker, real OHLCV data option, realistic UI)
- Stay reliably scriptable for stage demos (env-switchable full-mock mode)
- Showcase the *durability* story (kill the worker mid-trade; Temporal resumes seamlessly)
- Tell a coherent OpenAI Agents SDK + Temporal story end-to-end (one agent SDK across the stack)

Non-goals: real money trading; production-grade security; multi-user auth; persistent multi-day runs.

---

## 2. Scope summary (decisions locked during brainstorm)

| Area | Decision |
|---|---|
| Demo length & climax | 15+ min, full Phase 1→4 self-evolution |
| LLM stack | OpenAI everywhere via `temporalio.contrib.openai_agents` |
| Code-execution sandbox | OpenAI Agents SDK SandboxAgent + Docker backend |
| Data sources | Env-switchable: `DATA_MODE=mock` (Mockoon) or `DATA_MODE=live` (Yahoo Finance + Mockoon for news/broker) |
| Approval UX | In-app React modal (no Slack/Telegram) |
| Domain DB | Mockoon (`/db/trades`, `/db/strategy`, `/db/positions`, `/db/audit`) |
| FastAPI DB | SQLite (run registry, idempotency keys, chaos events) |
| Live loop tick | `TICK_SECONDS` env, default `10` |
| Broker MCP server | Dropped for v1 — Activity calls Mockoon directly |
| Stage controls | Full chaos panel in UI (kill worker, restart, crash broker, inject news, force drift, fast-forward) |
| Control plane | FastAPI is sole Temporal client; UI talks to FastAPI; SSE for live events |

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

### 3.1 Containers (docker-compose.yml)

1. `temporal` — `temporalio/auto-setup:latest` (`:7233` gRPC, `:8233` Web UI)
2. `mockoon` — `mockoon/cli:latest` (`:3001`), loads `mockoon/demo.json`
3. `fastapi` — Python 3.12, REST + SSE at `:8000`, mounts SQLite volume
4. `worker` — Python 3.12, hosts workflow + activity registrations; mounts `/var/run/docker.sock`
5. `frontend` — Vite dev server (`:5173`) for dev mode; nginx-served build for "demo mode"
6. `sandbox-base` — **image only** (not a running service); pre-baked with TA-Lib, yfinance, pandas, numpy, openai-agents

All on `demo_net` bridge network.

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
- `goal`, `limits`, `winning_strategy`, `positions`, `audit_log[]`, `live_metrics`, `last_decision`, `tick_count`, `phase` (enum: `SYNTHESIZING|WATCHING|AWAITING_APPROVAL|EVOLVING`)

**Signals:**
- `approve_trade(trade_id: str)` — Phase 3 approval
- `reject_trade(trade_id: str, reason: str)` — Phase 3 rejection
- `force_drift()` — chaos: trigger Phase 4 re-plan immediately
- `fast_forward_tick()` — chaos: wake the timer immediately
- `inject_news(headline: str, sentiment: float)` — chaos: push fake news into next tick
- `stop()` — graceful shutdown

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

                # ───── PHASE 4 check ─────
                if self.state.tick_count % 5 == 0 or self._force_drift_requested:
                    self._force_drift_requested = False
                    drift = await workflow.execute_activity(
                        check_drift,
                        DriftInput(live_metrics=self.state.live_metrics,
                                   baseline=self.state.winning_strategy.scorecard,
                                   threshold=inp.drift_threshold),
                        start_to_close_timeout=timedelta(seconds=10),
                    )
                    if drift.drifted:
                        self.state.audit_log.append(AuditEvent.drift(drift))
                        self.state.phase = Phase.EVOLVING
                        drift_detected = True
            # Loop back to Phase 1 for re-synthesis
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
| `fetch_market_snapshot` | ticker | `{price, indicators}` | max 5 | Yahoo or Mockoon `/market/quote` + `/market/indicators` |
| `fetch_news_snapshot` | ticker | `{headlines[], sentiment}` | max 5 | Always Mockoon (no free real news source) |
| `call_agent` | context bundle | `TradeIntent \| HOLD` | max 3, AuthErr non-retryable | OpenAI Agents SDK agent, `gpt-4o-mini` for speed; `max_retries=0` on the OpenAI client |
| `risk_check` | intent, positions, news, limits | `{decision, reason}` | max 0 (pure) | Deterministic checks: notional caps, sentiment threshold, restricted-term blocklist |
| `notify_ui` | event payload | `ok` | max 5 | POSTs to FastAPI `/internal/events` (shared-token auth) |
| `place_order` | intent, idempotency_key | `OrderResult` | max 5 | Mockoon `POST /broker/orders`; idempotency on header `X-Idempotency-Key` |
| `write_trade_record` | order_result | `ok` | max 5 | Mockoon `POST /db/trades` |
| `check_drift` | live_metrics, baseline, threshold | `{drifted, reason}` | max 0 | Pure comparison |
| `persist_strategy` | winning_strategy | `ok` | max 5 | Mockoon `POST /db/strategy` |

---

## 6. The Sandbox bridge (the wow piece)

Per `references/python/ai-patterns.md` (OpenAI Agents SDK integration) and the Temporal+OpenAI Agents Sandbox blog (https://temporal.io/blog/introducing-temporal-and-agentic-sandboxes-openai-agents-sdk).

> **Implementation note:** the exact import paths below are tentative — both `openai-agents` sandbox API and `temporalio.contrib.openai_agents` are recent additions and have moved between minor versions. The implementation plan will pin specific package versions and verify imports against the chosen versions. If the Temporal-aware sandbox client is not available at impl time, fall back to wrapping a plain `docker` SDK call from the activity and surfacing the same `Scorecard` contract — the workflow code is unaffected.

```python
# backend/worker/activities/backtest.py — illustrative, exact imports TBD at impl time
from temporalio import activity
from agents import Agent, Runner
from agents.sandbox import CodeSandbox, DockerSandboxClient
# When the temporal-aware client lands officially, swap the import below.
# from temporalio.contrib.openai_agents import temporal_sandbox_client

@activity.defn
async def run_backtest_in_sandbox(input: BacktestInput) -> Scorecard:
    sandbox_client = DockerSandboxClient(
        image="durable-agent-sandbox:latest",
        # Resource caps so a runaway script can't burn the demo machine:
        mem_limit="512m", cpu_quota=50_000,
        network_disabled=True,  # backtest sandbox is offline; data is mounted
    )
    async with CodeSandbox(client=sandbox_client) as sandbox:
        await sandbox.upload_file("/data/ohlcv.parquet", input.historical_data_ref)
        agent = Agent(
            name="quant-coder",
            instructions=BACKTEST_PROMPT,
            tools=[sandbox.run_python, sandbox.read_file, sandbox.write_file],
            model="gpt-4o-mini",
        )
        result = await Runner.run(agent, input.strategy_spec.to_prompt())
        return Scorecard.parse_raw(result.final_output)
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
    "kind": "phase_change | backtest_progress | trade_intent | risk_decision | approval_request | order_placed | chaos | drift_detected | audit",
    "payload": { ... }
  }
  ```

---

## 8. Frontend (React + Vite + shadcn + tailwind)

Single-page app, three tabs + persistent chaos panel.

**Tab 1 — Mission Control** (default)
- Hero card: ticker, objective, phase badge, total ROI sparkline
- Vertical stepper: Synthesizing → Watching → Awaiting Approval → Evolving
- Live event log (SSE-driven virtualized list, color-coded by `kind`)
- Workflow ID + deep-link to Temporal Web UI

**Tab 2 — Strategy War Room** (Phase 1)
- Grid of N "sandbox cards"
- Each card live-updates: status badge, Sharpe/ROI/Drawdown on completion
- Winner glows + "WINNER" ribbon
- Expandable "Generated Code" panel per card

**Tab 3 — Live Trading Floor** (Phases 2/3)
- Price chart (recharts) — last 50 ticks
- Trade intents table (intent → risk decision → order outcome)
- Approval modal pops on `approval_request` event: trade details, news summary, risk rationale, two big buttons (Approve / Reject)

**Persistent Chaos Panel** (right rail / drawer)
- Buttons: Kill Worker, Restart Worker, Crash Broker, Inject Bad News, Force Drift, Fast-Forward Tick
- Each calls `POST /api/chaos/{action}`
- Toast confirmation on success

**Aesthetic:** dark slate background, neon (cyan/violet) accents, mono font for code, Framer Motion for phase transitions. shadcn primitives: `Card`, `Badge`, `Dialog`, `Sheet`, `Tabs`, `Button`, `Tooltip`, `Toast`.

---

## 9. Stage demo script (target 15 min)

| Time | Action | Audience sees |
|---|---|---|
| 0:00 | Open UI, enter NVDA + objective, click Start | Phase badge → "Synthesizing" |
| 0:30 | Switch to War Room tab | 8 sandbox cards spinning; expand one to see LLM-written code |
| 1:30 | All sandboxes complete | Sharpe table, winner glows |
| 2:00 | Auto-transition to Trading Floor | First tick fires; intent table fills |
| 3:00 | **Chaos: Inject Bad News** | Next tick: news flips negative, risk_check blocks trade |
| 4:30 | **Chaos: Fast-Forward Tick** + clean news | Trade intent → BUY → approval modal pops |
| 5:00 | Click Approve | Order placed, trade record written |
| 6:00 | **Chaos: Kill Worker** | Activity in flight; UI freezes |
| 6:15 | **Chaos: Restart Worker** | Open Temporal Web UI: replay visible, activity completes |
| 7:30 | Walk audience through Event History | LLM prompts/responses visible as Events |
| 9:00 | **Chaos: Force Drift** | Phase badge → "Evolving"; Phase 1 re-fans out |
| 11:00 | New winning strategy adopted | Trading Floor resumes |
| 13:00 | Q&A buffer | — |

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
│       ├── main.py
│       ├── workflows/{parent.py, backtest.py}
│       └── activities/{market.py, news.py, llm.py, backtest.py, broker.py, risk.py, ui.py, drift.py, persist.py}
├── mockoon/
│   └── demo.json
└── sandbox/
    ├── Dockerfile           # base sandbox image: python + ta-lib + yfinance + pandas + openai-agents
    └── runner.py
```

---

## 11. Testing & observability

**Tests (kept lightweight for a demo):**
- Workflow replay tests with `WorkflowEnvironment.from_local` for the parent's happy path + each signal branch
- Activity unit tests (`pytest`) for `risk_check` (pure), `place_order` (httpx mock), `call_agent` (OpenAI client mock)
- One end-to-end smoke test under `pytest -m e2e` that runs the full compose stack in CI

**Observability:**
- Temporal Web UI at `:8233`, deep-linked from React UI
- `structlog` JSON logs across worker + FastAPI
- Token-usage logged inside `call_agent` activity
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
