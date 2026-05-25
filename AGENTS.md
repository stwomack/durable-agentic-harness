# AGENTS.md — Durable Agentic Harness

> Canonical context for AI coding agents working in this repo.
> Always read this file first before touching code.

---

## 1. What this project is

**Title:** Temporal: The Durable Operating System for Agentic AI

**Synopsis:** Temporal provides the durable OS layer that makes autonomous agents production-ready — preserving state, replaying decisions, plugging components together, and surviving crashes, restarts, and chaos. The demo runs an autonomous stock-trading agent built with the Durable Harness Pattern: it discovers a strategy through parallel sandboxed backtests, then enters a long-lived monitoring loop with news-aware risk guardrails and human-in-the-loop approval. Temporal's durable workflows, activities, signals, and event history give the agent autosave, guardrails, observability, and long-lived coordination — turning it into an Agentic AI operating system, not just a script runner.

**Demo arc on stage:**
1. **Discovery:** fan-out N parallel sandboxed backtests → pick a winner durably.
2. **Live execution:** every-N-second tick loop with market + news context, LLM trade-intent, deterministic risk check, human approval modal for big trades.
3. **Chaos survival:** kill the worker mid-trade → Temporal resumes from the exact line. Inject bad news → guardrail blocks. Fast-forward ticks for pacing.

**Why Temporal (the headline takeaways):**
- Durable execution: workflow state is the database; survives worker crashes mid-activity.
- Audit trail: every LLM prompt / response / tool call is an Event in history — full observability.
- Long-lived coordination: signals + queries let the agent pause durably for human approval at zero cost.
- Pluggable connectors: activities cleanly wrap LLM, sandbox, market data, news, broker — each retryable with its own policy.

---

## 2. Primary references (read these in order)

1. [`docs/superpowers/specs/2026-05-21-self-evolving-stock-agent-design.md`](docs/superpowers/specs/2026-05-21-self-evolving-stock-agent-design.md) — the locked design spec
2. [`project_description.md`](project_description.md) — the original brainstorm (some details superseded by the spec; see §5 below)
3. Temporal Python AI patterns: [`~/.claude/plugins/cache/temporal-marketplace/temporal/0.2.2/skills/temporal-developer/references/python/ai-patterns.md`](../../.claude/plugins/cache/temporal-marketplace/temporal/0.2.2/skills/temporal-developer/references/python/ai-patterns.md)
4. Inspiration repos (do not copy wholesale; borrow patterns):
   - https://github.com/temporal-community/temporal-ai-agent
   - https://github.com/temporal-community/ai-agents-workshop-python
   - https://github.com/temporal-community/openai-agents-sdk-deep-research-demo
   - https://temporal.io/blog/introducing-temporal-and-agentic-sandboxes-openai-agents-sdk

---

## 3. Stack at a glance

| Layer | Tech | Notes |
|---|---|---|
| Frontend | React + Vite + TypeScript + shadcn/ui + Tailwind + recharts | Single SPA, three sections + chaos panel |
| Backend API | FastAPI (Python 3.12) | Sole Temporal client; REST + SSE |
| Orchestrator | Temporal (`temporal server start-dev` on the host) | Reached from compose via `host.docker.internal:7233` |
| Worker | Python 3.12, `temporalio[openai-agents]>=1.17.0` | Hosts workflows + activities + the `OpenAIAgentsPlugin` |
| Agent SDK | `openai-agents` (`Agent`, `Runner`) + `temporalio.contrib.openai_agents` (`OpenAIAgentsPlugin`, `activity_as_tool`) | Trade-intent agent runs inside the parent workflow; LLM calls auto-dispatched as durable activities by the plugin; market/news activities exposed as Agent tools |
| Code sandbox | Plain `docker.from_env()` from inside the `run_backtest_in_sandbox` activity | Per-backtest disposable container with deterministic script from `backtest_template.build_backtest_code` (LLM-codegen removed for stage reliability) |
| Mocked services | Mockoon Desktop on host (`:3001`) | market, news, broker, domain DB |
| FastAPI DB | SQLite (`backend/fastapi_app/db.sqlite3`) | run registry, idempotency keys, chaos events |
| Live data (optional) | `yfinance` | Switched via `DATA_MODE=live` |
| Packaging | Docker Compose | fastapi + worker + frontend (Temporal & Mockoon on host) |

---

## 4. Critical invariants — DO NOT VIOLATE

