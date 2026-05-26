# Temporal: The Durable Operating System for Agentic AI

> Demo to showcase Temporal as the Durable OS layer for Agentic AI underneath an autonomous OpenAI-Agents-SDK trading agent.

An autonomous stock-trading agent that:
1. **Discovers** a strategy by fanning out N parallel sandboxed backtests within airgapped Dockers
2. **Lives** through a tick loop with market + news context, LLM trade-intent (OpenAI Agents SDK), deterministic risk guardrail, and human-in-the-loop approval for big trades
3. **Survives** chaos — kill the worker mid-trade and Temporal replays the agent's decision history to resume from the exact line

Temporal provides the durable OS layer: autosave (workflow state = event history), guardrails (deterministic activities + signals), observability (every LLM call / tool call / signal is a queryable event), and long-lived coordination (workflows pause for approval at zero CPU cost).

---
## Why Temporal? — The Durable OS for Agentic AI

**Agents are easy to demo. Hard to operate.** Every production agent eventually hits the same wall: LLM calls flake, workers crash mid-tool-call, human approvals stall for hours, parallel work loses children on restart. The usual answer — "just add retries + Redis + a state machine" — is the long road to badly reinventing Temporal.

**Reframe Temporal not as a workflow engine, but as OS primitives for agent loops:**

| OS primitive | Temporal equivalent | What it gives agents |
|---|---|---|
| Process scheduling | Workers + task queues | LLM/tool work dispatched durably, anywhere |
| Autosave / journaling | Event history | Replay from the exact event after a crash |
| IPC / interrupts | Signals, Updates & queries | Human-in-the-loop, mid-flight steering |
| Memory / state | Workflow state | Survives restarts — no Redis, no S3 checkpoints |
| Drivers | Activities | All side-effects, retried & idempotent by default |
| Long-lived sleep | `workflow.sleep()` | Pause days/weeks at zero CPU cost |

> *What Linux did for processes, Temporal does for agent loops.*

What this demo strips out — that you'd otherwise be writing yourself: no Celery, no Redis-backed queue, no hand-rolled retry policy, no "save progress to S3" code, no state machine for human approvals, no orphan-child cleanup on worker restart. **Temporal owns all of it.** What's left on top is just the agent logic.

---

## Architecture at a glance

```mermaid
graph TD
    UI["React UI<br/>(Vite + Tailwind)"]
    API["FastAPI<br/>(sole Temporal client)"]
    SQLITE[("SQLite<br/>run registry, idempotency")]
    TS["Temporal Service<br/>local host: <code>temporal server start-dev</code><br/>or Temporal Cloud namespace"]
    W["Temporal Worker<br/>workflows + activities<br/>+ OpenAIAgentsPlugin"]
    MOCK["Mockoon (host)<br/>market / news / broker / db"]
    SBX["Sandbox containers<br/>(TA-Lib + pandas;<br/>spawned per backtest)"]

    UI <-->|REST / SSE| API
    API <-->|gRPC| TS
    API --> SQLITE
    TS -->|poll| W
    W -->|HTTP| MOCK
    W -->|docker.sock| SBX
```

| Layer | Tech |
|---|---|
| Frontend | React 18 + Vite + Tailwind + shadcn primitives + recharts |
| Backend API | FastAPI (sole Temporal client) + SSE event bus |
| Workflows | `temporalio[openai-agents]>=1.17` — durable orchestration |
| LLM | OpenAI Agents SDK (`Agent` + `Runner` + `activity_as_tool`) wired into Temporal via `OpenAIAgentsPlugin` |
| Backtests | Per-strategy deterministic templates, executed in Docker sandboxes (TA-Lib pre-baked) |
| Mocked services | Mockoon Desktop (host) — market, news, broker, domain DB |
| App DB | SQLite (runs registry, idempotency keys, chaos log) |

---

## Sequence diagram

