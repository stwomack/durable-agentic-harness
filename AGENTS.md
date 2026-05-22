# AGENTS.md — Durable Agentic Harness

> Canonical context for AI coding agents working in this repo.
> Always read this file first before touching code.

---

## 1. What this project is

A demo application that proves **Temporal is the production-grade harness for agentic AI** by running an autonomous, self-evolving stock-trading agent. Built for a large-scale AI event with a 15+ minute stage slot.

**Single sentence pitch:** an OpenAI Agents SDK agent runs Python code in Docker sandboxes to discover a trading strategy, then a long-running Temporal workflow durably executes that strategy with news-aware guardrails and human approval — and re-evolves the strategy when it drifts.

**Why Temporal:** the agent must survive worker crashes mid-trade, pause durably for approval, run for hours, and produce an auditable Event History of every LLM decision.

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
| Frontend | React + Vite + TypeScript + shadcn/ui + Tailwind + Framer Motion + recharts | Single SPA, three tabs + chaos panel |
| Backend API | FastAPI (Python 3.12) | Sole Temporal client; REST + SSE |
| Orchestrator | Temporal (`temporalio/auto-setup`) | Local dev; Web UI on `:8233` |
| Worker | Python 3.12, `temporalio` SDK | Hosts workflows + activities |
| Agent SDK | `openai-agents` + `temporalio.contrib.openai_agents` | OpenAI Agents SDK with Temporal-aware activities |
| Code sandbox | OpenAI Agents SDK `CodeSandbox` + `DockerSandboxClient` | Per-backtest disposable containers |
| Mocked services | Mockoon CLI (`:3001`) | market, news, broker, domain DB |
| FastAPI DB | SQLite (`backend/fastapi_app/db.sqlite3`) | run registry, idempotency keys, chaos events |
| Live data (optional) | `yfinance` | Switched via `DATA_MODE=live` |
| Packaging | Docker Compose | All services + sandbox base image |

---

## 4. Critical invariants — DO NOT VIOLATE

### 4.1 Temporal workflow determinism
- **No I/O in workflow code.** No HTTP, no SQLite, no `time.time()`, no `random`, no `os.environ`. Everything goes through activities.
- Use `workflow.now()`, `workflow.uuid4()`, `workflow.sleep()`, `workflow.execute_activity()`.
- Workflow code consumes typed Pydantic models from `backend/shared/models.py` — no raw dicts.
- Use `with workflow.unsafe.imports_passed_through():` when importing activity modules into workflow files.

### 4.2 OpenAI client config
- Always set `max_retries=0` on the OpenAI client — Temporal retries, not the SDK.
- Use the `pydantic_data_converter` on the Temporal client so Pydantic models cross the wire correctly.
- See `backend/shared/openai_client.py` for the canonical client factory.

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
- Chaos signals (`force_drift`, `fast_forward_tick`, `inject_news`) go through Temporal Signals — not direct workflow mutation.

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
│   │   ├── prompts.py                            ← versioned prompt strings
│   │   ├── openai_client.py                      ← single OpenAI client factory
│   │   ├── settings.py                           ← Pydantic Settings (env vars)
│   │   └── constants.py
│   ├── fastapi_app/
│   │   ├── main.py
│   │   ├── temporal_client.py                    ← single shared TemporalClient instance
│   │   ├── chaos.py                              ← docker.sock control
│   │   ├── db.py                                 ← SQLite layer (sqlite3 stdlib, no ORM)
│   │   └── routes/{runs,events,chaos,approvals,internal}.py
│   └── worker/
│       ├── main.py                               ← worker registration entrypoint
│       ├── workflows/
│       │   ├── parent.py                         ← SelfEvolvingStockAgentWorkflow
│       │   └── backtest.py                       ← BacktestSandboxWorkflow
│       └── activities/
│           ├── market.py                         ← fetch_historical_data, fetch_market_snapshot
│           ├── news.py                           ← fetch_news_snapshot
│           ├── llm.py                            ← call_agent
│           ├── backtest.py                       ← run_backtest_in_sandbox (the wow piece)
│           ├── broker.py                         ← place_order
│           ├── risk.py                           ← risk_check (pure)
│           ├── drift.py                          ← check_drift (pure)
│           ├── persist.py                        ← persist_strategy, write_trade_record
│           └── ui.py                             ← notify_ui (POSTs to FastAPI /internal/events)
├── mockoon/
│   └── demo.json                                 ← all mocked endpoints
└── sandbox/
    ├── Dockerfile                                ← image: python + ta-lib + yfinance + pandas + openai-agents
    └── runner.py                                 ← helpers the LLM-written code can import
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
DRIFT_THRESHOLD=0.20
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
- Token usage is logged in `call_agent`; cost should be visible in worker logs

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

- [x] Brainstorm complete (Step 1)
- [x] Design spec written and approved (Step 2)
- [x] AGENTS.md committed (Step 3 — this file)
- [ ] Implementation plan written (next: invoke `superpowers:writing-plans`)
- [ ] Scaffold built
- [ ] Phase 1 (fan-out backtests) end-to-end
- [ ] Phase 2 (live monitor loop) end-to-end
- [ ] Phase 3 (guardrails + approval modal) end-to-end
- [ ] Phase 4 (drift detection + re-plan) end-to-end
- [ ] Chaos panel wired
- [ ] Stage rehearsal pass