### 4.1 Temporal workflow determinism
- **No I/O in workflow code.** No HTTP, no SQLite, no `time.time()`, no `random`, no `os.environ`. Everything goes through activities.
- Use `workflow.now()`, `workflow.uuid4()`, `workflow.sleep()`, `workflow.execute_activity()`.
- Workflow code consumes typed Pydantic models from `backend/shared/models.py` — no raw dicts.
- Use `with workflow.unsafe.imports_passed_through():` when importing activity modules into workflow files.

### 4.2 OpenAI Agents SDK integration

The integration is intentionally small and lives in two places:

**1. Worker setup** ([`worker/main.py`](backend/worker/main.py)) — one plugin on the client:

```python
client = await Client.connect(
    settings.temporal_address,
    data_converter=pydantic_data_converter,
    plugins=[OpenAIAgentsPlugin(model_params=ModelActivityParameters(...))],
)
```

The plugin auto-dispatches every Agent LLM call as a Temporal activity. No `call_agent` activity to write or register.

**2. The agent** ([`worker/workflows/parent.py::_run_trade_agent`](backend/worker/workflows/parent.py)) — defined and run **inside** the workflow:

```python
agent = Agent(
    name="TradeIntentAgent",
    instructions=LIVE_AGENT_PROMPT,
    model=settings.openai_model,
    tools=[
        temporal_agents.workflow.activity_as_tool(fetch_market_snapshot, **_T_MEDIUM),
        temporal_agents.workflow.activity_as_tool(fetch_news_snapshot, **_T_MEDIUM),
    ],
    output_type=TradeIntent,
)
result = await Runner.run(agent, input=input_msg, max_turns=20)
```

What this gives us:
- LLM call → durable Temporal activity (plugin)
- Tool call → durable Temporal activity (`activity_as_tool` wraps existing `fetch_*` activities)
- Structured output → `output_type=TradeIntent` removes JSON-parsing brittleness
- Worker crash mid-agent-loop → Temporal replays from the last event

Activities used as tools (`fetch_market_snapshot`, `fetch_news_snapshot`) MUST still be registered in `Worker(activities=[...])` and MUST have docstrings (the docstring becomes the tool description shown to the LLM).

### 4.3 Activity error classification
- Permanent failures (auth, invalid input, content policy) → raise `ApplicationError(..., non_retryable=True)`.
- Transient (rate limits, 5xx, network) → raise plain `ApplicationError`; Temporal retries.
- Rate-limit responses: parse `Retry-After` and set `next_retry_delay` on the error.

### 4.4 Idempotency
- Every `place_order` call carries an idempotency key derived from `f"{workflow_id}:{trade_id}"`.
- Mockoon's `/broker/orders` is configured to dedupe on the `X-Idempotency-Key` header.

### 4.5 Data-mode switch
- Activities that touch external data sources must dispatch via `settings.data_mode`:
  - `DATA_MODE=mock` → Mockoon
  - `DATA_MODE=live` → Yahoo Finance (history + quotes); news/broker still Mockoon
- Workflow code stays data-source-agnostic.

### 4.6 Chaos endpoints
- `POST /api/chaos/kill_worker` etc. live in FastAPI and use `docker.sock` to manipulate containers.
- Chaos signals (`fast_forward_tick`, `inject_news`) go through Temporal Signals — not direct workflow mutation.

---

## 5. Project structure