The diagram below shows the end-to-end flow: a user submits a ticker via the React UI, FastAPI starts a `ParentWorkflow` on Temporal, the worker fans out N parallel `BacktestWorkflow` children inside Docker sandboxes, the winning strategy drives a live tick loop where the OpenAI Agents SDK proposes trades through Temporal-managed activities, a deterministic risk guardrail filters them, large trades pause for human approval via signal, and chaos (kill-worker / inject-bad-news) is observed replaying from event history.

```mermaid
sequenceDiagram
    participant User as Operator
    participant UI as React UI
    participant API as FastAPI Backend
    participant Temporal as Temporal Service
    participant Worker as Temporal Worker
    participant Parent as ParentWorkflow
    participant Backtest as BacktestWorkflow (xN)
    participant Sandbox as Docker Sandbox
    participant Agent as OpenAI Agents SDK
    participant Mockoon as Mockoon (market/news/broker)

    User->>UI: Enter ticker (e.g. NVDA), Start
    UI->>API: POST /api/runs {ticker}
    API->>Temporal: start_workflow("ParentWorkflow", ticker, workflow_id)
    Temporal->>Worker: schedule on task queue

    Note over Parent, Backtest: PHASE 1 - Strategy Discovery (Fan-out)
    par 8 parallel backtests
        Parent->>Backtest: execute_child_workflow(strategy_i)
        Backtest->>Sandbox: spawn container (TA-Lib + pandas)
        Sandbox->>Mockoon: GET /market/ohlcv?ticker=NVDA
        Mockoon-->>Sandbox: historical OHLCV
        Sandbox-->>Backtest: metrics (sharpe, drawdown, pnl)
        Backtest-->>Parent: BacktestResult
    end
    Note over Parent: Pick winner by sharpe ratio
    Parent->>API: SSE event: backtests_complete

    Note over Parent, Agent: PHASE 2 - Live Tick Loop (every TICK_SECONDS)
    loop while !stop_signal
        Parent->>Agent: Runner.run(TradeIntentAgent, input)
        Note over Agent: Plugin-managed LLM activity
        Agent->>Worker: activity_as_tool: fetch_market_snapshot
        Worker->>Mockoon: GET /market/quote?ticker=NVDA
        Mockoon-->>Worker: latest quote
        Agent->>Worker: activity_as_tool: fetch_news_snapshot
        Worker->>Mockoon: GET /news?ticker=NVDA
        Mockoon-->>Worker: news items
        Agent-->>Parent: TradeIntent {action, qty, reason}

        Note over Parent: PHASE 3 - Deterministic Risk Guardrail
        Parent->>Worker: risk_check(intent, news_sentiment, position)
        alt risk = block
            Worker-->>Parent: block (bad news / position cap)
            Parent->>API: SSE event: trade_blocked
        else risk = allow
            alt notional > APPROVAL_THRESHOLD_USD
                Note over Parent: PHASE 4 - Human-in-the-Loop
                Parent->>API: SSE event: approval_required
                API->>UI: render approval modal
                User->>UI: Approve / Reject
                UI->>API: POST /api/runs/{id}/approve
                API->>Temporal: signal("human_review", decision)
                Temporal->>Parent: receive signal
            end
            Parent->>Worker: place_order(intent)
            Worker->>Mockoon: POST /broker/order
            Mockoon-->>Worker: fill confirmation
            Worker-->>Parent: OrderResult
            Parent->>API: SSE event: trade_executed
        end
    end

    Note over Parent, Worker: PHASE 5 - Chaos Resilience
    opt Kill Worker mid-activity
        User->>UI: Click "Kill Worker"
        UI->>API: POST /api/chaos/kill_worker
        Note over Worker: container exits mid-LLM-call
        Note over Temporal: event history preserved
        User->>UI: Click "Restart Worker"
        Worker->>Temporal: re-poll task queue
        Note over Parent: replay from last completed event
        Parent->>Agent: resume from exact line
    end

    User->>UI: Click Stop
    UI->>API: POST /api/runs/{id}/stop
    API->>Temporal: signal("stop")
    Parent-->>Temporal: workflow completes
```