```
durable-agentic-harness/
├── AGENTS.md                                     ← you are here
├── docker-compose.yml
├── .env.example
├── README.md
├── docs/superpowers/specs/                       ← design + plan docs
├── frontend/                                     ← Vite + React + shadcn
│   ├── src/components/{MissionControl,WarRoom,TradingFloor,ChaosPanel,ApprovalModal,EventLog}.tsx
│   ├── src/hooks/{useSSE,useWorkflow,useChaos}.ts
│   ├── src/lib/api.ts
│   └── Dockerfile
├── backend/
│   ├── pyproject.toml                            ← single Python project; uv- or poetry-managed
│   ├── Dockerfile.fastapi
│   ├── Dockerfile.worker
│   ├── shared/                                   ← imported by BOTH fastapi_app and worker
│   │   ├── models.py                             ← Pydantic types for all workflow I/O
│   │   ├── prompts.py                            ← versioned prompt strings (LIVE_AGENT_PROMPT, BACKTEST_PROMPT)
│   │   ├── settings.py                           ← Pydantic Settings (env vars)
│   │   ├── strategies.py                         ← default_candidate_strategies (deterministic list)
│   │   ├── selection.py                          ← select_winner (pure scorecard ranking)
│   │   └── constants.py                          ← Phase, RiskDecision, TradeAction enums
│   ├── fastapi_app/
│   │   ├── main.py
│   │   ├── temporal_client.py                    ← single shared TemporalClient instance
│   │   ├── chaos.py                              ← docker.sock control
│   │   ├── db.py                                 ← SQLite layer (sqlite3 stdlib, no ORM)
│   │   └── routes/{runs,events,chaos,approvals,internal}.py
│   └── worker/
│       ├── main.py                               ← worker entrypoint + OpenAIAgentsPlugin config
│       ├── workflows/
│       │   ├── parent.py                         ← SelfEvolvingStockAgentWorkflow (Agent + Runner inline)
│       │   ├── backtest.py                       ← BacktestSandboxWorkflow (child)
│       │   └── hello.py                          ← HelloWorkflow (smoke test)
│       └── activities/
│           ├── market.py                         ← fetch_historical_data, fetch_market_snapshot
│           ├── news.py                           ← fetch_news_snapshot
│           ├── backtest.py                       ← run_backtest_in_sandbox
│           ├── backtest_template.py              ← deterministic per-strategy backtest code generator
│           ├── broker.py                         ← place_order
│           ├── risk.py                           ← risk_check (pure)
│           ├── persist.py                        ← persist_strategy, write_trade_record
│           └── ui.py                             ← notify_ui (POSTs to FastAPI /internal/events)
├── mockoon/
│   └── demo.json                                 ← all mocked endpoints (loaded into Mockoon Desktop on host)
└── sandbox/
    ├── Dockerfile                                ← image: python + ta-lib + pandas + pyarrow
    └── runner.py                                 ← helpers the executed backtest code can import
```

---

## 6. Environment variables

See `.env.example`. Required:

```
OPENAI_API_KEY=sk-...
TEMPORAL_ADDRESS=temporal:7233           # inside compose; localhost:7233 for host runs
TEMPORAL_NAMESPACE=default
DATA_MODE=mock                           # or "live"
TICK_SECONDS=10                          # 15min in prod, 10s for demo
APPROVAL_THRESHOLD_USD=10000
NUM_SANDBOXES=8
MOCKOON_BASE_URL=http://mockoon:3001
FASTAPI_INTERNAL_TOKEN=demo-token-change-me
SANDBOX_IMAGE=durable-agent-sandbox:latest
LOG_LEVEL=INFO
```

---

## 6.5 House rules (locked during the build)

These overrides apply to ALL work in this repo:

1. **No `Co-Authored-By: Claude…` trailers** on git commits. Clean commit history only.
2. **Batch commits at phase boundaries**, not per task. Subagents must create/edit files but NOT commit during a phase. Controller commits once when each phase wraps.
3. **Temporal server runs on the host**, not in compose. `docker-compose.yml` must NOT include `temporal` or `temporal-ui` services. Containers reach the host's Temporal at `host.docker.internal:7233`. The Temporal Web UI is whatever port the user's local install uses.
4. **`.env`** values inside compose use `TEMPORAL_ADDRESS=host.docker.internal:7233`. Host-side scripts (running outside Docker) use `localhost:7233`.

## 7. How to run things

> Detailed implementation commands will be filled in by the implementation plan; the targets below are the contract.

| Goal | Command |
|---|---|
| Build everything | `docker compose build` |
| Start the demo (mock mode) | `docker compose up` |
| Start with live data | `DATA_MODE=live docker compose up` |
| Tail worker logs | `docker compose logs -f worker` |
| Open Temporal Web UI | http://localhost:8233 |
| Open the demo UI | http://localhost:5173 (dev) or http://localhost (prod build) |
| Reset everything | `docker compose down -v && docker compose up --build` |
| Run unit tests | `cd backend && pytest -m "not e2e"` |
| Run e2e smoke | `cd backend && pytest -m e2e` |

---

## 8. Common tasks (playbooks)

### Adding a new candidate strategy
1. Define a `StrategySpec` factory in `backend/shared/strategies.py`
2. Add to the default `candidate_strategies` list in `fastapi_app/routes/runs.py`
3. Update the backtest prompt in `shared/prompts.py` if the indicator family is new
4. No workflow changes required — Phase 1 is parametric on the input list

### Adding a new chaos action
1. Add a button in `frontend/src/components/ChaosPanel.tsx`
2. Add a route in `fastapi_app/routes/chaos.py`
3. If it requires workflow-side action, add a Signal handler in `worker/workflows/parent.py`
4. Otherwise (e.g. container manipulation), use `fastapi_app/chaos.py` + `docker.sock`

### Touching workflow code safely
1. Confirm the change is deterministic (no I/O, no `time`, no `random`, no `os.environ`)
2. Add or update a replay test in `backend/tests/workflows/`
3. If changing state shape, also bump the workflow version per Temporal versioning rules (`workflow.patched` / `workflow.get_version`)

### Adjusting a prompt
- Edit `backend/shared/prompts.py` — prompts are versioned by constant name; do not edit silently inline
- The `OpenAIAgentsPlugin` emits its own logs for LLM activity executions; check `docker compose logs worker` for token usage and timings

---

## 9. Style & conventions

- Python: ruff + black; type hints required on all public functions; Pydantic for all cross-boundary types
- TypeScript: prettier + ESLint; no `any`; React Query for server state; SSE via native `EventSource`
- Files stay under ~300 lines; if a module grows past that, split by responsibility
- No comments explaining WHAT — only WHY (non-obvious invariants, workarounds, references)
- Commits: conventional (`feat:`, `fix:`, `chore:`, `docs:`); reference the spec section in the body when relevant

---

## 10. Where the spec supersedes `project_description.md`

The original `project_description.md` is the source brainstorm; the design spec is now authoritative. Specific deviations:

- **DB:** spec uses **Mockoon for all domain data**; `project_description.md` mentioned both Mockoon and an unspecified DB. SQLite is FastAPI-only (run registry, idempotency, chaos log).
- **Broker MCP server:** spec **drops the MCP gateway** for v1; activities call Mockoon directly. MCP is a v2 enhancement.
- **Approval:** spec uses **in-app React modal**; `project_description.md` mentioned Slack/Telegram. Slack is a v2 toggle.
- **Tick interval:** spec uses **configurable `TICK_SECONDS` (default 10s)** for stage demo; `project_description.md` mentioned 15 minutes (production).
- **LLM provider:** spec uses **OpenAI everywhere via the Agents SDK**; `project_description.md` mentioned both Claude and OpenAI. Single SDK story.
- **Sandbox code generation:** **deterministic templates** (hand-written per strategy family) instead of LLM-generated code. We still execute the script in an isolated Docker sandbox and display the code in the War Room, but skip the OpenAI call per backtest for stage reliability. `BACKTEST_PROMPT` is unused; `_generate_backtest_code` was replaced by `build_backtest_code` in `backtest_template.py`.
- **Mockoon runs on the host**, not in compose. The user starts it via Mockoon Desktop (or `mockoon-cli`) and points the `MOCKOON_BASE_URL` env var to `http://host.docker.internal:3001` for containers. The `crash_broker` / `restart_broker` chaos buttons are therefore **removed** from the UI — the user can stop/start Mockoon Desktop directly if they need that drama.
- **Chaos panel v1 surface:** `Kill Worker`, `Restart Worker`, `Inject Bad News`, `Fast Forward`. The `Crash Broker` and `Restart Broker` buttons are gone.

---

## 11. Things that are easy to get wrong

- ❌ Importing `httpx` directly in workflow code — must go through an activity
- ❌ Catching all exceptions in activities and re-raising as plain `Exception` — wrong; classify them via `ApplicationError`
- ❌ Using `datetime.now()` in workflow code — use `workflow.now()`
- ❌ Forgetting `pydantic_data_converter` on the Temporal client — complex types will silently mangle
- ❌ Hardcoding `localhost` instead of `temporal` / `mockoon` / `fastapi` service names — breaks inside Docker
- ❌ Calling the OpenAI API with `max_retries > 0` — duplicates Temporal's retry behaviour
- ❌ Mutating workflow state from outside a Signal handler — use Signals or Updates exclusively
- ❌ Spawning sandbox containers without `mem_limit`/`cpu_quota` — runaway LLM-written code can DoS the demo machine

---

## 12. Status

- [x] Brainstorm complete
- [x] Design spec written and approved
- [x] AGENTS.md committed
- [x] Implementation plan written
- [x] Scaffold built (compose, FastAPI, worker, frontend, Mockoon fixtures, sandbox image Dockerfile)
- [x] Phase 1 (fan-out deterministic backtests) end-to-end
- [x] Phase 2 (live monitor loop) end-to-end
- [x] Phase 3 (guardrails + approval modal) end-to-end
- [x] Chaos panel: Kill Worker, Restart Worker, Inject Bad News, Fast Forward
- [ ] Stage rehearsal pass

**Cut from v1 (post-implementation simplification):**
- Chaos buttons: Crash Broker, Restart Broker
- LLM-generated backtest code (replaced by deterministic templates)