---

## Key features

- **Durable agent orchestration** — every LLM call from the OpenAI Agents SDK is dispatched as a Temporal activity, automatically retried, and recorded in the workflow's event history.
- **Fan-out parallel backtests** — N sandboxed strategies execute concurrently via `execute_child_workflow`, each in an airgapped Docker container with TA-Lib + pandas pre-baked; the winner by Sharpe ratio drives the live loop.
- **Deterministic risk guardrail** — a plain Python activity (not the LLM) sits between trade intent and order placement; bad-news sentiment and position caps short-circuit before any broker call.
- **Human-in-the-loop approvals** — trades above `APPROVAL_THRESHOLD_USD` block the workflow until a `human_review` signal arrives from the React modal; the workflow consumes zero CPU while waiting.
- **Chaos-tolerant by construction** — kill the worker mid-LLM-call and Temporal replays the agent's decision history on restart; the activity resumes at the exact event.
- **Structured agent output** — `Agent(..., output_type=TradeIntent)` removes JSON-parsing fragility and surfaces typed intents to the workflow.
- **Live SSE event stream** — every market tick, LLM turn, tool call, risk decision, and approval is broadcast to the UI through a single FastAPI SSE channel.
- **Local- or Cloud-Temporal** — point the same code at `temporal server start-dev` or a Temporal Cloud namespace via `.env`; no code changes required for the address swap.
- **Mocked external world** — Mockoon Desktop serves market quotes, news, broker fills, and a domain DB on the host so the demo runs offline and stays deterministic on stage.

---

## Prerequisites (one-time host setup)

These run on your Mac/host, not inside Docker. **Compose only contains FastAPI + worker + frontend.**

### 1. Temporal Service — pick one

The FastAPI client and the worker both connect to a Temporal Service. You can point them at a local dev server **or** Temporal Cloud.

#### Option A — Local dev server (default)

Install the Temporal CLI: https://docs.temporal.io/cli — then start it:

```bash
temporal server start-dev --ip 0.0.0.0
```

- gRPC server: `:7233`
- Web UI: `:8233`

> `--ip 0.0.0.0` is required so Docker containers can reach it via `host.docker.internal:7233`. Without it, Temporal binds to `127.0.0.1` only and the worker container will fail with `NetworkUnreachable`.

#### Option B — Temporal Cloud

To point at a Cloud namespace instead, override the address + namespace in `.env`:

```bash
TEMPORAL_ADDRESS=<your-namespace>.<account>.tmprl.cloud:7233
TEMPORAL_NAMESPACE=<your-namespace>.<account>
```

You'll also need to enable TLS + an auth credential on the two `Client.connect(...)` call sites — [`backend/fastapi_app/temporal_client.py`](backend/fastapi_app/temporal_client.py) and [`backend/worker/main.py`](backend/worker/main.py). Either:

- **API key** (simpler): `tls=True, api_key="<your-key>"` — get one from the Cloud UI → API Keys.
- **mTLS cert** (per-namespace): `tls=TLSConfig(client_cert=..., client_private_key=...)` — see [Temporal Cloud mTLS docs](https://docs.temporal.io/cloud/certificates).

Skip the `start-dev` step entirely. The Temporal Web UI link in [`MissionControl.tsx:42`](frontend/src/components/MissionControl.tsx#L42) (which hardcodes `localhost:8233`) won't apply — open your workflow in the Cloud UI instead.

### 2. Mockoon (on host)

Install the Mockoon Desktop app: https://mockoon.com/download/ — then:

1. **File → Open environment** → pick `mockoon/demo.json` from this repo
2. Click ▶ Start (the env binds to `:3001`)

> Make sure Mockoon is bound to all interfaces, not just `127.0.0.1`. In Mockoon Desktop the default is fine. CLI alternative: `mockoon-cli start --data ./mockoon/demo.json --port 3001`.

### 3. Build the sandbox base image (one-time)

The sandbox image is NOT built by compose — it's a per-backtest sibling container, pre-baked with TA-Lib + pandas + pyarrow. Compile is ~5 min the first time:

```bash
docker build -t durable-agent-sandbox:latest sandbox/
```

Verify:
```bash
docker images | grep durable-agent-sandbox
```

### 4. Docker Desktop must be running

Compose builds containers; the worker also spawns sibling sandbox containers via `docker.sock`.

---

## Run the demo

```bash
cp .env.example .env
# Required: set OPENAI_API_KEY=sk-...
# Optional: tune TICK_SECONDS, APPROVAL_THRESHOLD_USD, NUM_SANDBOXES

docker compose up --build
```

Open:
- **Demo UI:** http://localhost:5173
- **Temporal Web UI:** http://localhost:8233 (your host install)
- **FastAPI docs:** http://localhost:8000/docs
- **Mockoon Desktop:** native app

Enter `NVDA`, click **Start Self-Evolving Agent**, watch:
1. War Room — 8 sandboxes spin up, each running a deterministic backtest in a fresh Docker container. Winner glows.
2. Trading Floor — live tick loop every 10s, the OpenAI Agent decides BUY/SELL/HOLD, risk guardrail filters, big trades pop an approval modal.
3. Open the Temporal Web UI in a side tab — show the audience every LLM call as a `StartActivityTask` event in history.

### Stage choreography

See [§9 of the design spec](docs/superpowers/specs/2026-05-21-self-evolving-stock-agent-design.md#9-stage-demo-script-target-1012-min) for the minute-by-minute script. Key moments:

| Time | Chaos action | Audience sees |
|---|---|---|
| ~3:00 | **Inject Bad News** | Next tick: news flips negative, risk_check returns `block`, trade doesn't fire |
| ~4:30 | **Fast Forward** + clean news | Trade intent → BUY → approval modal pops |
| ~6:00 | **Kill Worker** | Agent freezes mid-activity |
| ~6:15 | **Restart Worker** | Open Temporal UI — replay continues from the exact event, activity completes |

---

## Screenshots

A guided tour of the demo as it runs. Each shot maps to a phase from the [sequence diagram](#sequence-diagram) above.

### 1. War Room — parallel backtest fan-out (Phase 1)
8 sandboxed strategies run concurrently in airgapped Docker containers; the winner (highlighted) drives the live tick loop.

![War Room with 8 parallel backtests, winner highlighted](docs/screenshots/1.png)

### 2. Temporal Web UI — backtest fan-out timeline
The Temporal timeline view shows N `BacktestSandboxWorkflow` children executing in parallel, followed by the first live-tick activities (`fetch_market_snapshot`, `fetch_news_snapshot`, `invoke_model_activity`, `risk_check`, `notify_ui`).

![Temporal timeline: parallel BacktestSandboxWorkflow children and start of tick loop](docs/screenshots/2.png)

### 3. Human-in-the-loop approval modal (Phase 4)
Any trade above `APPROVAL_THRESHOLD_USD` blocks the workflow until the operator approves or rejects. The workflow consumes zero CPU while waiting on the `human_review` signal.

![Approval modal with trade details, risk reason, and approve/reject buttons](docs/screenshots/3.png)

### 4. Temporal Web UI — tick loop with chaos event
A live tick: agent calls tools (`fetch_market_snapshot`, `fetch_news_snapshot`), `invoke_model_activity` runs the LLM, `risk_check` allows, `place_order` + `approve_trade` complete. Mid-loop, `inject_news` chaos lands as a signal recorded in history.

![Temporal timeline showing live tick activities and inject_news chaos signal](docs/screenshots/4.png)

### 5. Kill Worker — workflow task timed out
After clicking **Kill Worker**, Temporal records a `WORKFLOW_TASK_TIMED_OUT` event. The workflow itself is unharmed — event history is preserved on the Temporal Service and replay will resume on the next worker.

![Temporal Web UI showing Workflow Task Timed Out banner after kill](docs/screenshots/5.png)

### 6. Worker restart — resume from the exact event (Phase 5)
Banner: *"Worker up. Temporal replayed event history and resumed the Agent loop from the exact event it was on — no lost state, no retry from scratch."* Trade intents pre-kill are preserved; the loop continues.

![UI banner confirming worker restart and replay; trade intents intact](docs/screenshots/6.png)

### 7. Mockoon Desktop — mocked external services
Mockoon serves the market, news, broker, and domain-DB endpoints on `:3001` so the demo runs offline and stays deterministic on stage.

![Mockoon Desktop with /market, /news, /broker, /db routes configured](docs/screenshots/7.png)

### 8. Temporal Web UI — multi-tick history with retry attempts
Zoomed timeline showing multiple tick iterations after **Fast Forward**, including `place_order` with an `Attempt N/50` indicator — visual proof that activities are durably retried by Temporal.

![Temporal timeline across several ticks with attempt counters on place_order](docs/screenshots/8.png)

### 9. Temporal Web UI — risk guardrail blocks a trade
After **Inject Bad News**, `risk_check` returns `block` and `reject_trade` is recorded in history instead of `place_order` — the deterministic guardrail short-circuits before the broker call.

![Temporal timeline showing reject_trade event after inject_bad_news](docs/screenshots/9.png)

---

## Project layout

```
durable-agentic-harness/
├── README.md                                ← you are here
├── AGENTS.md                                ← canonical AI-agent context
├── docker-compose.yml                       ← fastapi + worker + frontend (no Temporal / Mockoon)
├── .env.example
├── docs/superpowers/{specs,plans}/          ← design spec + implementation plan
├── project_description.md                   ← original brainstorm
├── frontend/                                ← Vite + React + shadcn UI
├── backend/
│   ├── pyproject.toml                       ← temporalio[openai-agents], openai-agents
│   ├── Dockerfile.{fastapi,worker}
│   ├── shared/                              ← Pydantic models, prompts, settings
│   ├── fastapi_app/                         ← sole Temporal client + REST + SSE
│   └── worker/
│       ├── main.py                          ← Worker with OpenAIAgentsPlugin
│       ├── workflows/{parent,backtest,hello}.py
│       └── activities/                      ← market, news, broker, risk, persist, ui, backtest
├── mockoon/demo.json                        ← load into Mockoon Desktop on host
└── sandbox/                                 ← TA-Lib + pandas Docker base image
```

---

## The Durable Harness — How the OpenAI Agents SDK integrates with Temporal (wrapping `Runner.run` in a Temporal workflow)

The core architectural move is small but consequential: **call the OpenAI Agents SDK's `Runner.run()` *from inside* a Temporal workflow.** That single line — `await Runner.run(agent, input=msg)` — when made from a `@workflow.defn`, becomes the durable harness around the agent loop. The workflow is the harness; the agent loop is what runs inside it.

Three things click together to make it durable, using the canonical `temporalio.contrib.openai_agents` pattern from [temporal-community/openai-agents-demos](https://github.com/temporal-community/openai-agents-demos):

**1. `OpenAIAgentsPlugin` lifts every LLM call into a Temporal activity.** Each model invocation the Agents SDK makes is automatically dispatched as an activity — retried per policy, journaled in event history — with zero glue code on the application side.

```python
# backend/worker/main.py
client = await Client.connect(
    settings.temporal_address,
    plugins=[OpenAIAgentsPlugin(
        model_params=ModelActivityParameters(
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=RetryPolicy(initial_interval=timedelta(seconds=1), ...),
        ),
    )],
    ...
)
```

**2. `activity_as_tool(...)` lifts every tool the Agent can call into a Temporal activity.** The Agent thinks it's calling a regular Python function; Temporal sees a durable, retryable activity with timeouts and idempotency.

**3. `output_type=TradeIntent` makes the Agent emit a typed Pydantic object** — no JSON-parse-and-pray glue between the LLM and the workflow.

```python
# backend/worker/workflows/parent.py — _run_trade_agent()
agent = Agent(
    name="TradeIntentAgent",
    instructions=LIVE_AGENT_PROMPT,
    tools=[
        temporal_agents.workflow.activity_as_tool(
            fetch_market_snapshot, start_to_close_timeout=timedelta(seconds=30),
        ),
        temporal_agents.workflow.activity_as_tool(
            fetch_news_snapshot, start_to_close_timeout=timedelta(seconds=30),
        ),
    ],
    output_type=TradeIntent,
)
result = await Runner.run(agent, input=input_msg, max_turns=20)   # ← durable harness
```

**What "durable harness" actually buys you:** kill the worker mid-`Runner.run` — even mid-LLM-call, even between tool invocations. The next worker that polls the task queue picks up the same workflow execution, replays event history up to the last completed event, and the agent resumes its multi-turn reasoning from that exact point. Same tools already called, same intermediate state, no retry-from-scratch, no lost reasoning chain.

**What you get for free:**
- Every LLM call the Agent makes is dispatched as a Temporal activity (durable, retryable, in event history)
- Tool invocations route through `fetch_market_snapshot` / `fetch_news_snapshot` activities — also durable
- Worker crash mid-agent-loop: Temporal replays from the last completed event when the worker restarts
- The Agent's structured `output_type=TradeIntent` removes any JSON-parsing fragility

> *The harness is the workflow. The LLM is just an activity. Everything between — retries, state, replay, approvals, fan-out — is Temporal.*

---

## Environment variables

See [`.env.example`](.env.example) for the full list. The important ones:

| Var | Default | Notes |
|---|---|---|
| `OPENAI_API_KEY` | _required_ | Your OpenAI key (used by the Agent's plugin-managed activity) |
| `OPENAI_MODEL` | `gpt-4o-mini` | Bump to `gpt-4o` if the agent struggles with multi-turn reasoning |
| `TEMPORAL_ADDRESS` | `host.docker.internal:7233` | Container-side address for host's Temporal |
| `DATA_MODE` | `mock` | `mock` = all Mockoon; `live` = Yahoo Finance for OHLCV + quotes |
| `TICK_SECONDS` | `10` | Live loop tick interval |
| `APPROVAL_THRESHOLD_USD` | `10000` | Trades above this $ amount require human approval |
| `NUM_SANDBOXES` | `8` | Parallel backtests per Phase 1 |
| `SANDBOX_NETWORK_DISABLED` | `true` | Sandboxes run offline (just file I/O) |
| `FASTAPI_INTERNAL_TOKEN` | `demo-token-change-me` | Shared token for worker→fastapi event POSTs |

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `worker` exits with `NetworkUnreachable [fdc4:...]` | Temporal isn't bound to all interfaces. Restart with `temporal server start-dev --ip 0.0.0.0`. The compose worker has IPv6 disabled via sysctl, so it forces IPv4 lookup for `host.docker.internal`. |
| `worker` exits with `ModuleNotFoundError: No module named 'worker'` | The FastAPI Dockerfile is missing the `COPY worker/` line. Should already be fixed; rebuild with `docker compose up -d --build fastapi`. |
| `fetch_market_snapshot` returns `Expecting value: line 1 column N` | Mockoon Desktop has an old `demo.json` loaded. Stop + reload the env. Check templates render cleanly with `curl -i http://localhost:3001/market/quote?ticker=NVDA`. |
| `pyarrow` / `parquet` ImportError in worker | Rebuild worker (`docker compose up -d --build worker`) so it picks up the latest `pyproject.toml`. |
| Agents SDK `MaxTurnsExceeded (10)` | Model is looping on tools. Bump `OPENAI_MODEL=gpt-4o` in `.env`, or drop `tools=[...]` from the `Agent(...)` definition in [`parent.py`](backend/worker/workflows/parent.py). |
| `ValueError: no successful backtests` | All 8 sandboxes failed. Check `docker images | grep durable-agent-sandbox` — image must exist. If missing, run `docker build -t durable-agent-sandbox:latest sandbox/`. |
| UI says "no active run" but workflow is running in Temporal Web UI | The auto-attach hook hits `/api/runs/` and re-attaches to the most recent. Hit **Cmd+Shift+R**. Top-right of the header has a ✕ to detach + start fresh. |
| Frontend can't reach FastAPI through proxy | Vite proxy needs FastAPI on `:8000`. SSE bypasses the proxy via `http://localhost:8000` directly (FastAPI CORS allows `:5173`). |

---

## Demo commands cheatsheet

```bash
# Fresh start (rebuild everything; nuke volumes)
docker compose down -v
docker volume rm sandbox-data 2>/dev/null || true
docker compose up --build

# Restart just the worker after code changes
docker compose up -d --build worker

# Watch worker logs (live)
docker compose logs worker -f

# Watch FastAPI logs
docker compose logs fastapi -f

# Terminate a stuck workflow
temporal workflow terminate -w agent-NVDA-XXXXXXXX --reason "manual cleanup"

# Smoke test a Mockoon endpoint
curl -s "http://localhost:3001/market/quote?ticker=NVDA" | jq

# Smoke test FastAPI health
curl -s http://localhost:8000/health | jq

# List recent runs from SQLite
curl -s http://localhost:8000/api/runs/ | jq
```

---

## What's NOT in v1 (deferred)

- **Crash Broker / Restart Broker chaos buttons** — Mockoon runs on the host now (Mockoon Desktop), so the user stops/starts it there directly.
- **LLM-generated backtest code** — for stage reliability, backtests use deterministic templates per strategy family ([`backtest_template.py`](backend/worker/activities/backtest_template.py)). The script is still shown in the War Room UI; the OpenAI call is just skipped at Phase 1.
- **Broker MCP server** — `place_order` activity hits Mockoon directly. MCP gateway is a v2 enhancement.
- **Slack / Telegram approval** — approvals happen in the in-app React modal.

---

## Temporal Cloud configuration

The app works against either a local `temporal server start-dev` instance **or** a Temporal Cloud namespace. The default `.env.example` points at the local server; switch by changing two variables and adding an auth credential.

### Switching to Temporal Cloud

1. **Obtain Temporal Cloud credentials:**
   - Sign up for [Temporal Cloud](https://temporal.io/cloud).
   - Create a namespace (e.g. `my-namespace.account-id`).
   - Generate an API key from the Cloud console under **Settings → API Keys**, or provision an mTLS certificate per the [Cloud mTLS docs](https://docs.temporal.io/cloud/certificates).

2. **Update your `.env`:**

   ```bash
   TEMPORAL_ADDRESS=my-namespace.account-id.tmprl.cloud:7233
   TEMPORAL_NAMESPACE=my-namespace.account-id
   TEMPORAL_TASK_QUEUE=durable-agent-tq

   # API key auth (simpler)
   TEMPORAL_API_KEY=your-actual-api-key-here

   # OR mTLS (per-namespace certs)
   # TEMPORAL_TLS_CERT_PATH=/path/to/client.pem
   # TEMPORAL_TLS_KEY_PATH=/path/to/client.key
   ```

3. **Enable TLS on the two `Client.connect(...)` call sites:**

   - [`backend/fastapi_app/temporal_client.py`](backend/fastapi_app/temporal_client.py)
   - [`backend/worker/main.py`](backend/worker/main.py)

   Pass `tls=True, api_key=settings.temporal_api_key` for API key auth, or `tls=TLSConfig(client_cert=..., client_private_key=...)` for mTLS.

4. **Restart the worker and FastAPI containers:**

   ```bash
   docker compose up -d --build worker fastapi
   ```

   No local `temporal server start-dev` is needed — open workflow history in the Temporal Cloud UI instead of `localhost:8233`. The hardcoded link in [`MissionControl.tsx:42`](frontend/src/components/MissionControl.tsx#L42) won't apply.

### Temporal Cloud benefits

- **Zero infrastructure** — no local server to babysit; Temporal handles persistence, scaling, and upgrades.
- **High availability** — multi-AZ replication and automatic failover for the orchestration layer.
- **Built-in observability** — workflow history, metrics, and search attributes are exposed through the Cloud UI without extra setup.
- **Security** — TLS in transit, API key or mTLS auth, and per-namespace isolation.
- **Same code, same demo** — the worker and activities are unchanged; the only delta is the connection config in `.env`.

---

## Contributing

Contributions are welcome — bug fixes, new chaos buttons, alternative LLM providers, or polish on the stage script.

### Getting started

1. Fork the repository and clone your fork.
2. Create a feature branch: `git checkout -b feat/your-feature-name`.
3. Read [`AGENTS.md`](AGENTS.md) for the canonical project context AI-assisted coding agents should follow.
4. Make your changes, keeping the demo green: `docker compose up --build` should still complete the choreography end-to-end.
5. Commit with a descriptive message and open a Pull Request against `main` describing the change and how to verify it.

### Contribution ideas

- **Additional LLM providers** — swap the `OpenAIAgentsPlugin` for an Anthropic / Bedrock / local Ollama provider.
- **Real market data** — replace Mockoon endpoints with live providers (Yahoo Finance, Polygon, Alpaca) behind the existing activity contracts.
- **Broker MCP gateway** — implement the deferred MCP server for `place_order` instead of hitting Mockoon directly.
- **Slack / Telegram approvals** — wire the `human_review` signal to an out-of-app approval channel.
- **More strategy templates** — extend [`backtest_template.py`](backend/worker/activities/backtest_template.py) with new deterministic strategy families.
- **End-to-end tests** — Playwright runs through the demo script and asserts the workflow completes after a kill-worker chaos event.
- **Frontend polish** — additional War Room visualizations, equity-curve overlays, or a replay scrubber over Temporal event history.

### Code standards

- Match the existing style: typed Python (Pydantic models in `backend/shared/`), function-style React components with Tailwind, no implicit `any` in TypeScript.
- Keep workflows deterministic — no `datetime.now()`, `random`, network I/O, or filesystem access outside an activity.
- Activities own all side effects; workflows only orchestrate.
- Update [`AGENTS.md`](AGENTS.md) and the relevant [`docs/superpowers/specs/`](docs/superpowers/specs/) entry if you change the demo contract.
- Confirm `docker compose up --build` still runs the full choreography before opening a PR.

---

## Supporting docs
1. **Canonical context for AI/coding agents:** [`AGENTS.md`](AGENTS.md)
2. **Locked design spec:** [`docs/superpowers/specs/2026-05-21-self-evolving-stock-agent-design.md`](docs/superpowers/specs/2026-05-21-self-evolving-stock-agent-design.md)
3. **Implementation plan & history:** [`docs/superpowers/plans/2026-05-21-self-evolving-stock-agent-plan.md`](docs/superpowers/plans/2026-05-21-self-evolving-stock-agent-plan.md)
4. **Original brainstorm:** [`project_description.md`](project_description.md)

---

## License & credits

This project is released under the MIT License.

```
MIT License

Copyright (c) 2026 Temporal Technologies

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

Inspiration drawn from:
- [temporal-community/temporal-ai-agent](https://github.com/temporal-community/temporal-ai-agent)
- [temporal-community/openai-agents-demos](https://github.com/temporal-community/openai-agents-demos)
- [temporal-sa/agentic-loan-origination](https://github.com/temporal-sa/agentic-loan-origination) — sequence-diagram + Temporal Cloud README structure
- [Temporal blog: Introducing Temporal and Agentic Sandboxes for the OpenAI Agents SDK](https://temporal.io/blog/introducing-temporal-and-agentic-sandboxes-openai-agents-sdk)
