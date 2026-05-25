# Temporal: The Durable Operating System for Agentic AI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a stage-ready demo that runs an autonomous stock-trading agent inside a Temporal durable workflow — discovering, executing, and chaos-surviving — to show how Temporal is the **durable OS for agentic AI** (autosave, guardrails, observability, long-lived coordination).

**Architecture:** React UI → FastAPI (sole Temporal client) → Temporal Server (on host) → Worker (workflows + activities) → Mockoon on host (mocked market/news/broker/DB) + Docker sandbox per backtest. See [`docs/superpowers/specs/2026-05-21-self-evolving-stock-agent-design.md`](../specs/2026-05-21-self-evolving-stock-agent-design.md).

**Tech Stack:** Python 3.12 (`temporalio`, `openai`, `fastapi`, `pydantic`, `httpx`, `yfinance`, `pandas`, `pyarrow`, `docker`), TypeScript (Vite, React 18, shadcn/ui, Tailwind, recharts), Mockoon Desktop on host, Temporal `start-dev` on host, SQLite, Docker Compose.

---

## v2 simplification (applied 2026-05-22)

After end-to-end implementation, the demo scope was tightened. The following items are **CUT from v1** and are kept here only as historical task descriptions. Do NOT implement them.

| Cut item | Where it appears in this plan | Replacement |
|---|---|---|
| Phase 4 drift detection + re-evolution loop | Task 31 (`check_drift` activity), Task 32 (drift loop-back in parent) | Workflow exits cleanly after Phase 2+3. `check_drift` activity removed. Phase-4 stage moment removed from §9 of the spec. |
| `force_drift` signal | Inside Task 26 (parent signals) and Task 34 (chaos route) and Task 35 (button) | Removed everywhere. |
| `Crash Broker` / `Restart Broker` chaos buttons | Task 33 (chaos backend) and Task 34 (chaos routes) and Task 35 (panel UI) | Mockoon runs on host via Mockoon Desktop — user stops/starts it there. The two routes and buttons are removed. |
| LLM-generated backtest code (OpenAI Agents SDK SandboxAgent) | Task 13 (`run_backtest_in_sandbox`) | Replaced by deterministic `backtest_template.build_backtest_code(strategy_spec, data_path)` per family (RSI/MACD/EMA/Bollinger/Mean-Reversion). Sandbox still runs the script in Docker. |
| Compose-bundled Temporal + Mockoon | Task 8 (`docker-compose.yml`) | Both moved to host. Compose only has `fastapi`, `worker`, `frontend`. Containers reach the host via `host.docker.internal`. |
| `temporalio.contrib.openai_agents` Temporal-aware sandbox | Task 13 | Direct `docker` SDK call from the activity. |

---

## Phase Map (milestone gates)

| Phase | Tasks | Demoable milestone |
|---|---|---|
| **A — Foundation** | 1–10 | `docker compose up` succeeds; "hello" workflow runs end-to-end from FastAPI; frontend boots |
| **B — Phase 1: War Room** | 11–21 | Submit ticker → N parallel deterministic backtests → winner highlighted in UI |
| **C — Phase 2+3: Trading Floor** | 22–30 | Live loop ticks → intents → risk check → approval modal → broker order |
| **D — Chaos** | 33–36 (drift tasks 31–32 cut) | Chaos panel kills/restarts worker mid-trade with Temporal recovery; Inject Bad News blocks; Fast Forward paces |

---

## File Structure (lock decomposition before tasks)

```
durable-agentic-harness/
├── AGENTS.md                            (exists)
├── docker-compose.yml                   Task 8
├── .env.example                         Task 1
├── .gitignore                           Task 1
├── README.md                            Task 1
├── docs/superpowers/{specs,plans}/      (exists)
├── frontend/
│   ├── Dockerfile                       Task 9
│   ├── package.json                     Task 9
│   ├── vite.config.ts                   Task 9
│   ├── tailwind.config.ts               Task 9
│   ├── tsconfig.json                    Task 9
│   ├── index.html                       Task 9
│   ├── components.json                  Task 9
│   └── src/
│       ├── main.tsx                     Task 9
│       ├── App.tsx                      Tasks 9, 19, 28, 35
│       ├── index.css                    Task 9
│       ├── types.ts                     Task 18
│       ├── lib/{api.ts, utils.ts}       Task 18
│       ├── hooks/{useSSE,useWorkflow,useChaos}.ts   Tasks 18, 35
│       └── components/
│           ├── MissionControl.tsx       Task 19
│           ├── WarRoom.tsx              Task 20
│           ├── TradingFloor.tsx         Task 28
│           ├── ApprovalModal.tsx        Task 29
│           ├── ChaosPanel.tsx           Task 35
│           ├── EventLog.tsx             Task 19
│           └── ui/                      Task 9 (shadcn primitives)
├── backend/
│   ├── pyproject.toml                   Task 3
│   ├── Dockerfile.fastapi               Task 3
│   ├── Dockerfile.worker                Task 3
│   ├── shared/
│   │   ├── __init__.py                  Task 4
│   │   ├── settings.py                  Task 4
│   │   ├── constants.py                 Task 4
│   │   ├── models.py                    Task 4
│   │   ├── prompts.py                   Task 4
│   │   ├── strategies.py                Task 4
│   │   └── openai_client.py             Task 4
│   ├── fastapi_app/
│   │   ├── __init__.py                  Task 7
│   │   ├── main.py                      Tasks 7, 16, 17, 27, 34
│   │   ├── temporal_client.py           Task 7
│   │   ├── db.py                        Task 7
│   │   ├── events.py                    Task 17 (SSE pub/sub bus)
│   │   ├── chaos.py                     Task 33
│   │   └── routes/{runs,events,approvals,internal,chaos}.py
│   ├── worker/
│   │   ├── __init__.py                  Task 6
│   │   ├── main.py                      Tasks 6, 14, 15, 26, 32
│   │   ├── workflows/{parent,backtest}.py
│   │   └── activities/
│   │       ├── persist.py               Task 11
│   │       ├── ui.py                    Task 11
│   │       ├── market.py                Tasks 12, 22
│   │       ├── news.py                  Task 22
│   │       ├── backtest.py              Task 13
│   │       ├── llm.py                   Task 23
│   │       ├── risk.py                  Task 24
│   │       ├── broker.py                Task 25
│   │       └── drift.py                 Task 31
│   └── tests/
│       ├── conftest.py                  Task 4
│       ├── unit/{test_risk,test_drift,test_select_winner,test_models}.py
│       ├── workflows/{test_parent_replay,test_backtest_replay}.py
│       └── e2e/test_smoke.py
├── mockoon/
│   └── demo.json                        Task 2
└── sandbox/
    ├── Dockerfile                       Task 5
    └── runner.py                        Task 5
```

---

# PHASE A — Foundation (Tasks 1–10)

## Task 1: Repository scaffold

**Files:**
- Create: `.gitignore`, `.env.example`, `README.md`

- [ ] **Step 1: Create `.gitignore`**

```gitignore
# Python
__pycache__/
*.pyc
.venv/
.pytest_cache/
.ruff_cache/
*.egg-info/
dist/
build/

# Node
node_modules/
.vite/
dist/
*.local

# Env / secrets
.env
.env.local
backend/fastapi_app/db.sqlite3
backend/fastapi_app/db.sqlite3-journal

# OS
.DS_Store

# Docker
.docker/
```

- [ ] **Step 2: Create `.env.example`**

```dotenv
OPENAI_API_KEY=sk-replace-me
# Temporal runs on the host (not in compose). From inside containers we reach it via host.docker.internal.
# Host-side scripts use localhost:7233.
TEMPORAL_ADDRESS=host.docker.internal:7233
TEMPORAL_NAMESPACE=default
TEMPORAL_TASK_QUEUE=stock-agent
DATA_MODE=mock
TICK_SECONDS=10
DRIFT_THRESHOLD=0.20
APPROVAL_THRESHOLD_USD=10000
NUM_SANDBOXES=8
MOCKOON_BASE_URL=http://mockoon:3001
FASTAPI_INTERNAL_URL=http://fastapi:8000
FASTAPI_INTERNAL_TOKEN=demo-token-change-me
SANDBOX_IMAGE=durable-agent-sandbox:latest
SANDBOX_NETWORK_DISABLED=true
LOG_LEVEL=INFO
OPENAI_MODEL=gpt-4o-mini
```

- [ ] **Step 3: Create `README.md`**

```markdown
# Durable Agentic Harness — Self-Evolving Stock Agent

A demo proving Temporal is the production-grade harness for agentic AI. See [`AGENTS.md`](AGENTS.md) for the project bible and [`docs/superpowers/specs/`](docs/superpowers/specs/) for the locked design.

## Quick start

```bash
cp .env.example .env
# Edit .env: set OPENAI_API_KEY
docker compose build
docker compose up
```

Open:
- Demo UI: http://localhost:5173
- Temporal Web UI: http://localhost:8233
- FastAPI docs: http://localhost:8000/docs

## Stage demo

See [`docs/superpowers/specs/2026-05-21-self-evolving-stock-agent-design.md`](docs/superpowers/specs/2026-05-21-self-evolving-stock-agent-design.md) §9.
```

- [ ] **Step 4: Commit**

```bash
git add .gitignore .env.example README.md
git commit -m "chore: scaffold repo with gitignore, env example, README"
```

---

## Task 2: Mockoon fixture file

**Files:**
- Create: `mockoon/demo.json`

- [ ] **Step 1: Create `mockoon/demo.json` with all mocked endpoints**

This Mockoon environment defines every external service the worker hits when `DATA_MODE=mock`.

```json
{
  "uuid": "demo-env",
  "lastMigration": 33,
  "name": "Durable Agent Demo",
  "endpointPrefix": "",
  "latency": 0,
  "port": 3001,
  "hostname": "0.0.0.0",
  "routes": [
    {
      "uuid": "r-prices",
      "method": "get",
      "endpoint": "market/prices",
      "responses": [{
        "statusCode": 200,
        "body": "{\"ticker\":\"{{queryParam 'ticker'}}\",\"range\":\"{{queryParam 'range'}}\",\"ohlcv\":[{{#repeat 750 comma=true}}{\"t\":{{add @index 1700000000}},\"o\":{{float 100 200}},\"h\":{{float 100 220}},\"l\":{{float 80 180}},\"c\":{{float 100 220}},\"v\":{{int 1000000 5000000}}}{{/repeat}}]}",
        "headers": [{"key": "Content-Type", "value": "application/json"}]
      }]
    },
    {
      "uuid": "r-quote",
      "method": "get",
      "endpoint": "market/quote",
      "responses": [{
        "statusCode": 200,
        "body": "{\"ticker\":\"{{queryParam 'ticker'}}\",\"price\":{{float 140 180}},\"ts\":{{now 'unix'}}}",
        "headers": [{"key": "Content-Type", "value": "application/json"}]
      }]
    },
    {
      "uuid": "r-indicators",
      "method": "get",
      "endpoint": "market/indicators",
      "responses": [{
        "statusCode": 200,
        "body": "{\"ticker\":\"{{queryParam 'ticker'}}\",\"rsi\":{{float 25 75}},\"ema12\":{{float 140 175}},\"ema26\":{{float 138 172}},\"macd\":{{float -2 2}},\"bb_upper\":{{float 175 190}},\"bb_lower\":{{float 130 150}}}",
        "headers": [{"key": "Content-Type", "value": "application/json"}]
      }]
    },
    {
      "uuid": "r-headlines",
      "method": "get",
      "endpoint": "news/headlines",
      "responses": [{
        "statusCode": 200,
        "body": "{\"ticker\":\"{{queryParam 'ticker'}}\",\"headlines\":[{\"title\":\"{{queryParam 'ticker'}} beats earnings expectations\",\"published_at\":{{now 'unix'}}},{\"title\":\"Analyst upgrades {{queryParam 'ticker'}} to Buy\",\"published_at\":{{now 'unix'}}}]}",
        "headers": [{"key": "Content-Type", "value": "application/json"}]
      }]
    },
    {
      "uuid": "r-sentiment",
      "method": "get",
      "endpoint": "news/sentiment",
      "responses": [{
        "statusCode": 200,
        "body": "{\"ticker\":\"{{queryParam 'ticker'}}\",\"score\":{{float -0.5 0.7}},\"rationale\":\"Recent coverage shows mixed-to-positive sentiment\"}",
        "headers": [{"key": "Content-Type", "value": "application/json"}]
      }]
    },
    {
      "uuid": "r-orders",
      "method": "post",
      "endpoint": "broker/orders",
      "responses": [{
        "statusCode": 200,
        "body": "{\"orderId\":\"ord-{{shuffle 'a' 'b' 'c'}}{{int 1000 9999}}\",\"status\":\"filled\",\"filledQty\":{{body 'qty' 1}},\"avgPrice\":{{float 140 180}}}",
        "headers": [{"key": "Content-Type", "value": "application/json"}]
      }]
    },
    {
      "uuid": "r-db-trades",
      "method": "post",
      "endpoint": "db/trades",
      "responses": [{"statusCode": 200, "body": "{\"stored\":true}", "headers": [{"key": "Content-Type", "value": "application/json"}]}]
    },
    {
      "uuid": "r-db-strategy",
      "method": "post",
      "endpoint": "db/strategy",
      "responses": [{"statusCode": 200, "body": "{\"stored\":true}", "headers": [{"key": "Content-Type", "value": "application/json"}]}]
    },
    {
      "uuid": "r-db-audit",
      "method": "post",
      "endpoint": "db/audit",
      "responses": [{"statusCode": 200, "body": "{\"stored\":true}", "headers": [{"key": "Content-Type", "value": "application/json"}]}]
    }
  ]
}
```

- [ ] **Step 2: Verify Mockoon syntax loads**

Run: `docker run --rm -v "$(pwd)/mockoon":/data -p 3001:3001 mockoon/cli:latest --data /data/demo.json --port 3001`

Expected: log line "Server started on port 3001". Stop with Ctrl-C.

- [ ] **Step 3: Smoke-test one endpoint**

In another terminal, after starting Mockoon: `curl -s http://localhost:3001/market/quote?ticker=NVDA | jq`

Expected: JSON `{ticker, price, ts}`.

- [ ] **Step 4: Commit**

```bash
git add mockoon/demo.json
git commit -m "feat(mockoon): add fake market/news/broker/db fixtures"
```

---

## Task 3: Backend Python project (`pyproject.toml` + Dockerfiles)

**Files:**
- Create: `backend/pyproject.toml`, `backend/Dockerfile.fastapi`, `backend/Dockerfile.worker`

- [ ] **Step 1: Create `backend/pyproject.toml`**

```toml
[project]
name = "durable-agentic-harness"
version = "0.1.0"
description = "Self-evolving stock agent powered by Temporal + OpenAI Agents SDK"
requires-python = ">=3.12,<3.13"
dependencies = [
  "temporalio>=1.9.0",
  "openai>=1.50.0",
  "openai-agents>=0.2.0",
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.30.0",
  "httpx>=0.27.0",
  "pydantic>=2.8.0",
  "pydantic-settings>=2.4.0",
  "python-dotenv>=1.0.0",
  "structlog>=24.1.0",
  "sse-starlette>=2.1.0",
  "docker>=7.1.0",
  "yfinance>=0.2.40",
  "pandas>=2.2.0",
  "numpy>=1.26.0"
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0.0",
  "pytest-asyncio>=0.23.0",
  "pytest-httpx>=0.30.0",
  "ruff>=0.5.0",
  "black>=24.0.0"
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = ["e2e: end-to-end smoke tests requiring full compose stack"]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.black]
line-length = 100
target-version = ["py312"]
```

- [ ] **Step 2: Create `backend/Dockerfile.fastapi`**

```dockerfile
FROM python:3.12-slim AS base
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e .

COPY shared/ ./shared/
COPY fastapi_app/ ./fastapi_app/

EXPOSE 8000
CMD ["uvicorn", "fastapi_app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Create `backend/Dockerfile.worker`**

```dockerfile
FROM python:3.12-slim AS base
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

# Need docker CLI to talk to docker.sock for sandbox spawning
RUN apt-get update && apt-get install -y --no-install-recommends \
    docker.io ca-certificates curl && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e .

COPY shared/ ./shared/
COPY worker/ ./worker/

CMD ["python", "-m", "worker.main"]
```

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml backend/Dockerfile.fastapi backend/Dockerfile.worker
git commit -m "feat(backend): add pyproject and Dockerfiles for fastapi + worker"
```

---

## Task 4: Shared package (settings, models, prompts, openai client)

**Files:**
- Create: `backend/shared/__init__.py`, `settings.py`, `constants.py`, `models.py`, `prompts.py`, `strategies.py`, `openai_client.py`
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: Create `backend/shared/__init__.py`** (empty file marks the package).

- [ ] **Step 2: Create `backend/shared/settings.py`**

```python
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4o-mini", alias="OPENAI_MODEL")

    temporal_address: str = Field("temporal:7233", alias="TEMPORAL_ADDRESS")
    temporal_namespace: str = Field("default", alias="TEMPORAL_NAMESPACE")
    temporal_task_queue: str = Field("stock-agent", alias="TEMPORAL_TASK_QUEUE")

    data_mode: str = Field("mock", alias="DATA_MODE")  # "mock" | "live"
    tick_seconds: int = Field(10, alias="TICK_SECONDS")
    drift_threshold: float = Field(0.20, alias="DRIFT_THRESHOLD")
    approval_threshold_usd: float = Field(10000.0, alias="APPROVAL_THRESHOLD_USD")
    num_sandboxes: int = Field(8, alias="NUM_SANDBOXES")

    mockoon_base_url: str = Field("http://mockoon:3001", alias="MOCKOON_BASE_URL")
    fastapi_internal_url: str = Field("http://fastapi:8000", alias="FASTAPI_INTERNAL_URL")
    fastapi_internal_token: str = Field("demo-token-change-me", alias="FASTAPI_INTERNAL_TOKEN")

    sandbox_image: str = Field("durable-agent-sandbox:latest", alias="SANDBOX_IMAGE")
    sandbox_network_disabled: bool = Field(True, alias="SANDBOX_NETWORK_DISABLED")
    log_level: str = Field("INFO", alias="LOG_LEVEL")


settings = Settings()
```

- [ ] **Step 3: Create `backend/shared/constants.py`**

```python
from enum import Enum


class Phase(str, Enum):
    SYNTHESIZING = "SYNTHESIZING"
    WATCHING = "WATCHING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    EVOLVING = "EVOLVING"


class RiskDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    ALLOW_REQUIRES_APPROVAL = "allow_requires_approval"


class TradeAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


RESTRICTED_NEWS_TERMS = ("fraud", "sec probe", "bankruptcy", "trading halt", "delisting")
DRIFT_CHECK_TICK_INTERVAL = 5  # check drift every K ticks
```

- [ ] **Step 4: Create `backend/shared/models.py`**

```python
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field
from .constants import Phase, RiskDecision, TradeAction


class StrategySpec(BaseModel):
    id: str
    family: Literal["RSI", "MACD", "EMA_CROSS", "BOLLINGER", "MEAN_REVERSION"]
    params: dict[str, float | int]

    def to_prompt(self) -> str:
        return f"Implement a backtest for strategy family={self.family} with params={self.params}."


class TradeLimits(BaseModel):
    max_notional_per_trade: float = 50_000
    max_daily_notional: float = 200_000
    max_position_pct: float = 0.25


class AgentInput(BaseModel):
    ticker: str
    objective: str = "maximize Sharpe; max drawdown < 10%"
    history_range: str = "3y"
    num_sandboxes: int = 8
    candidate_strategies: list[StrategySpec]
    limits: TradeLimits = Field(default_factory=TradeLimits)
    approval_threshold: float = 10_000.0
    tick_seconds: int = 10
    drift_threshold: float = 0.20


class HistoricalDataRef(BaseModel):
    path: str  # path inside the shared volume
    rows: int
    ticker: str
    range: str


class Scorecard(BaseModel):
    strategy_id: str
    roi: float = 0.0
    sharpe: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    num_trades: int = 0
    generated_code: str = ""
    error: Optional[str] = None


class BacktestInput(BaseModel):
    strategy_spec: StrategySpec
    historical_data_ref: HistoricalDataRef
    sandbox_image: str


class MarketSnapshot(BaseModel):
    ticker: str
    price: float
    ts: int
    rsi: float
    ema12: float
    ema26: float
    macd: float
    bb_upper: float
    bb_lower: float


class NewsHeadline(BaseModel):
    title: str
    published_at: int


class NewsSnapshot(BaseModel):
    ticker: str
    headlines: list[NewsHeadline]
    sentiment: float
    rationale: str = ""


class Position(BaseModel):
    ticker: str
    qty: float = 0.0
    avg_price: float = 0.0


class Positions(BaseModel):
    by_ticker: dict[str, Position] = Field(default_factory=dict)

    def apply(self, order: "OrderResult") -> None:
        p = self.by_ticker.get(order.ticker) or Position(ticker=order.ticker)
        if order.side == "BUY":
            new_qty = p.qty + order.filled_qty
            p.avg_price = (p.qty * p.avg_price + order.filled_qty * order.avg_price) / max(new_qty, 1e-9)
            p.qty = new_qty
        else:
            p.qty -= order.filled_qty
        self.by_ticker[order.ticker] = p


class TradeIntent(BaseModel):
    id: str
    ticker: str
    action: TradeAction
    qty: float
    rationale: str


class AgentCallInput(BaseModel):
    winning_strategy: StrategySpec
    market: MarketSnapshot
    news: NewsSnapshot
    positions: Positions


class RiskCheckInput(BaseModel):
    intent: TradeIntent
    news: NewsSnapshot
    positions: Positions
    limits: TradeLimits
    approval_threshold: float


class RiskResult(BaseModel):
    decision: RiskDecision
    reason: str


class PlaceOrderInput(BaseModel):
    intent: TradeIntent
    idempotency_key: str


class OrderResult(BaseModel):
    order_id: str
    ticker: str
    side: Literal["BUY", "SELL"]
    status: str
    filled_qty: float
    avg_price: float


class DriftInput(BaseModel):
    baseline_sharpe: float
    live_roi: float
    backtest_roi: float
    threshold: float


class DriftResult(BaseModel):
    drifted: bool
    reason: str


class AuditEvent(BaseModel):
    ts: datetime
    kind: str
    payload: dict


class ApprovalRequest(BaseModel):
    trade_id: str
    workflow_id: str
    intent: TradeIntent
    risk: RiskResult
    news: NewsSnapshot


class UIEvent(BaseModel):
    ts: datetime
    workflow_id: str
    kind: str  # phase_change, backtest_progress, trade_intent, risk_decision, approval_request, order_placed, chaos, drift_detected, audit
    payload: dict
```

- [ ] **Step 5: Create `backend/shared/prompts.py`**

```python
BACKTEST_PROMPT = """\
You are a quantitative researcher writing Python code to backtest a trading strategy.

The historical OHLCV data is at /data/ohlcv.parquet (columns: t, o, h, l, c, v).
Use `pandas` to read it, `talib` for indicators, and produce a JSON scorecard.

The scorecard MUST be the LAST line you print, on its own line, as valid JSON:
{"strategy_id": "<id>", "roi": <float>, "sharpe": <float>, "max_drawdown": <float>, "win_rate": <float>, "num_trades": <int>}

Strategy spec follows. Write the code, run it, and print the scorecard.
"""

LIVE_AGENT_PROMPT = """\
You are a trading agent. Given the chosen strategy, current market snapshot, news, and current positions,
output exactly ONE JSON object matching TradeIntent: {id, ticker, action, qty, rationale}.

Rules:
- action must be one of BUY, SELL, HOLD.
- For HOLD, qty is 0.
- Be conservative: prefer HOLD if market conditions conflict with strategy.
- Never recommend qty > 100 shares in one trade.

Return ONLY the JSON, no prose.
"""
```

- [ ] **Step 6: Create `backend/shared/strategies.py`**

```python
from .models import StrategySpec


def default_candidate_strategies(n: int = 8) -> list[StrategySpec]:
    """Deterministic list of N candidate strategies covering 5 families."""
    base = [
        StrategySpec(id="rsi-14-30-70", family="RSI", params={"period": 14, "oversold": 30, "overbought": 70}),
        StrategySpec(id="macd-12-26-9", family="MACD", params={"fast": 12, "slow": 26, "signal": 9}),
        StrategySpec(id="ema-12-26", family="EMA_CROSS", params={"fast": 12, "slow": 26}),
        StrategySpec(id="ema-9-21", family="EMA_CROSS", params={"fast": 9, "slow": 21}),
        StrategySpec(id="bb-20-2", family="BOLLINGER", params={"period": 20, "std": 2.0}),
        StrategySpec(id="bb-10-1.5", family="BOLLINGER", params={"period": 10, "std": 1.5}),
        StrategySpec(id="mr-20", family="MEAN_REVERSION", params={"window": 20, "z_threshold": 1.5}),
        StrategySpec(id="rsi-7-25-75", family="RSI", params={"period": 7, "oversold": 25, "overbought": 75}),
    ]
    return base[:n]
```

- [ ] **Step 7: Create `backend/shared/openai_client.py`**

```python
from openai import AsyncOpenAI
from .settings import settings


def make_openai_client() -> AsyncOpenAI:
    """Single source of OpenAI clients. CRITICAL: max_retries=0 — Temporal handles retries."""
    return AsyncOpenAI(api_key=settings.openai_api_key, max_retries=0, timeout=30.0)
```

- [ ] **Step 8: Create `backend/tests/conftest.py`**

```python
import pytest
from datetime import datetime
from shared.models import (
    StrategySpec, TradeLimits, MarketSnapshot, NewsSnapshot, NewsHeadline,
    Positions, Position, TradeIntent,
)
from shared.constants import TradeAction


@pytest.fixture
def sample_strategy() -> StrategySpec:
    return StrategySpec(id="rsi-14-30-70", family="RSI",
                        params={"period": 14, "oversold": 30, "overbought": 70})


@pytest.fixture
def sample_market() -> MarketSnapshot:
    return MarketSnapshot(ticker="NVDA", price=150.0, ts=1700000000,
                          rsi=55.0, ema12=148.0, ema26=145.0, macd=0.5,
                          bb_upper=155.0, bb_lower=140.0)


@pytest.fixture
def sample_news_positive() -> NewsSnapshot:
    return NewsSnapshot(ticker="NVDA",
                        headlines=[NewsHeadline(title="NVDA beats earnings", published_at=1700000000)],
                        sentiment=0.6, rationale="positive coverage")


@pytest.fixture
def sample_news_negative() -> NewsSnapshot:
    return NewsSnapshot(ticker="NVDA",
                        headlines=[NewsHeadline(title="NVDA SEC probe announced", published_at=1700000000)],
                        sentiment=-0.7, rationale="restricted news term + low sentiment")


@pytest.fixture
def sample_intent_buy() -> TradeIntent:
    return TradeIntent(id="t-1", ticker="NVDA", action=TradeAction.BUY, qty=10, rationale="bullish")


@pytest.fixture
def sample_intent_big_buy() -> TradeIntent:
    return TradeIntent(id="t-2", ticker="NVDA", action=TradeAction.BUY, qty=100, rationale="bullish big")


@pytest.fixture
def empty_positions() -> Positions:
    return Positions()
```

- [ ] **Step 9: Verify imports**

Run: `cd backend && pip install -e ".[dev]" && python -c "from shared.models import AgentInput; from shared.settings import settings; print('ok')"`

(`settings()` import may fail because OPENAI_API_KEY isn't set — set a dummy in shell: `export OPENAI_API_KEY=test`.)

Expected: prints `ok`.

- [ ] **Step 10: Commit**

```bash
git add backend/shared backend/tests/conftest.py
git commit -m "feat(shared): add settings, models, prompts, strategies, openai client"
```

---

## Task 5: Sandbox base Docker image

**Files:**
- Create: `sandbox/Dockerfile`, `sandbox/runner.py`

- [ ] **Step 1: Create `sandbox/runner.py`**

```python
"""Helpers the LLM-written backtest code can import.

The LLM is instructed to print a JSON scorecard as the last line of stdout;
this module makes that easier by exposing a `print_scorecard(...)` helper.
"""
import json
import sys


def print_scorecard(strategy_id: str, *, roi: float, sharpe: float, max_drawdown: float,
                    win_rate: float, num_trades: int) -> None:
    out = {
        "strategy_id": strategy_id,
        "roi": roi,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "win_rate": win_rate,
        "num_trades": num_trades,
    }
    sys.stdout.flush()
    print(json.dumps(out))
```

- [ ] **Step 2: Create `sandbox/Dockerfile`**

```dockerfile
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

# Build deps for TA-Lib (C library)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential wget tar && rm -rf /var/lib/apt/lists/*

# Install TA-Lib C library
RUN wget -q https://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz \
    && tar -xzf ta-lib-0.4.0-src.tar.gz \
    && cd ta-lib \
    && ./configure --prefix=/usr \
    && make -j$(nproc) \
    && make install \
    && cd .. && rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

# Python deps for backtests
RUN pip install --upgrade pip && pip install \
    numpy==1.26.4 \
    pandas==2.2.2 \
    pyarrow==17.0.0 \
    ta-lib==0.4.32 \
    yfinance==0.2.40

WORKDIR /work
COPY runner.py /work/runner.py

# Sandbox is launched with the user-supplied entrypoint by the host;
# default holds the container open if no command is given (so we can `docker exec`).
CMD ["python", "-c", "import time; time.sleep(3600)"]
```

- [ ] **Step 3: Build the image**

Run from repo root: `docker build -t durable-agent-sandbox:latest sandbox/`

Expected: image builds; final line `Successfully tagged durable-agent-sandbox:latest`.

- [ ] **Step 4: Smoke-test the image**

```bash
docker run --rm durable-agent-sandbox:latest python -c "import talib, pandas, numpy; print('ok', talib.__ta_version__)"
```

Expected: `ok 0.4.0` (or similar version string).

- [ ] **Step 5: Commit**

```bash
git add sandbox/
git commit -m "feat(sandbox): add ta-lib + pandas base image with runner helpers"
```

---

## Task 6: Worker skeleton (hello workflow)

**Files:**
- Create: `backend/worker/__init__.py`, `backend/worker/main.py`
- Create: `backend/worker/workflows/__init__.py`, `backend/worker/workflows/hello.py`

- [ ] **Step 1: Create `backend/worker/__init__.py` and `backend/worker/workflows/__init__.py`** (empty package markers).

- [ ] **Step 2: Create `backend/worker/workflows/hello.py`**

```python
from datetime import timedelta
from temporalio import workflow


@workflow.defn
class HelloWorkflow:
    @workflow.run
    async def run(self, name: str) -> str:
        await workflow.sleep(timedelta(seconds=0))  # exercise replay
        return f"Hello, {name} — from a durable workflow"
```

- [ ] **Step 3: Create `backend/worker/main.py`**

```python
import asyncio
import logging

import structlog
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from shared.settings import settings
from worker.workflows.hello import HelloWorkflow


structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(
    getattr(logging, settings.log_level.upper(), logging.INFO)))
log = structlog.get_logger("worker")


async def main() -> None:
    client = await Client.connect(
        settings.temporal_address,
        namespace=settings.temporal_namespace,
        data_converter=pydantic_data_converter,
    )
    log.info("worker.connected", address=settings.temporal_address,
             namespace=settings.temporal_namespace, task_queue=settings.temporal_task_queue)

    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[HelloWorkflow],
        activities=[],
    )
    log.info("worker.starting")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Commit**

```bash
git add backend/worker
git commit -m "feat(worker): add worker entrypoint with hello workflow"
```

---

## Task 7: FastAPI skeleton + Temporal client + SQLite

**Files:**
- Create: `backend/fastapi_app/__init__.py`, `main.py`, `temporal_client.py`, `db.py`
- Create: `backend/fastapi_app/routes/__init__.py`, `routes/runs.py`

- [ ] **Step 1: Create `backend/fastapi_app/__init__.py`** and `routes/__init__.py` (empty).

- [ ] **Step 2: Create `backend/fastapi_app/temporal_client.py`**

```python
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from shared.settings import settings

_client: Client | None = None


async def get_temporal_client() -> Client:
    global _client
    if _client is None:
        _client = await Client.connect(
            settings.temporal_address,
            namespace=settings.temporal_namespace,
            data_converter=pydantic_data_converter,
        )
    return _client
```

- [ ] **Step 3: Create `backend/fastapi_app/db.py`**

```python
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).parent / "db.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  workflow_id TEXT PRIMARY KEY,
  ticker      TEXT NOT NULL,
  started_at  TEXT NOT NULL,
  status      TEXT NOT NULL,
  last_phase  TEXT,
  params_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS idempotency_keys (
  key            TEXT PRIMARY KEY,
  workflow_id    TEXT NOT NULL,
  action         TEXT NOT NULL,
  response_json  TEXT,
  created_at     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chaos_events (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  workflow_id  TEXT NOT NULL,
  kind         TEXT NOT NULL,
  payload_json TEXT,
  ts           TEXT NOT NULL
);
"""


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def insert_run(workflow_id: str, ticker: str, params: dict[str, Any]) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO runs(workflow_id,ticker,started_at,status,last_phase,params_json) VALUES (?,?,?,?,?,?)",
            (workflow_id, ticker, datetime.utcnow().isoformat(), "RUNNING", "SYNTHESIZING", json.dumps(params)),
        )
        conn.commit()
    finally:
        conn.close()


def list_runs(limit: int = 20) -> list[dict[str, Any]]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def log_chaos(workflow_id: str, kind: str, payload: dict[str, Any]) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO chaos_events(workflow_id,kind,payload_json,ts) VALUES (?,?,?,?)",
            (workflow_id, kind, json.dumps(payload), datetime.utcnow().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 4: Create `backend/fastapi_app/routes/runs.py`**

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..temporal_client import get_temporal_client
from ..db import insert_run, list_runs
from worker.workflows.hello import HelloWorkflow
from shared.settings import settings

router = APIRouter(prefix="/api/runs", tags=["runs"])


class HelloRequest(BaseModel):
    name: str


@router.post("/hello")
async def start_hello(req: HelloRequest) -> dict:
    client = await get_temporal_client()
    handle = await client.start_workflow(
        HelloWorkflow.run, req.name,
        id=f"hello-{req.name}",
        task_queue=settings.temporal_task_queue,
    )
    insert_run(handle.id, ticker="-", params={"name": req.name})
    result = await handle.result()
    return {"workflow_id": handle.id, "result": result}


@router.get("/")
async def runs() -> list[dict]:
    return list_runs()
```

- [ ] **Step 5: Create `backend/fastapi_app/main.py`**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routes.runs import router as runs_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Durable Agentic Harness API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(runs_router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True}
```

- [ ] **Step 6: Commit**

```bash
git add backend/fastapi_app
git commit -m "feat(fastapi): add app skeleton, temporal client, sqlite, hello run route"
```

---

## Task 8: docker-compose.yml

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Create `docker-compose.yml`**

```yaml
# Temporal server is NOT bundled here — the user runs `temporal server start-dev` on the host.
# Containers reach it via host.docker.internal:7233 (Docker Desktop on macOS/Windows).
services:
  mockoon:
    image: mockoon/cli:latest
    command: ["--data", "/data/demo.json", "--port", "3001"]
    volumes:
      - ./mockoon:/data:ro
    ports: ["3001:3001"]
    networks: [demo_net]

  fastapi:
    build:
      context: ./backend
      dockerfile: Dockerfile.fastapi
    env_file: .env
    environment:
      - TEMPORAL_ADDRESS=host.docker.internal:7233
      - MOCKOON_BASE_URL=http://mockoon:3001
    extra_hosts:
      - "host.docker.internal:host-gateway"
    ports: ["8000:8000"]
    depends_on: [mockoon]
    volumes:
      - fastapi-data:/app/fastapi_app
      - /var/run/docker.sock:/var/run/docker.sock
    networks: [demo_net]

  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile.worker
    env_file: .env
    environment:
      - TEMPORAL_ADDRESS=host.docker.internal:7233
      - MOCKOON_BASE_URL=http://mockoon:3001
      - FASTAPI_INTERNAL_URL=http://fastapi:8000
    extra_hosts:
      - "host.docker.internal:host-gateway"
    depends_on: [mockoon, fastapi]
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - sandbox-data:/data
    networks: [demo_net]

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports: ["5173:5173"]
    depends_on: [fastapi]
    networks: [demo_net]

networks:
  demo_net:
    driver: bridge

volumes:
  fastapi-data:
  sandbox-data:
```

- [ ] **Step 2: Verify compose syntax**

Run: `docker compose config > /dev/null && echo "ok"`

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat(infra): add docker-compose with temporal, mockoon, fastapi, worker, frontend"
```

---

## Task 9: Frontend scaffold

**Files:**
- Create: `frontend/package.json`, `vite.config.ts`, `tsconfig.json`, `tailwind.config.ts`, `postcss.config.js`, `index.html`, `components.json`, `Dockerfile`
- Create: `frontend/src/main.tsx`, `App.tsx`, `index.css`
- Create: `frontend/src/lib/utils.ts`

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "durable-agent-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --host 0.0.0.0",
    "build": "tsc -b && vite build",
    "preview": "vite preview --host 0.0.0.0"
  },
  "dependencies": {
    "@radix-ui/react-dialog": "^1.1.2",
    "@radix-ui/react-slot": "^1.1.0",
    "@radix-ui/react-tabs": "^1.1.1",
    "@radix-ui/react-toast": "^1.2.2",
    "@radix-ui/react-tooltip": "^1.1.3",
    "class-variance-authority": "^0.7.0",
    "clsx": "^2.1.1",
    "framer-motion": "^11.11.0",
    "lucide-react": "^0.451.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "recharts": "^2.13.0",
    "tailwind-merge": "^2.5.4"
  },
  "devDependencies": {
    "@types/react": "^18.3.11",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.2",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.47",
    "tailwindcss": "^3.4.13",
    "tailwindcss-animate": "^1.0.7",
    "typescript": "^5.6.2",
    "vite": "^5.4.8"
  }
}
```

- [ ] **Step 2: Create `frontend/vite.config.ts`**

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  server: {
    port: 5173,
    host: "0.0.0.0",
    proxy: { "/api": "http://fastapi:8000" },
  },
});
```

- [ ] **Step 3: Create `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "skipLibCheck": true,
    "strict": true,
    "noUnusedLocals": false,
    "noUnusedParameters": false,
    "noFallthroughCasesInSwitch": true,
    "esModuleInterop": true,
    "jsx": "react-jsx",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "allowImportingTsExtensions": false,
    "baseUrl": ".",
    "paths": { "@/*": ["src/*"] }
  },
  "include": ["src"]
}
```

- [ ] **Step 4: Create `frontend/tailwind.config.ts`**

```ts
import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "hsl(222 47% 6%)",
        foreground: "hsl(210 40% 96%)",
        muted: "hsl(222 30% 18%)",
        accent: { DEFAULT: "hsl(189 90% 55%)", violet: "hsl(265 90% 65%)" },
        card: "hsl(222 47% 9%)",
        border: "hsl(222 30% 22%)",
      },
      fontFamily: { mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"] },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
export default config;
```

- [ ] **Step 5: Create `frontend/postcss.config.js`**

```js
export default {
  plugins: { tailwindcss: {}, autoprefixer: {} },
};
```

- [ ] **Step 6: Create `frontend/index.html`**

```html
<!doctype html>
<html lang="en" class="dark">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Durable Agentic Harness</title>
  </head>
  <body class="bg-background text-foreground">
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 7: Create `frontend/components.json` (shadcn config)**

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "default",
  "tailwind": {
    "config": "tailwind.config.ts",
    "css": "src/index.css",
    "baseColor": "slate",
    "cssVariables": false
  },
  "aliases": { "components": "@/components", "utils": "@/lib/utils" }
}
```

- [ ] **Step 8: Create `frontend/src/lib/utils.ts`**

```ts
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)); }
```

- [ ] **Step 9: Create `frontend/src/index.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root { color-scheme: dark; }
body { font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
```

- [ ] **Step 10: Create `frontend/src/App.tsx`**

```tsx
import { useEffect, useState } from "react";

export default function App() {
  const [health, setHealth] = useState<string>("checking...");
  useEffect(() => {
    fetch("/api/runs/").then(() => setHealth("ok")).catch(() => setHealth("error"));
  }, []);
  return (
    <div className="min-h-screen p-12">
      <h1 className="text-3xl font-semibold tracking-tight">Durable Agentic Harness</h1>
      <p className="mt-2 text-sm text-foreground/70">API: {health}</p>
    </div>
  );
}
```

- [ ] **Step 11: Create `frontend/src/main.tsx`**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode><App /></React.StrictMode>
);
```

- [ ] **Step 12: Create `frontend/Dockerfile`**

```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev"]
```

- [ ] **Step 13: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): scaffold vite + react + shadcn-ready + tailwind dark theme"
```

---

## Task 10: End-to-end "hello" smoke test

**Files:**
- Create: `backend/tests/__init__.py`, `backend/tests/e2e/__init__.py`, `backend/tests/e2e/test_smoke.py`

- [ ] **Step 1: Create the test file**

```python
import pytest
import httpx


@pytest.mark.e2e
async def test_compose_health() -> None:
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.get("http://localhost:8000/health")
        assert r.status_code == 200
        assert r.json() == {"ok": True}


@pytest.mark.e2e
async def test_hello_workflow_completes() -> None:
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.post("http://localhost:8000/api/runs/hello", json={"name": "Stage"})
        assert r.status_code == 200
        data = r.json()
        assert data["result"].startswith("Hello, Stage")
        assert data["workflow_id"] == "hello-Stage"
```

- [ ] **Step 2: Boot the stack**

```bash
docker compose up --build -d
docker compose logs -f worker  # watch in a side terminal until you see "worker.starting"
```

- [ ] **Step 3: Run the smoke test**

```bash
cd backend && pytest -m e2e -v
```

Expected: both tests pass. The `/api/runs/hello` call returns within a couple seconds.

- [ ] **Step 4: Open Temporal Web UI**

Open http://localhost:8233 in a browser; you should see a `hello-Stage` workflow execution under namespace `default`.

- [ ] **Step 5: Tear down**

```bash
docker compose down
```

- [ ] **Step 6: Commit**

```bash
git add backend/tests
git commit -m "test(e2e): add compose smoke + hello-workflow smoke"
```

**🎉 PHASE A COMPLETE — you have running infra and a durable hello-workflow.**

---

# PHASE B — Phase 1 War Room (Tasks 11–21)

## Task 11: `persist_strategy` and `notify_ui` activities

**Files:**
- Create: `backend/worker/activities/__init__.py`, `backend/worker/activities/persist.py`, `backend/worker/activities/ui.py`

- [ ] **Step 1: Create `backend/worker/activities/__init__.py`** (empty).

- [ ] **Step 2: Create `backend/worker/activities/persist.py`**

```python
import httpx
from temporalio import activity
from temporalio.exceptions import ApplicationError

from shared.models import StrategySpec, OrderResult
from shared.settings import settings


@activity.defn
async def persist_strategy(strategy: StrategySpec) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as c:
        try:
            r = await c.post(f"{settings.mockoon_base_url}/db/strategy", json=strategy.model_dump())
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500:
                raise ApplicationError(f"db/strategy 5xx: {e}", type="ServerError")
            raise ApplicationError(f"db/strategy 4xx: {e}", type="ClientError", non_retryable=True)


@activity.defn
async def write_trade_record(order: OrderResult) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as c:
        try:
            r = await c.post(f"{settings.mockoon_base_url}/db/trades", json=order.model_dump())
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500:
                raise ApplicationError(f"db/trades 5xx: {e}", type="ServerError")
            raise ApplicationError(f"db/trades 4xx: {e}", type="ClientError", non_retryable=True)
```

- [ ] **Step 3: Create `backend/worker/activities/ui.py`**

```python
import httpx
from temporalio import activity
from temporalio.exceptions import ApplicationError

from shared.models import UIEvent
from shared.settings import settings


@activity.defn
async def notify_ui(event: UIEvent) -> dict:
    async with httpx.AsyncClient(timeout=5.0) as c:
        try:
            r = await c.post(
                f"{settings.fastapi_internal_url}/internal/events",
                headers={"X-Internal-Token": settings.fastapi_internal_token},
                json=event.model_dump(mode="json"),
            )
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500:
                raise ApplicationError(f"notify_ui 5xx: {e}", type="ServerError")
            raise ApplicationError(f"notify_ui 4xx: {e}", type="ClientError", non_retryable=True)
        except httpx.RequestError as e:
            raise ApplicationError(f"notify_ui connection: {e}", type="ConnectionError")
```

- [ ] **Step 4: Commit**

```bash
git add backend/worker/activities/
git commit -m "feat(activities): add persist_strategy, write_trade_record, notify_ui"
```

---

## Task 12: `fetch_historical_data` activity

**Files:**
- Create: `backend/worker/activities/market.py`

- [ ] **Step 1: Create `backend/worker/activities/market.py`**

```python
from pathlib import Path
import json

import httpx
import pandas as pd
from temporalio import activity
from temporalio.exceptions import ApplicationError

from shared.models import HistoricalDataRef
from shared.settings import settings


SHARED_DATA_DIR = Path("/data")


@activity.defn
async def fetch_historical_data(ticker: str, range_: str) -> HistoricalDataRef:
    """Fetch historical OHLCV and persist to shared volume. Returns a ref the sandbox can read."""
    SHARED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SHARED_DATA_DIR / f"{ticker}-{range_}.parquet"

    if settings.data_mode == "live":
        try:
            import yfinance as yf
            data = yf.download(ticker, period=range_, progress=False)
            if data is None or data.empty:
                raise ApplicationError(f"yahoo returned empty for {ticker}", type="DataError",
                                       non_retryable=True)
            df = data.reset_index().rename(columns={
                "Date": "t", "Open": "o", "High": "h", "Low": "l",
                "Close": "c", "Volume": "v",
            })
            df["t"] = df["t"].astype("int64") // 10**9  # epoch seconds
        except Exception as e:
            raise ApplicationError(f"yfinance failed: {e}", type="ServerError")
    else:
        async with httpx.AsyncClient(timeout=30.0) as c:
            r = await c.get(f"{settings.mockoon_base_url}/market/prices",
                            params={"ticker": ticker, "range": range_})
            r.raise_for_status()
            payload = r.json()
            df = pd.DataFrame(payload["ohlcv"])

    df.to_parquet(out_path, index=False)
    return HistoricalDataRef(path=str(out_path), rows=len(df), ticker=ticker, range=range_)
```

- [ ] **Step 2: Commit**

```bash
git add backend/worker/activities/market.py
git commit -m "feat(activities): add fetch_historical_data (yfinance + mockoon switch)"
```

---

## Task 13: `run_backtest_in_sandbox` activity

**Files:**
- Create: `backend/worker/activities/backtest.py`

- [ ] **Step 1: Create `backend/worker/activities/backtest.py`**

> **Implementation note:** the OpenAI Agents SDK sandbox API may not be fully published by build time. This task uses a direct `docker` SDK approach that achieves the same semantics (LLM writes Python → run in sandboxed container → parse scorecard). The OpenAI Agents SDK can be layered on top later by swapping the `_run_code_in_container` helper.

```python
import asyncio
import json
import re
import textwrap
from pathlib import Path

import docker
from temporalio import activity
from temporalio.exceptions import ApplicationError

from shared.models import BacktestInput, Scorecard
from shared.openai_client import make_openai_client
from shared.prompts import BACKTEST_PROMPT
from shared.settings import settings


@activity.defn
async def run_backtest_in_sandbox(inp: BacktestInput) -> Scorecard:
    activity.heartbeat({"strategy_id": inp.strategy_spec.id, "stage": "writing_code"})

    code = await _generate_backtest_code(inp)
    activity.heartbeat({"strategy_id": inp.strategy_spec.id, "stage": "executing"})

    try:
        stdout = await asyncio.get_event_loop().run_in_executor(
            None, _run_code_in_container, code, inp.historical_data_ref.path
        )
    except Exception as e:
        raise ApplicationError(f"sandbox execution failed: {e}", type="SandboxError")

    scorecard = _parse_scorecard(stdout, inp.strategy_spec.id, code)
    return scorecard


async def _generate_backtest_code(inp: BacktestInput) -> str:
    client = make_openai_client()
    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": BACKTEST_PROMPT},
            {"role": "user", "content": inp.strategy_spec.to_prompt()},
        ],
        temperature=0.3,
    )
    raw = response.choices[0].message.content or ""
    code = _extract_python_block(raw)
    if not code:
        raise ApplicationError("LLM did not produce a python code block",
                               type="LLMOutputError", non_retryable=True)
    return code


def _extract_python_block(text: str) -> str:
    m = re.search(r"```(?:python)?\n(.*?)```", text, re.DOTALL)
    return m.group(1).strip() if m else text.strip()


def _run_code_in_container(code: str, data_host_path: str) -> str:
    client = docker.from_env()
    # The same shared volume the worker writes to is bind-mounted into the sandbox.
    container = client.containers.run(
        image=settings.sandbox_image,
        command=["python", "-c", code],
        volumes={"sandbox-data": {"bind": "/data", "mode": "ro"}},
        network_disabled=settings.sandbox_network_disabled,
        mem_limit="512m",
        nano_cpus=500_000_000,  # 0.5 CPU
        detach=True,
        remove=False,
    )
    try:
        result = container.wait(timeout=90)
        logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
        if result.get("StatusCode", 1) != 0:
            raise RuntimeError(f"sandbox exited non-zero: {result}\n{logs[-2000:]}")
        return logs
    finally:
        try:
            container.remove(force=True)
        except Exception:
            pass


def _parse_scorecard(stdout: str, strategy_id: str, generated_code: str) -> Scorecard:
    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            data = json.loads(line)
            return Scorecard(
                strategy_id=str(data.get("strategy_id") or strategy_id),
                roi=float(data.get("roi", 0)),
                sharpe=float(data.get("sharpe", 0)),
                max_drawdown=float(data.get("max_drawdown", 0)),
                win_rate=float(data.get("win_rate", 0)),
                num_trades=int(data.get("num_trades", 0)),
                generated_code=generated_code,
            )
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
    return Scorecard(strategy_id=strategy_id, generated_code=generated_code,
                     error="no parseable scorecard in stdout")
```

- [ ] **Step 2: Commit**

```bash
git add backend/worker/activities/backtest.py
git commit -m "feat(activities): add run_backtest_in_sandbox via docker SDK + OpenAI"
```

---

## Task 14: `BacktestSandboxWorkflow` (child workflow)

**Files:**
- Create: `backend/worker/workflows/backtest.py`
- Modify: `backend/worker/main.py`

- [ ] **Step 1: Create `backend/worker/workflows/backtest.py`**

```python
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from shared.models import BacktestInput, Scorecard
    from worker.activities.backtest import run_backtest_in_sandbox


@workflow.defn
class BacktestSandboxWorkflow:
    @workflow.run
    async def run(self, inp: BacktestInput) -> Scorecard:
        try:
            return await workflow.execute_activity(
                run_backtest_in_sandbox,
                inp,
                start_to_close_timeout=timedelta(seconds=180),
                retry_policy=RetryPolicy(maximum_attempts=2),
                heartbeat_timeout=timedelta(seconds=30),
            )
        except Exception as e:
            return Scorecard(strategy_id=inp.strategy_spec.id, error=str(e)[:300])
```

- [ ] **Step 2: Modify `backend/worker/main.py` to register the new workflow + activity**

Replace the workflows/activities lists:

```python
from worker.workflows.hello import HelloWorkflow
from worker.workflows.backtest import BacktestSandboxWorkflow
from worker.activities.backtest import run_backtest_in_sandbox
from worker.activities.persist import persist_strategy, write_trade_record
from worker.activities.ui import notify_ui
from worker.activities.market import fetch_historical_data

# ...
worker = Worker(
    client,
    task_queue=settings.temporal_task_queue,
    workflows=[HelloWorkflow, BacktestSandboxWorkflow],
    activities=[
        run_backtest_in_sandbox, persist_strategy, write_trade_record,
        notify_ui, fetch_historical_data,
    ],
)
```

- [ ] **Step 3: Commit**

```bash
git add backend/worker/workflows/backtest.py backend/worker/main.py
git commit -m "feat(workflows): add BacktestSandboxWorkflow + register activities"
```

---

## Task 15: `select_winner` + `SelfEvolvingStockAgentWorkflow` (Phase 1 only)

**Files:**
- Create: `backend/shared/selection.py`
- Create: `backend/worker/workflows/parent.py`
- Modify: `backend/worker/main.py`
- Create: `backend/tests/unit/__init__.py`, `backend/tests/unit/test_select_winner.py`

- [ ] **Step 1: Create `backend/tests/unit/test_select_winner.py` (TDD — write test first)**

```python
from shared.selection import select_winner
from shared.models import Scorecard


def test_select_winner_picks_highest_sharpe():
    cards = [
        Scorecard(strategy_id="a", sharpe=1.0, max_drawdown=0.15, roi=0.2),
        Scorecard(strategy_id="b", sharpe=1.5, max_drawdown=0.20, roi=0.18),
        Scorecard(strategy_id="c", sharpe=1.5, max_drawdown=0.10, roi=0.15),
    ]
    winner = select_winner(cards)
    # ties on sharpe broken by lowest drawdown
    assert winner.strategy_id == "c"


def test_select_winner_ignores_errored():
    cards = [
        Scorecard(strategy_id="a", error="boom"),
        Scorecard(strategy_id="b", sharpe=0.5, max_drawdown=0.2),
    ]
    winner = select_winner(cards)
    assert winner.strategy_id == "b"


def test_select_winner_raises_when_all_errored():
    import pytest
    cards = [Scorecard(strategy_id="a", error="boom"), Scorecard(strategy_id="b", error="boom2")]
    with pytest.raises(ValueError, match="no successful backtests"):
        select_winner(cards)
```

- [ ] **Step 2: Run test — expect failure**

```bash
cd backend && pytest tests/unit/test_select_winner.py -v
```

Expected: ImportError for `shared.selection`.

- [ ] **Step 3: Create `backend/shared/selection.py`**

```python
from .models import Scorecard


def select_winner(scorecards: list[Scorecard]) -> Scorecard:
    """Pick highest Sharpe; tiebreak by lowest max_drawdown."""
    valid = [s for s in scorecards if s.error is None]
    if not valid:
        raise ValueError("no successful backtests to choose from")
    valid.sort(key=lambda s: (-s.sharpe, s.max_drawdown))
    return valid[0]
```

- [ ] **Step 4: Run test — expect pass**

```bash
cd backend && pytest tests/unit/test_select_winner.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Create `backend/worker/workflows/parent.py` (Phase 1 only for now)**

```python
import asyncio
from datetime import datetime, timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from shared.constants import Phase
    from shared.models import (
        AgentInput, BacktestInput, Scorecard, StrategySpec, UIEvent,
    )
    from shared.selection import select_winner
    from worker.workflows.backtest import BacktestSandboxWorkflow
    from worker.activities.market import fetch_historical_data
    from worker.activities.persist import persist_strategy
    from worker.activities.ui import notify_ui


@workflow.defn
class SelfEvolvingStockAgentWorkflow:
    def __init__(self) -> None:
        self.phase: Phase = Phase.SYNTHESIZING
        self.winning_strategy: Optional[StrategySpec] = None
        self.scorecards: list[Scorecard] = []

    @workflow.run
    async def run(self, inp: AgentInput) -> dict:
        wf_id = workflow.info().workflow_id

        # ───── PHASE 1: SYNTHESIZING ─────
        self.phase = Phase.SYNTHESIZING
        await _emit(wf_id, "phase_change", {"phase": self.phase.value})

        data_ref = await workflow.execute_activity(
            fetch_historical_data, args=[inp.ticker, inp.history_range],
            start_to_close_timeout=timedelta(seconds=120),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        await _emit(wf_id, "backtest_progress",
                    {"status": "starting_fanout", "n": len(inp.candidate_strategies)})

        child_handles = await asyncio.gather(*[
            workflow.start_child_workflow(
                BacktestSandboxWorkflow.run,
                BacktestInput(strategy_spec=s, historical_data_ref=data_ref,
                              sandbox_image=inp.candidate_strategies[0].id and "durable-agent-sandbox:latest"),
                id=f"{wf_id}-bt-{s.id}",
            )
            for s in inp.candidate_strategies
        ])

        for h, spec in zip(child_handles, inp.candidate_strategies):
            await _emit(wf_id, "backtest_progress",
                        {"status": "running", "strategy_id": spec.id})

        results = await asyncio.gather(*child_handles, return_exceptions=True)
        self.scorecards = [r for r in results if isinstance(r, Scorecard)]

        for sc in self.scorecards:
            await _emit(wf_id, "backtest_progress",
                        {"status": "done", "strategy_id": sc.strategy_id,
                         "sharpe": sc.sharpe, "roi": sc.roi, "max_drawdown": sc.max_drawdown,
                         "error": sc.error, "generated_code": sc.generated_code})

        winner = select_winner(self.scorecards)
        # Find matching original spec by id (preserve params)
        winner_spec = next(s for s in inp.candidate_strategies if s.id == winner.strategy_id)
        self.winning_strategy = winner_spec

        await workflow.execute_activity(
            persist_strategy, winner_spec,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=5),
        )
        await _emit(wf_id, "phase_change",
                    {"phase": "WINNER_SELECTED",
                     "winning_strategy": winner_spec.model_dump(),
                     "winning_scorecard": winner.model_dump()})

        return {"winner": winner.model_dump(), "spec": winner_spec.model_dump()}

    @workflow.query
    def get_state(self) -> dict:
        return {
            "phase": self.phase.value,
            "winning_strategy": self.winning_strategy.model_dump() if self.winning_strategy else None,
            "scorecards": [s.model_dump() for s in self.scorecards],
        }


async def _emit(workflow_id: str, kind: str, payload: dict) -> None:
    """Helper: send a UIEvent via the notify_ui activity."""
    event = UIEvent(ts=datetime.utcnow(), workflow_id=workflow_id, kind=kind, payload=payload)
    await workflow.execute_activity(
        notify_ui, event,
        start_to_close_timeout=timedelta(seconds=5),
        retry_policy=RetryPolicy(maximum_attempts=5),
    )
```

- [ ] **Step 6: Modify `backend/worker/main.py` to register the parent**

Add to imports and the workflows list:

```python
from worker.workflows.parent import SelfEvolvingStockAgentWorkflow
# ...
workflows=[HelloWorkflow, BacktestSandboxWorkflow, SelfEvolvingStockAgentWorkflow],
```

- [ ] **Step 7: Commit**

```bash
git add backend/shared/selection.py backend/worker/workflows/parent.py backend/worker/main.py backend/tests/unit/
git commit -m "feat(workflows): add SelfEvolvingStockAgentWorkflow Phase 1 + select_winner"
```

---

## Task 16: FastAPI `/api/runs` start + list endpoints

**Files:**
- Modify: `backend/fastapi_app/routes/runs.py`

- [ ] **Step 1: Replace `backend/fastapi_app/routes/runs.py`**

```python
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from shared.models import AgentInput
from shared.strategies import default_candidate_strategies
from shared.settings import settings
from worker.workflows.hello import HelloWorkflow
from worker.workflows.parent import SelfEvolvingStockAgentWorkflow

from ..temporal_client import get_temporal_client
from ..db import insert_run, list_runs

router = APIRouter(prefix="/api/runs", tags=["runs"])


class HelloRequest(BaseModel):
    name: str


class StartRunRequest(BaseModel):
    ticker: str
    objective: str = "maximize Sharpe; max drawdown < 10%"
    history_range: str = "3y"
    num_sandboxes: int | None = None
    tick_seconds: int | None = None


@router.post("/hello")
async def start_hello(req: HelloRequest) -> dict:
    client = await get_temporal_client()
    handle = await client.start_workflow(
        HelloWorkflow.run, req.name, id=f"hello-{req.name}",
        task_queue=settings.temporal_task_queue,
    )
    insert_run(handle.id, ticker="-", params={"name": req.name})
    return {"workflow_id": handle.id, "result": await handle.result()}


@router.post("/")
async def start_run(req: StartRunRequest) -> dict:
    n = req.num_sandboxes or settings.num_sandboxes
    inp = AgentInput(
        ticker=req.ticker.upper(),
        objective=req.objective,
        history_range=req.history_range,
        num_sandboxes=n,
        candidate_strategies=default_candidate_strategies(n),
        approval_threshold=settings.approval_threshold_usd,
        tick_seconds=req.tick_seconds or settings.tick_seconds,
        drift_threshold=settings.drift_threshold,
    )
    workflow_id = f"agent-{req.ticker.upper()}-{uuid.uuid4().hex[:8]}"
    client = await get_temporal_client()
    await client.start_workflow(
        SelfEvolvingStockAgentWorkflow.run, inp,
        id=workflow_id, task_queue=settings.temporal_task_queue,
    )
    insert_run(workflow_id, ticker=req.ticker.upper(), params=inp.model_dump())
    return {"workflow_id": workflow_id, "ticker": req.ticker.upper()}


@router.get("/")
async def runs() -> list[dict]:
    return list_runs()


@router.get("/{workflow_id}/state")
async def run_state(workflow_id: str) -> dict:
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)
    try:
        state = await handle.query("get_state")
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    return state
```

- [ ] **Step 2: Commit**

```bash
git add backend/fastapi_app/routes/runs.py
git commit -m "feat(fastapi): add POST /api/runs to start agent workflow"
```

---

## Task 17: FastAPI SSE event bus

**Files:**
- Create: `backend/fastapi_app/events.py`
- Create: `backend/fastapi_app/routes/events.py`, `backend/fastapi_app/routes/internal.py`
- Modify: `backend/fastapi_app/main.py`

- [ ] **Step 1: Create `backend/fastapi_app/events.py`**

```python
import asyncio
from collections import defaultdict
from typing import AsyncIterator


class EventBus:
    """In-process pub/sub: workflow_id -> set of asyncio.Queues."""

    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = defaultdict(set)

    async def publish(self, workflow_id: str, event: dict) -> None:
        for q in list(self._subs.get(workflow_id, ())):
            await q.put(event)

    async def subscribe(self, workflow_id: str) -> AsyncIterator[dict]:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subs[workflow_id].add(q)
        try:
            while True:
                event = await q.get()
                yield event
        finally:
            self._subs[workflow_id].discard(q)


bus = EventBus()
```

- [ ] **Step 2: Create `backend/fastapi_app/routes/internal.py`**

```python
from fastapi import APIRouter, Header, HTTPException

from shared.models import UIEvent
from shared.settings import settings
from ..events import bus

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/events")
async def post_event(event: UIEvent, x_internal_token: str = Header(default="")) -> dict:
    if x_internal_token != settings.fastapi_internal_token:
        raise HTTPException(status_code=401, detail="unauthorized")
    await bus.publish(event.workflow_id, event.model_dump(mode="json"))
    return {"ok": True}
```

- [ ] **Step 3: Create `backend/fastapi_app/routes/events.py`**

```python
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from ..events import bus

router = APIRouter(prefix="/api/runs", tags=["events"])


@router.get("/{workflow_id}/events")
async def stream(workflow_id: str) -> EventSourceResponse:
    async def event_gen():
        async for event in bus.subscribe(workflow_id):
            yield {"event": event["kind"], "data": event}
    return EventSourceResponse(event_gen())
```

- [ ] **Step 4: Modify `backend/fastapi_app/main.py` to register both routers**

```python
from .routes.events import router as events_router
from .routes.internal import router as internal_router
# ...
app.include_router(runs_router)
app.include_router(events_router)
app.include_router(internal_router)
```

- [ ] **Step 5: Commit**

```bash
git add backend/fastapi_app/events.py backend/fastapi_app/routes/events.py backend/fastapi_app/routes/internal.py backend/fastapi_app/main.py
git commit -m "feat(fastapi): add in-process event bus + SSE + internal events endpoint"
```

---

## Task 18: Frontend types, API client, SSE hook

**Files:**
- Create: `frontend/src/types.ts`, `frontend/src/lib/api.ts`, `frontend/src/hooks/useSSE.ts`, `frontend/src/hooks/useWorkflow.ts`

- [ ] **Step 1: Create `frontend/src/types.ts`**

```ts
export type Phase = "SYNTHESIZING" | "WATCHING" | "AWAITING_APPROVAL" | "EVOLVING";

export type StrategySpec = {
  id: string;
  family: "RSI" | "MACD" | "EMA_CROSS" | "BOLLINGER" | "MEAN_REVERSION";
  params: Record<string, number>;
};

export type Scorecard = {
  strategy_id: string;
  roi: number;
  sharpe: number;
  max_drawdown: number;
  win_rate: number;
  num_trades: number;
  generated_code: string;
  error?: string | null;
};

export type UIEvent = {
  ts: string;
  workflow_id: string;
  kind: string;
  payload: Record<string, unknown>;
};

export type RunState = {
  phase: Phase | "WINNER_SELECTED";
  winning_strategy: StrategySpec | null;
  scorecards: Scorecard[];
};
```

- [ ] **Step 2: Create `frontend/src/lib/api.ts`**

```ts
const API = ""; // proxied by Vite

export async function startRun(payload: { ticker: string; num_sandboxes?: number }) {
  const r = await fetch(`${API}/api/runs/`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error(await r.text());
  return (await r.json()) as { workflow_id: string; ticker: string };
}

export async function getState(workflowId: string) {
  const r = await fetch(`${API}/api/runs/${workflowId}/state`);
  if (!r.ok) throw new Error(await r.text());
  return await r.json();
}
```

- [ ] **Step 3: Create `frontend/src/hooks/useSSE.ts`**

```ts
import { useEffect, useState } from "react";
import type { UIEvent } from "../types";

export function useSSE(workflowId: string | null) {
  const [events, setEvents] = useState<UIEvent[]>([]);
  useEffect(() => {
    if (!workflowId) return;
    const es = new EventSource(`/api/runs/${workflowId}/events`);
    es.onmessage = (m) => {
      try {
        const data = JSON.parse(m.data) as UIEvent;
        setEvents((prev) => [...prev, data]);
      } catch {}
    };
    // sse_starlette emits typed events; capture all via custom listener:
    const handler = (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as UIEvent;
        setEvents((prev) => [...prev, data]);
      } catch {}
    };
    ["phase_change", "backtest_progress", "trade_intent", "risk_decision",
     "approval_request", "order_placed", "drift_detected", "audit", "chaos"]
      .forEach((k) => es.addEventListener(k, handler));
    return () => es.close();
  }, [workflowId]);
  return events;
}
```

- [ ] **Step 4: Create `frontend/src/hooks/useWorkflow.ts`**

```ts
import { useMemo } from "react";
import type { UIEvent, Scorecard, StrategySpec } from "../types";

export function useWorkflow(events: UIEvent[]) {
  return useMemo(() => {
    let phase = "SYNTHESIZING" as string;
    const scorecards: Record<string, Scorecard> = {};
    let winningStrategy: StrategySpec | null = null;
    let winningScorecard: Scorecard | null = null;

    for (const e of events) {
      if (e.kind === "phase_change") phase = (e.payload.phase as string) ?? phase;
      if (e.kind === "phase_change" && e.payload.winning_strategy)
        winningStrategy = e.payload.winning_strategy as StrategySpec;
      if (e.kind === "phase_change" && e.payload.winning_scorecard)
        winningScorecard = e.payload.winning_scorecard as Scorecard;
      if (e.kind === "backtest_progress" && e.payload.status === "done") {
        const sid = e.payload.strategy_id as string;
        scorecards[sid] = {
          strategy_id: sid,
          roi: (e.payload.roi as number) ?? 0,
          sharpe: (e.payload.sharpe as number) ?? 0,
          max_drawdown: (e.payload.max_drawdown as number) ?? 0,
          win_rate: 0,
          num_trades: 0,
          generated_code: (e.payload.generated_code as string) ?? "",
          error: (e.payload.error as string) ?? null,
        };
      }
    }

    return { phase, scorecards, winningStrategy, winningScorecard };
  }, [events]);
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types.ts frontend/src/lib/api.ts frontend/src/hooks/
git commit -m "feat(frontend): add types, api client, SSE + workflow state hooks"
```

---

## Task 19: Frontend Mission Control + Event Log

**Files:**
- Create: `frontend/src/components/MissionControl.tsx`, `frontend/src/components/EventLog.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create `frontend/src/components/EventLog.tsx`**

```tsx
import type { UIEvent } from "../types";

const KIND_COLORS: Record<string, string> = {
  phase_change: "text-cyan-300",
  backtest_progress: "text-violet-300",
  trade_intent: "text-amber-300",
  risk_decision: "text-orange-300",
  approval_request: "text-yellow-300",
  order_placed: "text-emerald-300",
  drift_detected: "text-rose-300",
  chaos: "text-pink-400",
  audit: "text-foreground/60",
};

export function EventLog({ events }: { events: UIEvent[] }) {
  return (
    <div className="font-mono text-xs h-72 overflow-auto rounded border border-border bg-card p-3">
      {events.length === 0 && <div className="text-foreground/40">awaiting events…</div>}
      {events.map((e, i) => (
        <div key={i} className="flex gap-2">
          <span className="text-foreground/40">{new Date(e.ts).toLocaleTimeString()}</span>
          <span className={KIND_COLORS[e.kind] ?? "text-foreground/80"}>{e.kind}</span>
          <span className="text-foreground/70 truncate">{JSON.stringify(e.payload)}</span>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Create `frontend/src/components/MissionControl.tsx`**

```tsx
import { useState } from "react";
import { startRun } from "../lib/api";

const PHASES = ["SYNTHESIZING", "WINNER_SELECTED", "WATCHING", "AWAITING_APPROVAL", "EVOLVING"];

export function MissionControl({
  workflowId, onStart, currentPhase,
}: {
  workflowId: string | null;
  currentPhase: string;
  onStart: (wfId: string) => void;
}) {
  const [ticker, setTicker] = useState("NVDA");
  const [busy, setBusy] = useState(false);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <input
          className="bg-card border border-border rounded px-3 py-2 font-mono uppercase w-32"
          value={ticker} onChange={(e) => setTicker(e.target.value.toUpperCase())}
        />
        <button
          disabled={busy || !!workflowId}
          onClick={async () => {
            setBusy(true);
            try {
              const r = await startRun({ ticker });
              onStart(r.workflow_id);
            } finally { setBusy(false); }
          }}
          className="bg-accent text-background font-medium rounded px-4 py-2 hover:opacity-90 disabled:opacity-40"
        >
          Start Self-Evolving Agent
        </button>
        {workflowId && (
          <a href={`http://localhost:8233/namespaces/default/workflows/${workflowId}`}
             target="_blank" rel="noreferrer"
             className="text-xs underline text-accent-violet">View in Temporal UI</a>
        )}
      </div>

      <div className="flex gap-3">
        {PHASES.map((p) => (
          <div key={p}
               className={"px-3 py-1 rounded border text-xs font-mono " +
                          (p === currentPhase ? "bg-accent text-background border-accent" : "border-border text-foreground/60")}>
            {p}
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Replace `frontend/src/App.tsx`**

```tsx
import { useState } from "react";
import { MissionControl } from "./components/MissionControl";
import { EventLog } from "./components/EventLog";
import { useSSE } from "./hooks/useSSE";
import { useWorkflow } from "./hooks/useWorkflow";

export default function App() {
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const events = useSSE(workflowId);
  const { phase } = useWorkflow(events);

  return (
    <div className="min-h-screen p-10 max-w-6xl mx-auto space-y-8">
      <header className="flex items-baseline justify-between">
        <h1 className="text-3xl font-semibold tracking-tight">
          <span className="text-accent">Durable</span> Agentic Harness
        </h1>
        <span className="text-xs font-mono text-foreground/50">{workflowId ?? "no active run"}</span>
      </header>
      <MissionControl workflowId={workflowId} onStart={setWorkflowId} currentPhase={phase} />
      <EventLog events={events} />
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ frontend/src/App.tsx
git commit -m "feat(frontend): add Mission Control + Event Log driven by SSE"
```

---

## Task 20: Frontend War Room component

**Files:**
- Create: `frontend/src/components/WarRoom.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create `frontend/src/components/WarRoom.tsx`**

```tsx
import { useState } from "react";
import type { Scorecard, StrategySpec } from "../types";

type Props = {
  scorecards: Record<string, Scorecard>;
  winningStrategy: StrategySpec | null;
  expected: number;
};

export function WarRoom({ scorecards, winningStrategy, expected }: Props) {
  const cards = Object.values(scorecards);
  const placeholders = Math.max(0, expected - cards.length);
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {cards.map((sc) => (
        <SandboxCard key={sc.strategy_id} sc={sc} winning={sc.strategy_id === winningStrategy?.id} />
      ))}
      {Array.from({ length: placeholders }).map((_, i) => (
        <div key={`p-${i}`}
             className="border border-border rounded p-4 h-40 animate-pulse bg-card/50 text-xs text-foreground/40 font-mono">
          running…
        </div>
      ))}
    </div>
  );
}

function SandboxCard({ sc, winning }: { sc: Scorecard; winning: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={"border rounded p-4 bg-card transition-all " +
                    (winning ? "border-accent shadow-[0_0_30px_-5px_hsl(189_90%_55%/0.6)]" : "border-border")}>
      <div className="flex items-baseline justify-between">
        <div className="font-mono text-xs">{sc.strategy_id}</div>
        {winning && <span className="text-[10px] font-bold text-accent uppercase">WINNER</span>}
      </div>
      {sc.error ? (
        <div className="mt-3 text-rose-300 text-xs font-mono">error: {sc.error}</div>
      ) : (
        <div className="mt-3 grid grid-cols-3 gap-2 text-xs font-mono">
          <Metric label="Sharpe" value={sc.sharpe.toFixed(2)} />
          <Metric label="ROI" value={(sc.roi * 100).toFixed(1) + "%"} />
          <Metric label="DD" value={(sc.max_drawdown * 100).toFixed(1) + "%"} />
        </div>
      )}
      <button onClick={() => setOpen((o) => !o)}
              className="mt-3 text-[10px] underline text-accent-violet">
        {open ? "hide" : "show"} generated code
      </button>
      {open && (
        <pre className="mt-2 max-h-40 overflow-auto text-[10px] bg-background/60 p-2 rounded">
{sc.generated_code || "(no code)"}
        </pre>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-foreground/40 text-[10px] uppercase">{label}</div>
      <div className="text-foreground">{value}</div>
    </div>
  );
}
```

- [ ] **Step 2: Update `frontend/src/App.tsx` to mount WarRoom**

```tsx
import { useState } from "react";
import { MissionControl } from "./components/MissionControl";
import { EventLog } from "./components/EventLog";
import { WarRoom } from "./components/WarRoom";
import { useSSE } from "./hooks/useSSE";
import { useWorkflow } from "./hooks/useWorkflow";

export default function App() {
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [expected, setExpected] = useState(8);
  const events = useSSE(workflowId);
  const { phase, scorecards, winningStrategy } = useWorkflow(events);

  return (
    <div className="min-h-screen p-10 max-w-6xl mx-auto space-y-8">
      <header className="flex items-baseline justify-between">
        <h1 className="text-3xl font-semibold tracking-tight">
          <span className="text-accent">Durable</span> Agentic Harness
        </h1>
        <span className="text-xs font-mono text-foreground/50">{workflowId ?? "no active run"}</span>
      </header>
      <MissionControl workflowId={workflowId} onStart={setWorkflowId} currentPhase={phase} />
      <section>
        <h2 className="text-sm uppercase tracking-widest text-foreground/60 mb-3">War Room</h2>
        <WarRoom scorecards={scorecards} winningStrategy={winningStrategy} expected={expected} />
      </section>
      <EventLog events={events} />
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/WarRoom.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add War Room grid of sandbox cards with winner glow"
```

---

## Task 21: Manual verification of Phase 1

- [ ] **Step 1: Boot the stack**

```bash
docker compose down -v && docker compose build && docker compose up -d
```

- [ ] **Step 2: Open the UI**

http://localhost:5173 — enter `NVDA`, click "Start Self-Evolving Agent".

- [ ] **Step 3: Watch the demo**

Within ~90 seconds you should see:
- Phase badge cycles SYNTHESIZING → WINNER_SELECTED
- 8 sandbox cards populate with Sharpe/ROI/DD
- One card glows with WINNER ribbon
- Event log streams `backtest_progress` and `phase_change` events

- [ ] **Step 4: Verify in Temporal Web UI**

http://localhost:8233 — open the `agent-NVDA-*` workflow. Confirm child `BacktestSandboxWorkflow` executions are visible.

- [ ] **Step 5: Reset for next phase**

```bash
docker compose down
```

- [ ] **Step 6: Tag milestone**

```bash
git tag phase-b-complete
git commit --allow-empty -m "milestone: Phase B (War Room) complete"
```

**🎉 PHASE B COMPLETE — fan-out backtests + winner selection demoable in UI.**

---

# PHASE C — Phase 2+3 Trading Floor (Tasks 22–30)

## Task 22: Market + News snapshot activities

**Files:**
- Modify: `backend/worker/activities/market.py` (add `fetch_market_snapshot`)
- Create: `backend/worker/activities/news.py`

- [ ] **Step 1: Append to `backend/worker/activities/market.py`**

```python
from shared.models import MarketSnapshot


@activity.defn
async def fetch_market_snapshot(ticker: str) -> MarketSnapshot:
    if settings.data_mode == "live":
        try:
            import yfinance as yf
            t = yf.Ticker(ticker)
            hist = t.history(period="60d")
            close = float(hist["Close"].iloc[-1])
            ema12 = float(hist["Close"].ewm(span=12).mean().iloc[-1])
            ema26 = float(hist["Close"].ewm(span=26).mean().iloc[-1])
            macd = ema12 - ema26
            delta = hist["Close"].diff()
            gain = delta.clip(lower=0).rolling(14).mean().iloc[-1]
            loss = (-delta.clip(upper=0)).rolling(14).mean().iloc[-1]
            rsi = 100.0 - (100.0 / (1.0 + (gain / max(loss, 1e-9)))) if loss else 50.0
            bb_std = hist["Close"].rolling(20).std().iloc[-1]
            bb_upper = ema26 + 2 * bb_std
            bb_lower = ema26 - 2 * bb_std
            import time
            return MarketSnapshot(ticker=ticker, price=close, ts=int(time.time()),
                                  rsi=float(rsi), ema12=ema12, ema26=ema26, macd=macd,
                                  bb_upper=float(bb_upper), bb_lower=float(bb_lower))
        except Exception as e:
            raise ApplicationError(f"yahoo quote failed: {e}", type="ServerError")

    async with httpx.AsyncClient(timeout=10.0) as c:
        q = (await c.get(f"{settings.mockoon_base_url}/market/quote", params={"ticker": ticker})).json()
        ind = (await c.get(f"{settings.mockoon_base_url}/market/indicators", params={"ticker": ticker})).json()
    return MarketSnapshot(
        ticker=ticker, price=float(q["price"]), ts=int(q["ts"]),
        rsi=float(ind["rsi"]), ema12=float(ind["ema12"]), ema26=float(ind["ema26"]),
        macd=float(ind["macd"]), bb_upper=float(ind["bb_upper"]), bb_lower=float(ind["bb_lower"]),
    )
```

- [ ] **Step 2: Create `backend/worker/activities/news.py`**

```python
import httpx
from temporalio import activity
from temporalio.exceptions import ApplicationError

from shared.models import NewsSnapshot, NewsHeadline
from shared.settings import settings


@activity.defn
async def fetch_news_snapshot(ticker: str) -> NewsSnapshot:
    async with httpx.AsyncClient(timeout=10.0) as c:
        try:
            h = (await c.get(f"{settings.mockoon_base_url}/news/headlines",
                             params={"ticker": ticker})).json()
            s = (await c.get(f"{settings.mockoon_base_url}/news/sentiment",
                             params={"ticker": ticker})).json()
        except httpx.HTTPError as e:
            raise ApplicationError(f"news fetch failed: {e}", type="ServerError")
    return NewsSnapshot(
        ticker=ticker,
        headlines=[NewsHeadline(**hh) for hh in h.get("headlines", [])],
        sentiment=float(s["score"]),
        rationale=str(s.get("rationale", "")),
    )
```

- [ ] **Step 3: Commit**

```bash
git add backend/worker/activities/market.py backend/worker/activities/news.py
git commit -m "feat(activities): add fetch_market_snapshot + fetch_news_snapshot"
```

---

## Task 23: `call_agent` activity (OpenAI Agents SDK)

**Files:**
- Create: `backend/worker/activities/llm.py`

- [ ] **Step 1: Create `backend/worker/activities/llm.py`**

```python
import json
import uuid

import openai
from temporalio import activity
from temporalio.exceptions import ApplicationError

from shared.constants import TradeAction
from shared.models import AgentCallInput, TradeIntent
from shared.openai_client import make_openai_client
from shared.prompts import LIVE_AGENT_PROMPT
from shared.settings import settings


@activity.defn
async def call_agent(inp: AgentCallInput) -> TradeIntent:
    client = make_openai_client()
    user_msg = json.dumps({
        "strategy": inp.winning_strategy.model_dump(),
        "market": inp.market.model_dump(),
        "news": inp.news.model_dump(),
        "positions": inp.positions.model_dump(),
    })
    try:
        resp = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": LIVE_AGENT_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
    except openai.AuthenticationError as e:
        raise ApplicationError(f"openai auth: {e}", type="AuthenticationError", non_retryable=True)
    except openai.RateLimitError as e:
        raise ApplicationError(f"openai rate limited: {e}", type="RateLimitError")
    except openai.APIStatusError as e:
        if e.status_code >= 500:
            raise ApplicationError(f"openai 5xx: {e}", type="ServerError")
        raise ApplicationError(f"openai 4xx: {e}", type="ClientError", non_retryable=True)

    raw = resp.choices[0].message.content or "{}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise ApplicationError(f"LLM non-JSON: {raw[:200]}", type="LLMOutputError", non_retryable=True)

    action_raw = str(data.get("action", "HOLD")).upper()
    try:
        action = TradeAction(action_raw)
    except ValueError:
        action = TradeAction.HOLD

    return TradeIntent(
        id=str(data.get("id") or f"t-{uuid.uuid4().hex[:8]}"),
        ticker=str(data.get("ticker", inp.market.ticker)),
        action=action,
        qty=float(data.get("qty", 0)),
        rationale=str(data.get("rationale", "")),
    )
```

- [ ] **Step 2: Commit**

```bash
git add backend/worker/activities/llm.py
git commit -m "feat(activities): add call_agent (OpenAI chat with structured trade intent)"
```

---

## Task 24: `risk_check` activity (TDD)

**Files:**
- Create: `backend/worker/activities/risk.py`
- Create: `backend/tests/unit/test_risk.py`

- [ ] **Step 1: Create `backend/tests/unit/test_risk.py` (TDD — test first)**

```python
import pytest
from shared.constants import RiskDecision, TradeAction
from shared.models import (
    RiskCheckInput, TradeIntent, TradeLimits, NewsSnapshot, NewsHeadline, Positions,
)
from worker.activities.risk import _risk_check_pure


def make_inp(intent, news, *, approval=10_000):
    return RiskCheckInput(
        intent=intent, news=news, positions=Positions(),
        limits=TradeLimits(max_notional_per_trade=50_000),
        approval_threshold=approval,
    )


def test_block_on_restricted_news(sample_intent_buy, sample_news_negative):
    res = _risk_check_pure(make_inp(sample_intent_buy, sample_news_negative))
    assert res.decision == RiskDecision.BLOCK
    assert "restricted" in res.reason.lower() or "sentiment" in res.reason.lower()


def test_block_on_low_sentiment(sample_intent_buy):
    news = NewsSnapshot(ticker="NVDA", headlines=[NewsHeadline(title="ok", published_at=0)],
                        sentiment=-0.7)
    res = _risk_check_pure(make_inp(sample_intent_buy, news))
    assert res.decision == RiskDecision.BLOCK


def test_block_on_notional_cap(sample_news_positive):
    big_intent = TradeIntent(id="t-3", ticker="NVDA", action=TradeAction.BUY,
                             qty=1000, rationale="oversized")
    inp = RiskCheckInput(
        intent=big_intent, news=sample_news_positive, positions=Positions(),
        limits=TradeLimits(max_notional_per_trade=50_000),
        approval_threshold=10_000,
    )
    res = _risk_check_pure(inp)
    assert res.decision == RiskDecision.BLOCK
    assert "notional" in res.reason.lower()


def test_requires_approval_above_threshold(sample_intent_big_buy, sample_news_positive):
    inp = make_inp(sample_intent_big_buy, sample_news_positive, approval=100)
    res = _risk_check_pure(inp)
    assert res.decision == RiskDecision.ALLOW_REQUIRES_APPROVAL


def test_allow_when_small_and_positive(sample_intent_buy, sample_news_positive):
    res = _risk_check_pure(make_inp(sample_intent_buy, sample_news_positive, approval=1_000_000))
    assert res.decision == RiskDecision.ALLOW
```

- [ ] **Step 2: Create `backend/worker/activities/risk.py`**

```python
from temporalio import activity

from shared.constants import RESTRICTED_NEWS_TERMS, RiskDecision, TradeAction
from shared.models import RiskCheckInput, RiskResult


def _risk_check_pure(inp: RiskCheckInput) -> RiskResult:
    if inp.intent.action == TradeAction.HOLD:
        return RiskResult(decision=RiskDecision.ALLOW, reason="HOLD")

    # Restricted news terms
    for h in inp.news.headlines:
        title = h.title.lower()
        for term in RESTRICTED_NEWS_TERMS:
            if term in title:
                return RiskResult(decision=RiskDecision.BLOCK,
                                  reason=f"restricted news term: '{term}'")

    # Sentiment
    if inp.news.sentiment < -0.5:
        return RiskResult(decision=RiskDecision.BLOCK,
                          reason=f"sentiment too negative: {inp.news.sentiment:.2f}")

    # Notional cap
    notional = inp.intent.qty * inp.positions.by_ticker.get(
        inp.intent.ticker, type("p", (), {"avg_price": 150.0})()
    ).avg_price if inp.positions.by_ticker.get(inp.intent.ticker) else inp.intent.qty * 150.0
    if notional > inp.limits.max_notional_per_trade:
        return RiskResult(decision=RiskDecision.BLOCK,
                          reason=f"notional {notional:.0f} exceeds cap {inp.limits.max_notional_per_trade:.0f}")

    if notional > inp.approval_threshold:
        return RiskResult(decision=RiskDecision.ALLOW_REQUIRES_APPROVAL,
                          reason=f"notional {notional:.0f} > approval threshold {inp.approval_threshold:.0f}")

    return RiskResult(decision=RiskDecision.ALLOW, reason="all checks passed")


@activity.defn
async def risk_check(inp: RiskCheckInput) -> RiskResult:
    return _risk_check_pure(inp)
```

- [ ] **Step 3: Run tests — expect pass**

```bash
cd backend && pytest tests/unit/test_risk.py -v
```

Expected: 5 passed.

- [ ] **Step 4: Commit**

```bash
git add backend/worker/activities/risk.py backend/tests/unit/test_risk.py
git commit -m "feat(activities): add risk_check with news + sentiment + notional rules"
```

---

## Task 25: `place_order` activity

**Files:**
- Create: `backend/worker/activities/broker.py`

- [ ] **Step 1: Create `backend/worker/activities/broker.py`**

```python
import httpx
from temporalio import activity
from temporalio.exceptions import ApplicationError

from shared.models import OrderResult, PlaceOrderInput
from shared.settings import settings


@activity.defn
async def place_order(inp: PlaceOrderInput) -> OrderResult:
    payload = {
        "ticker": inp.intent.ticker,
        "side": inp.intent.action.value,
        "qty": inp.intent.qty,
        "orderType": "market",
    }
    async with httpx.AsyncClient(timeout=10.0) as c:
        try:
            r = await c.post(
                f"{settings.mockoon_base_url}/broker/orders",
                headers={"X-Idempotency-Key": inp.idempotency_key},
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500:
                raise ApplicationError(f"broker 5xx: {e}", type="ServerError")
            raise ApplicationError(f"broker 4xx: {e}", type="ClientError", non_retryable=True)
        except httpx.HTTPError as e:
            raise ApplicationError(f"broker conn: {e}", type="ConnectionError")

    return OrderResult(
        order_id=str(data.get("orderId", "")),
        ticker=inp.intent.ticker,
        side=inp.intent.action.value,  # "BUY" or "SELL"
        status=str(data.get("status", "unknown")),
        filled_qty=float(data.get("filledQty", inp.intent.qty)),
        avg_price=float(data.get("avgPrice", 0.0)),
    )
```

- [ ] **Step 2: Commit**

```bash
git add backend/worker/activities/broker.py
git commit -m "feat(activities): add place_order with idempotency header"
```

---

## Task 26: Extend parent workflow with Phase 2+3 loop + signals

**Files:**
- Modify: `backend/worker/workflows/parent.py`
- Modify: `backend/worker/main.py`

- [ ] **Step 1: Replace `backend/worker/workflows/parent.py`**

```python
import asyncio
from datetime import datetime, timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from shared.constants import Phase, RiskDecision, TradeAction
    from shared.models import (
        AgentInput, AgentCallInput, BacktestInput, NewsHeadline, OrderResult,
        PlaceOrderInput, Positions, Position, RiskCheckInput, Scorecard, StrategySpec,
        TradeIntent, UIEvent,
    )
    from shared.selection import select_winner
    from worker.workflows.backtest import BacktestSandboxWorkflow
    from worker.activities.market import fetch_historical_data, fetch_market_snapshot
    from worker.activities.news import fetch_news_snapshot
    from worker.activities.llm import call_agent
    from worker.activities.risk import risk_check
    from worker.activities.broker import place_order
    from worker.activities.persist import persist_strategy, write_trade_record
    from worker.activities.ui import notify_ui


@workflow.defn
class SelfEvolvingStockAgentWorkflow:
    def __init__(self) -> None:
        self.phase: Phase = Phase.SYNTHESIZING
        self.winning_strategy: Optional[StrategySpec] = None
        self.scorecards: list[Scorecard] = []
        self.positions: Positions = Positions()
        self.tick_count: int = 0
        self.live_roi: float = 0.0
        self._approvals: dict[str, bool] = {}
        self._injected_news: list[NewsHeadline] = []
        self._injected_sentiment_override: Optional[float] = None
        self._fast_forward: bool = False
        self._stop: bool = False
        self._force_drift: bool = False

    @workflow.signal
    def approve_trade(self, trade_id: str) -> None:
        self._approvals[trade_id] = True

    @workflow.signal
    def reject_trade(self, trade_id: str, reason: str = "") -> None:
        self._approvals[trade_id] = False

    @workflow.signal
    def fast_forward_tick(self) -> None:
        self._fast_forward = True

    @workflow.signal
    def inject_news(self, headline: str, sentiment: float) -> None:
        self._injected_news.append(NewsHeadline(title=headline, published_at=0))
        self._injected_sentiment_override = sentiment

    @workflow.signal
    def force_drift(self) -> None:
        self._force_drift = True

    @workflow.signal
    def stop(self) -> None:
        self._stop = True

    @workflow.query
    def get_state(self) -> dict:
        return {
            "phase": self.phase.value,
            "winning_strategy": self.winning_strategy.model_dump() if self.winning_strategy else None,
            "scorecards": [s.model_dump() for s in self.scorecards],
            "positions": self.positions.model_dump(),
            "tick_count": self.tick_count,
            "live_roi": self.live_roi,
        }

    @workflow.run
    async def run(self, inp: AgentInput) -> dict:
        wf_id = workflow.info().workflow_id

        while not self._stop:
            # ───── PHASE 1: SYNTHESIZING ─────
            await self._run_phase_1(inp, wf_id)
            if self._stop:
                break
            # ───── PHASE 2 + 3: WATCHING / AWAITING_APPROVAL ─────
            drifted = await self._run_phases_2_and_3(inp, wf_id)
            if not drifted:
                break  # graceful stop
        return {"stopped": True}

    async def _run_phase_1(self, inp: AgentInput, wf_id: str) -> None:
        self.phase = Phase.SYNTHESIZING
        await self._emit(wf_id, "phase_change", {"phase": self.phase.value})

        data_ref = await workflow.execute_activity(
            fetch_historical_data, args=[inp.ticker, inp.history_range],
            start_to_close_timeout=timedelta(seconds=120),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        await self._emit(wf_id, "backtest_progress",
                         {"status": "starting_fanout", "n": len(inp.candidate_strategies)})

        child_handles = await asyncio.gather(*[
            workflow.start_child_workflow(
                BacktestSandboxWorkflow.run,
                BacktestInput(strategy_spec=s, historical_data_ref=data_ref,
                              sandbox_image="durable-agent-sandbox:latest"),
                id=f"{wf_id}-bt-{s.id}-{self.tick_count}",
            )
            for s in inp.candidate_strategies
        ])
        results = await asyncio.gather(*child_handles, return_exceptions=True)
        self.scorecards = [r for r in results if isinstance(r, Scorecard)]
        for sc in self.scorecards:
            await self._emit(wf_id, "backtest_progress", {
                "status": "done", "strategy_id": sc.strategy_id,
                "sharpe": sc.sharpe, "roi": sc.roi, "max_drawdown": sc.max_drawdown,
                "error": sc.error, "generated_code": sc.generated_code,
            })

        winner = select_winner(self.scorecards)
        winner_spec = next(s for s in inp.candidate_strategies if s.id == winner.strategy_id)
        self.winning_strategy = winner_spec
        self.live_roi = 0.0
        await workflow.execute_activity(
            persist_strategy, winner_spec,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=5),
        )
        await self._emit(wf_id, "phase_change",
                         {"phase": "WINNER_SELECTED",
                          "winning_strategy": winner_spec.model_dump(),
                          "winning_scorecard": winner.model_dump()})

    async def _run_phases_2_and_3(self, inp: AgentInput, wf_id: str) -> bool:
        """Returns True if drift triggered re-synthesis, False if stop requested."""
        self.phase = Phase.WATCHING
        await self._emit(wf_id, "phase_change", {"phase": self.phase.value})

        while not self._stop:
            try:
                await workflow.wait_condition(
                    lambda: self._fast_forward or self._stop or self._force_drift,
                    timeout=timedelta(seconds=inp.tick_seconds),
                )
            except TimeoutError:
                pass
            self._fast_forward = False
            if self._stop:
                return False
            if self._force_drift:
                self._force_drift = False
                await self._emit(wf_id, "drift_detected", {"reason": "forced by chaos"})
                self.phase = Phase.EVOLVING
                await self._emit(wf_id, "phase_change", {"phase": self.phase.value})
                return True

            self.tick_count += 1
            market = await workflow.execute_activity(
                fetch_market_snapshot, inp.ticker,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=5),
            )
            news = await workflow.execute_activity(
                fetch_news_snapshot, inp.ticker,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=5),
            )
            # Apply chaos: injected news + sentiment override
            if self._injected_news:
                news.headlines.extend(self._injected_news)
                self._injected_news = []
            if self._injected_sentiment_override is not None:
                news.sentiment = self._injected_sentiment_override
                self._injected_sentiment_override = None

            intent = await workflow.execute_activity(
                call_agent,
                AgentCallInput(winning_strategy=self.winning_strategy, market=market,
                               news=news, positions=self.positions),
                start_to_close_timeout=timedelta(seconds=60),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            await self._emit(wf_id, "trade_intent", {
                "tick": self.tick_count, "intent": intent.model_dump(),
                "price": market.price, "sentiment": news.sentiment,
            })

            if intent.action == TradeAction.HOLD:
                continue

            risk = await workflow.execute_activity(
                risk_check,
                RiskCheckInput(intent=intent, news=news, positions=self.positions,
                               limits=inp.limits, approval_threshold=inp.approval_threshold),
                start_to_close_timeout=timedelta(seconds=5),
            )
            await self._emit(wf_id, "risk_decision",
                             {"trade_id": intent.id, "decision": risk.decision.value, "reason": risk.reason})

            if risk.decision == RiskDecision.BLOCK:
                continue

            if risk.decision == RiskDecision.ALLOW_REQUIRES_APPROVAL:
                self.phase = Phase.AWAITING_APPROVAL
                await self._emit(wf_id, "approval_request", {
                    "trade_id": intent.id, "intent": intent.model_dump(),
                    "risk": risk.model_dump(), "news_sentiment": news.sentiment,
                    "headlines": [h.model_dump() for h in news.headlines][:3],
                })
                await workflow.wait_condition(lambda: intent.id in self._approvals or self._stop)
                self.phase = Phase.WATCHING
                if self._stop:
                    return False
                if not self._approvals[intent.id]:
                    await self._emit(wf_id, "audit", {"trade_id": intent.id, "outcome": "rejected"})
                    continue

            order = await workflow.execute_activity(
                place_order,
                PlaceOrderInput(intent=intent, idempotency_key=f"{wf_id}:{intent.id}"),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=5),
            )
            await workflow.execute_activity(
                write_trade_record, order,
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=RetryPolicy(maximum_attempts=5),
            )
            self.positions.apply(order)
            self.live_roi += 0.005 if intent.action == TradeAction.BUY else -0.002
            await self._emit(wf_id, "order_placed", {"order": order.model_dump()})

        return False

    async def _emit(self, wf_id: str, kind: str, payload: dict) -> None:
        event = UIEvent(ts=datetime.utcnow(), workflow_id=wf_id, kind=kind, payload=payload)
        await workflow.execute_activity(
            notify_ui, event,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(maximum_attempts=5),
        )
```

- [ ] **Step 2: Modify `backend/worker/main.py` activity registration**

```python
from worker.activities.news import fetch_news_snapshot
from worker.activities.llm import call_agent
from worker.activities.risk import risk_check
from worker.activities.broker import place_order
from worker.activities.market import fetch_historical_data, fetch_market_snapshot
# ...
activities=[
    run_backtest_in_sandbox, persist_strategy, write_trade_record,
    notify_ui, fetch_historical_data, fetch_market_snapshot,
    fetch_news_snapshot, call_agent, risk_check, place_order,
],
```

- [ ] **Step 3: Commit**

```bash
git add backend/worker/workflows/parent.py backend/worker/main.py
git commit -m "feat(workflows): extend parent with Phase 2+3 live loop + signals"
```

---

## Task 27: FastAPI approval endpoints

**Files:**
- Create: `backend/fastapi_app/routes/approvals.py`
- Modify: `backend/fastapi_app/main.py`

- [ ] **Step 1: Create `backend/fastapi_app/routes/approvals.py`**

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..temporal_client import get_temporal_client

router = APIRouter(prefix="/api/runs", tags=["approvals"])


class ApprovalBody(BaseModel):
    trade_id: str
    reason: str | None = None


@router.post("/{workflow_id}/approve")
async def approve(workflow_id: str, body: ApprovalBody) -> dict:
    client = await get_temporal_client()
    h = client.get_workflow_handle(workflow_id)
    try:
        await h.signal("approve_trade", body.trade_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@router.post("/{workflow_id}/reject")
async def reject(workflow_id: str, body: ApprovalBody) -> dict:
    client = await get_temporal_client()
    h = client.get_workflow_handle(workflow_id)
    try:
        await h.signal("reject_trade", body.trade_id, body.reason or "")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}
```

- [ ] **Step 2: Modify `backend/fastapi_app/main.py`**

```python
from .routes.approvals import router as approvals_router
# ...
app.include_router(approvals_router)
```

- [ ] **Step 3: Commit**

```bash
git add backend/fastapi_app/routes/approvals.py backend/fastapi_app/main.py
git commit -m "feat(fastapi): add /approve and /reject signal endpoints"
```

---

## Task 28: Trading Floor component

**Files:**
- Create: `frontend/src/components/TradingFloor.tsx`
- Modify: `frontend/src/hooks/useWorkflow.ts`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Extend `frontend/src/hooks/useWorkflow.ts` to track trades + ticks**

Replace the file:

```ts
import { useMemo } from "react";
import type { UIEvent, Scorecard, StrategySpec } from "./../types";

export type TickPoint = { tick: number; price: number };
export type Trade = {
  trade_id: string;
  action: string;
  qty: number;
  rationale?: string;
  risk?: { decision: string; reason: string };
  order?: { order_id: string; status: string; filled_qty: number; avg_price: number };
};
export type ApprovalReq = {
  trade_id: string;
  intent: { id: string; ticker: string; action: string; qty: number; rationale: string };
  risk: { decision: string; reason: string };
  news_sentiment: number;
  headlines: { title: string; published_at: number }[];
};

export function useWorkflow(events: UIEvent[]) {
  return useMemo(() => {
    let phase = "SYNTHESIZING" as string;
    const scorecards: Record<string, Scorecard> = {};
    let winningStrategy: StrategySpec | null = null;
    let winningScorecard: Scorecard | null = null;
    const ticks: TickPoint[] = [];
    const trades: Record<string, Trade> = {};
    const approvals: ApprovalReq[] = [];

    for (const e of events) {
      if (e.kind === "phase_change") {
        phase = (e.payload.phase as string) ?? phase;
        if (e.payload.winning_strategy) winningStrategy = e.payload.winning_strategy as StrategySpec;
        if (e.payload.winning_scorecard) winningScorecard = e.payload.winning_scorecard as Scorecard;
      }
      if (e.kind === "backtest_progress" && e.payload.status === "done") {
        const sid = e.payload.strategy_id as string;
        scorecards[sid] = {
          strategy_id: sid,
          roi: (e.payload.roi as number) ?? 0,
          sharpe: (e.payload.sharpe as number) ?? 0,
          max_drawdown: (e.payload.max_drawdown as number) ?? 0,
          win_rate: 0,
          num_trades: 0,
          generated_code: (e.payload.generated_code as string) ?? "",
          error: (e.payload.error as string) ?? null,
        };
      }
      if (e.kind === "trade_intent") {
        const intent = e.payload.intent as Trade & { id: string };
        ticks.push({ tick: e.payload.tick as number, price: e.payload.price as number });
        trades[intent.id] = {
          trade_id: intent.id, action: intent.action, qty: intent.qty,
          rationale: (intent as any).rationale,
        };
      }
      if (e.kind === "risk_decision") {
        const t = trades[e.payload.trade_id as string];
        if (t) t.risk = { decision: e.payload.decision as string, reason: e.payload.reason as string };
      }
      if (e.kind === "approval_request") {
        approvals.push(e.payload as unknown as ApprovalReq);
      }
      if (e.kind === "order_placed") {
        const o = e.payload.order as Trade["order"];
        // Match by most-recent intent (simple heuristic for demo)
        const recent = Object.values(trades).reverse()[0];
        if (recent && o) recent.order = o;
      }
    }

    const pendingApproval = approvals.find(
      (a) => !trades[a.trade_id]?.order && trades[a.trade_id]?.risk?.decision === "allow_requires_approval",
    );

    return { phase, scorecards, winningStrategy, winningScorecard, ticks, trades, pendingApproval };
  }, [events]);
}
```

- [ ] **Step 2: Create `frontend/src/components/TradingFloor.tsx`**

```tsx
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import type { TickPoint, Trade } from "../hooks/useWorkflow";

export function TradingFloor({ ticks, trades }: { ticks: TickPoint[]; trades: Record<string, Trade> }) {
  const data = ticks.slice(-50);
  const tradeList = Object.values(trades).slice(-15).reverse();
  return (
    <div className="grid grid-cols-3 gap-6">
      <div className="col-span-2 border border-border rounded p-4 bg-card h-72">
        <div className="text-xs uppercase tracking-widest text-foreground/60 mb-2">Price (last 50 ticks)</div>
        <ResponsiveContainer width="100%" height="90%">
          <LineChart data={data}>
            <XAxis dataKey="tick" stroke="#64748b" tick={{ fontSize: 10 }} />
            <YAxis domain={["auto", "auto"]} stroke="#64748b" tick={{ fontSize: 10 }} />
            <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155" }} />
            <Line type="monotone" dataKey="price" stroke="hsl(189 90% 55%)" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="border border-border rounded p-4 bg-card h-72 overflow-auto">
        <div className="text-xs uppercase tracking-widest text-foreground/60 mb-2">Trade Intents</div>
        <div className="font-mono text-xs space-y-2">
          {tradeList.length === 0 && <div className="text-foreground/40">awaiting ticks…</div>}
          {tradeList.map((t) => (
            <div key={t.trade_id} className="border-b border-border/60 pb-2">
              <div className="flex gap-2 items-baseline">
                <span className={"font-bold " + (t.action === "BUY" ? "text-emerald-300" :
                                                  t.action === "SELL" ? "text-rose-300" : "text-foreground/60")}>
                  {t.action}
                </span>
                <span>{t.qty}</span>
                {t.risk && (
                  <span className={"text-[10px] uppercase " +
                                   (t.risk.decision === "allow" ? "text-emerald-300" :
                                    t.risk.decision === "block" ? "text-rose-300" : "text-amber-300")}>
                    {t.risk.decision}
                  </span>
                )}
                {t.order && <span className="text-emerald-300 text-[10px]">✓ {t.order.order_id}</span>}
              </div>
              {t.rationale && <div className="text-foreground/50 text-[10px] truncate">{t.rationale}</div>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Mount Trading Floor in `App.tsx`** (replace section)

```tsx
import { useState } from "react";
import { MissionControl } from "./components/MissionControl";
import { EventLog } from "./components/EventLog";
import { WarRoom } from "./components/WarRoom";
import { TradingFloor } from "./components/TradingFloor";
import { useSSE } from "./hooks/useSSE";
import { useWorkflow } from "./hooks/useWorkflow";

export default function App() {
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const expected = 8;
  const events = useSSE(workflowId);
  const { phase, scorecards, winningStrategy, ticks, trades } = useWorkflow(events);

  return (
    <div className="min-h-screen p-10 max-w-6xl mx-auto space-y-8">
      <header className="flex items-baseline justify-between">
        <h1 className="text-3xl font-semibold tracking-tight">
          <span className="text-accent">Durable</span> Agentic Harness
        </h1>
        <span className="text-xs font-mono text-foreground/50">{workflowId ?? "no active run"}</span>
      </header>
      <MissionControl workflowId={workflowId} onStart={setWorkflowId} currentPhase={phase} />
      <section>
        <h2 className="text-sm uppercase tracking-widest text-foreground/60 mb-3">War Room</h2>
        <WarRoom scorecards={scorecards} winningStrategy={winningStrategy} expected={expected} />
      </section>
      <section>
        <h2 className="text-sm uppercase tracking-widest text-foreground/60 mb-3">Trading Floor</h2>
        <TradingFloor ticks={ticks} trades={trades} />
      </section>
      <EventLog events={events} />
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/useWorkflow.ts frontend/src/components/TradingFloor.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add Trading Floor with price chart + intent table"
```

---

## Task 29: Approval modal

**Files:**
- Create: `frontend/src/components/ApprovalModal.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create `frontend/src/components/ApprovalModal.tsx`**

```tsx
import type { ApprovalReq } from "../hooks/useWorkflow";

export function ApprovalModal({
  workflowId, request, onClose,
}: {
  workflowId: string;
  request: ApprovalReq;
  onClose: () => void;
}) {
  async function send(action: "approve" | "reject") {
    await fetch(`/api/runs/${workflowId}/${action}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ trade_id: request.trade_id }),
    });
    onClose();
  }
  return (
    <div className="fixed inset-0 bg-background/80 backdrop-blur flex items-center justify-center z-50">
      <div className="bg-card border border-border rounded-lg p-6 max-w-md w-full space-y-4 shadow-2xl">
        <div className="text-xs uppercase tracking-widest text-amber-300">Approval Required</div>
        <div className="font-mono text-sm">
          <div className="flex justify-between"><span>Action</span><span className="text-accent">{request.intent.action}</span></div>
          <div className="flex justify-between"><span>Ticker</span><span>{request.intent.ticker}</span></div>
          <div className="flex justify-between"><span>Qty</span><span>{request.intent.qty}</span></div>
          <div className="flex justify-between"><span>Sentiment</span><span>{request.news_sentiment.toFixed(2)}</span></div>
        </div>
        <div className="text-xs text-foreground/70 italic">"{request.intent.rationale}"</div>
        <div className="text-xs text-foreground/60">
          <div className="font-bold mb-1">Risk:</div>
          <div>{request.risk.reason}</div>
        </div>
        <div className="text-xs text-foreground/60">
          <div className="font-bold mb-1">Recent headlines:</div>
          <ul className="list-disc pl-4 space-y-1">
            {request.headlines.map((h, i) => <li key={i}>{h.title}</li>)}
          </ul>
        </div>
        <div className="flex gap-3 pt-2">
          <button onClick={() => send("approve")}
                  className="flex-1 bg-emerald-500 text-background font-bold rounded px-4 py-2 hover:opacity-90">
            Approve
          </button>
          <button onClick={() => send("reject")}
                  className="flex-1 bg-rose-500 text-background font-bold rounded px-4 py-2 hover:opacity-90">
            Reject
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Mount the modal in `App.tsx`**

Add inside the main `<div>` (before closing `</div>`):

```tsx
{workflowId && pendingApproval && (
  <ApprovalModal workflowId={workflowId} request={pendingApproval} onClose={() => {}} />
)}
```

And destructure `pendingApproval` from `useWorkflow(events)`. Import `ApprovalModal`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ApprovalModal.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add Approval modal wired to /approve and /reject"
```

---

## Task 30: Manual verification of Phase 2+3

- [ ] **Step 1: Boot the stack**

```bash
docker compose down -v && docker compose up --build -d
```

- [ ] **Step 2: Start a run + observe**

Open http://localhost:5173, enter NVDA, start. Within ~2 minutes you should see:
- War Room cards complete with a winner
- Trading Floor ticks every 10s with intents and risk decisions
- Eventually an approval modal pops; click Approve
- An order line appears in the intent table with `✓ ord-…`

- [ ] **Step 3: Verify Temporal Web UI**

Open the workflow at http://localhost:8233. Confirm Signals (`approve_trade`) appear in the event history.

- [ ] **Step 4: Tear down + tag**

```bash
docker compose down
git tag phase-c-complete
git commit --allow-empty -m "milestone: Phase C (Trading Floor) complete"
```

**🎉 PHASE C COMPLETE — full Phase 2+3 demo (live loop, risk, approval, broker order) works.**

---

# PHASE D — Phase 4 + Chaos (Tasks 31–36)

## Task 31: `check_drift` activity (TDD)

**Files:**
- Create: `backend/worker/activities/drift.py`
- Create: `backend/tests/unit/test_drift.py`

- [ ] **Step 1: Create `backend/tests/unit/test_drift.py`**

```python
from shared.models import DriftInput
from worker.activities.drift import _check_drift_pure


def test_no_drift_when_close():
    res = _check_drift_pure(DriftInput(baseline_sharpe=1.5, live_roi=0.18, backtest_roi=0.20, threshold=0.20))
    assert res.drifted is False


def test_drift_when_live_roi_lags():
    res = _check_drift_pure(DriftInput(baseline_sharpe=1.5, live_roi=0.10, backtest_roi=0.30, threshold=0.20))
    assert res.drifted is True
    assert "lag" in res.reason.lower() or "drift" in res.reason.lower()
```

- [ ] **Step 2: Create `backend/worker/activities/drift.py`**

```python
from temporalio import activity

from shared.models import DriftInput, DriftResult


def _check_drift_pure(inp: DriftInput) -> DriftResult:
    if inp.backtest_roi <= 0:
        return DriftResult(drifted=False, reason="no backtest ROI baseline")
    gap = (inp.backtest_roi - inp.live_roi) / abs(inp.backtest_roi)
    if gap > inp.threshold:
        return DriftResult(drifted=True,
                           reason=f"live ROI lags backtest by {gap*100:.0f}% (threshold {inp.threshold*100:.0f}%)")
    return DriftResult(drifted=False, reason=f"within tolerance ({gap*100:.0f}%)")


@activity.defn
async def check_drift(inp: DriftInput) -> DriftResult:
    return _check_drift_pure(inp)
```

- [ ] **Step 3: Run tests — expect pass**

```bash
cd backend && pytest tests/unit/test_drift.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/worker/activities/drift.py backend/tests/unit/test_drift.py
git commit -m "feat(activities): add check_drift with ratio-vs-baseline rule"
```

---

## Task 32: Drift loop-back in parent workflow

**Files:**
- Modify: `backend/worker/workflows/parent.py`
- Modify: `backend/worker/main.py`

- [ ] **Step 1: Add drift check inside the live loop in `parent.py`**

After the `order_placed` emit and `self.live_roi` update, add:

```python
            # ───── PHASE 4 drift check ─────
            from shared.constants import DRIFT_CHECK_TICK_INTERVAL
            from worker.activities.drift import check_drift  # noqa: imported above too
            from shared.models import DriftInput
            if self.tick_count % DRIFT_CHECK_TICK_INTERVAL == 0:
                baseline_roi = next(
                    (s.roi for s in self.scorecards if s.strategy_id == self.winning_strategy.id),
                    0.0,
                )
                drift = await workflow.execute_activity(
                    check_drift,
                    DriftInput(baseline_sharpe=0.0, live_roi=self.live_roi,
                               backtest_roi=baseline_roi, threshold=inp.drift_threshold),
                    start_to_close_timeout=timedelta(seconds=5),
                )
                if drift.drifted:
                    await self._emit(wf_id, "drift_detected", {"reason": drift.reason})
                    self.phase = Phase.EVOLVING
                    await self._emit(wf_id, "phase_change", {"phase": self.phase.value})
                    return True
```

Also add `check_drift` to the top-level imports inside `workflow.unsafe.imports_passed_through()`:

```python
    from worker.activities.drift import check_drift
```

- [ ] **Step 2: Register `check_drift` in `backend/worker/main.py`**

```python
from worker.activities.drift import check_drift
# ...
activities=[
    ..., check_drift,
],
```

- [ ] **Step 3: Commit**

```bash
git add backend/worker/workflows/parent.py backend/worker/main.py
git commit -m "feat(workflows): add Phase 4 drift detection + re-synthesis loop-back"
```

---

## Task 33: FastAPI chaos backend (docker.sock)

**Files:**
- Create: `backend/fastapi_app/chaos.py`

- [ ] **Step 1: Create `backend/fastapi_app/chaos.py`**

```python
import docker
from docker.errors import NotFound

_client: docker.DockerClient | None = None


def _client_lazy() -> docker.DockerClient:
    global _client
    if _client is None:
        _client = docker.from_env()
    return _client


def stop_container(name_substr: str) -> dict:
    c = _client_lazy()
    matches = [ct for ct in c.containers.list(all=True) if name_substr in ct.name]
    if not matches:
        raise NotFound(f"no container matching '{name_substr}'")
    for ct in matches:
        ct.stop(timeout=2)
    return {"stopped": [ct.name for ct in matches]}


def start_container(name_substr: str) -> dict:
    c = _client_lazy()
    matches = [ct for ct in c.containers.list(all=True) if name_substr in ct.name]
    if not matches:
        raise NotFound(f"no container matching '{name_substr}'")
    for ct in matches:
        ct.start()
    return {"started": [ct.name for ct in matches]}
```

- [ ] **Step 2: Commit**

```bash
git add backend/fastapi_app/chaos.py
git commit -m "feat(fastapi): add docker.sock chaos helpers (stop/start containers)"
```

---

## Task 34: FastAPI chaos routes

**Files:**
- Create: `backend/fastapi_app/routes/chaos.py`
- Modify: `backend/fastapi_app/main.py`
- Modify: `docker-compose.yml` (mount docker.sock into fastapi)

- [ ] **Step 1: Create `backend/fastapi_app/routes/chaos.py`**

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..chaos import stop_container, start_container
from ..db import log_chaos
from ..temporal_client import get_temporal_client

router = APIRouter(prefix="/api/chaos", tags=["chaos"])


class WorkflowChaos(BaseModel):
    workflow_id: str


class InjectNewsBody(BaseModel):
    workflow_id: str
    headline: str
    sentiment: float


@router.post("/kill_worker")
async def kill_worker() -> dict:
    try:
        res = stop_container("worker")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    log_chaos("global", "kill_worker", res)
    return res


@router.post("/restart_worker")
async def restart_worker() -> dict:
    try:
        res = start_container("worker")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    log_chaos("global", "restart_worker", res)
    return res


@router.post("/crash_broker")
async def crash_broker() -> dict:
    try:
        res = stop_container("mockoon")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    log_chaos("global", "crash_broker", res)
    return res


@router.post("/restart_broker")
async def restart_broker() -> dict:
    try:
        res = start_container("mockoon")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    log_chaos("global", "restart_broker", res)
    return res


@router.post("/fast_forward")
async def fast_forward(body: WorkflowChaos) -> dict:
    client = await get_temporal_client()
    h = client.get_workflow_handle(body.workflow_id)
    await h.signal("fast_forward_tick")
    log_chaos(body.workflow_id, "fast_forward", {})
    return {"ok": True}


@router.post("/inject_news")
async def inject_news(body: InjectNewsBody) -> dict:
    client = await get_temporal_client()
    h = client.get_workflow_handle(body.workflow_id)
    await h.signal("inject_news", body.headline, body.sentiment)
    log_chaos(body.workflow_id, "inject_news", body.model_dump())
    return {"ok": True}


@router.post("/force_drift")
async def force_drift(body: WorkflowChaos) -> dict:
    client = await get_temporal_client()
    h = client.get_workflow_handle(body.workflow_id)
    await h.signal("force_drift")
    log_chaos(body.workflow_id, "force_drift", {})
    return {"ok": True}
```

- [ ] **Step 2: Mount the router in `backend/fastapi_app/main.py`**

```python
from .routes.chaos import router as chaos_router
# ...
app.include_router(chaos_router)
```

- [ ] **Step 3: Mount docker.sock into FastAPI in `docker-compose.yml`**

Update the `fastapi` service:

```yaml
  fastapi:
    build:
      context: ./backend
      dockerfile: Dockerfile.fastapi
    env_file: .env
    environment:
      - TEMPORAL_ADDRESS=temporal:7233
      - MOCKOON_BASE_URL=http://mockoon:3001
    ports: ["8000:8000"]
    depends_on: [temporal, mockoon]
    volumes:
      - fastapi-data:/app/fastapi_app
      - /var/run/docker.sock:/var/run/docker.sock
    networks: [demo_net]
```

- [ ] **Step 4: Commit**

```bash
git add backend/fastapi_app/routes/chaos.py backend/fastapi_app/main.py docker-compose.yml
git commit -m "feat(fastapi): add chaos routes (kill/restart worker, fast-forward, inject_news, force_drift)"
```

---

## Task 35: Frontend Chaos Panel

**Files:**
- Create: `frontend/src/hooks/useChaos.ts`, `frontend/src/components/ChaosPanel.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create `frontend/src/hooks/useChaos.ts`**

```ts
export function useChaos(workflowId: string | null) {
  async function call(path: string, body?: object) {
    await fetch(`/api/chaos/${path}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
  }
  return {
    killWorker: () => call("kill_worker"),
    restartWorker: () => call("restart_worker"),
    crashBroker: () => call("crash_broker"),
    restartBroker: () => call("restart_broker"),
    fastForward: () => workflowId && call("fast_forward", { workflow_id: workflowId }),
    forceDrift: () => workflowId && call("force_drift", { workflow_id: workflowId }),
    injectBadNews: () =>
      workflowId &&
      call("inject_news", {
        workflow_id: workflowId,
        headline: "SEC probe into NVDA announced overnight",
        sentiment: -0.85,
      }),
  };
}
```

- [ ] **Step 2: Create `frontend/src/components/ChaosPanel.tsx`**

```tsx
import { useChaos } from "../hooks/useChaos";

export function ChaosPanel({ workflowId }: { workflowId: string | null }) {
  const c = useChaos(workflowId);
  const Btn = ({ label, onClick, variant }: { label: string; onClick: () => void | Promise<void>; variant: "danger" | "warn" | "info" }) => (
    <button
      onClick={onClick}
      className={"text-xs font-mono uppercase tracking-wider rounded px-2 py-1 transition-all " +
                 (variant === "danger" ? "bg-rose-500/20 text-rose-200 hover:bg-rose-500/40" :
                  variant === "warn" ? "bg-amber-500/20 text-amber-200 hover:bg-amber-500/40" :
                  "bg-accent/20 text-accent hover:bg-accent/40")}
    >
      {label}
    </button>
  );
  return (
    <div className="fixed right-6 top-1/2 -translate-y-1/2 w-44 space-y-2 z-40 bg-card border border-border rounded p-3">
      <div className="text-[10px] uppercase tracking-widest text-foreground/50 mb-1">Chaos</div>
      <Btn label="Kill Worker"     onClick={c.killWorker}    variant="danger" />
      <Btn label="Restart Worker"  onClick={c.restartWorker} variant="info" />
      <Btn label="Crash Broker"    onClick={c.crashBroker}   variant="danger" />
      <Btn label="Restart Broker"  onClick={c.restartBroker} variant="info" />
      <Btn label="Inject Bad News" onClick={c.injectBadNews} variant="warn" />
      <Btn label="Fast Forward"    onClick={c.fastForward}   variant="info" />
      <Btn label="Force Drift"     onClick={c.forceDrift}    variant="warn" />
    </div>
  );
}
```

- [ ] **Step 3: Mount the panel in `App.tsx`**

Add `<ChaosPanel workflowId={workflowId} />` inside the main `<div>`, alongside the approval modal. Import it.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/useChaos.ts frontend/src/components/ChaosPanel.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add Chaos Panel (kill/restart/inject/fast-forward/drift)"
```

---

## Task 36: Full stage rehearsal

- [ ] **Step 1: Boot the full stack**

```bash
docker compose down -v && docker compose up --build -d
```

- [ ] **Step 2: Run through the demo script** (see `docs/superpowers/specs/2026-05-21-self-evolving-stock-agent-design.md` §9)

Walk through:
1. Start NVDA
2. War Room populates, winner glows
3. Trading Floor starts ticking
4. Click `Inject Bad News` → next tick: risk_decision becomes BLOCK
5. Wait a few ticks for fresh news → approval modal pops → Approve
6. Click `Kill Worker` mid-loop
7. Wait ~5 seconds → click `Restart Worker` → workflow resumes (visible in Temporal UI history)
8. Click `Force Drift` → Phase badge → EVOLVING → new fan-out cycle starts
9. Wait for new winner + resumed live loop

- [ ] **Step 3: Smoke test workflows still complete**

```bash
cd backend && pytest -m e2e -v
```

Expected: hello smoke still passes (it's a sanity gate, not a full demo test).

- [ ] **Step 4: Tag final milestone**

```bash
docker compose down
git tag phase-d-complete
git commit --allow-empty -m "milestone: Phase D (Evolution + Chaos) complete — demo-ready"
```

**🎉 ALL PHASES COMPLETE — full stage-ready demo.**

---

# Self-Review Checklist (performed at end of plan)

**Spec coverage:**
- §1 Goal — Phase A→D produces the demo
- §2 Decisions — every locked decision has a corresponding task (data mode switch: Task 12/22; tick: Task 26; chaos: Tasks 33–35)
- §3 Architecture — Tasks 1–8 build all 6 containers
- §4 Workflows — Tasks 14 (child), 15 (parent Phase 1), 26 (Phase 2+3), 32 (Phase 4)
- §5 Activities — Tasks 11 (persist/ui), 12 (history), 13 (backtest), 22 (market/news), 23 (LLM), 24 (risk), 25 (broker), 31 (drift)
- §6 Sandbox bridge — Task 13 (with implementation note about API uncertainty)
- §7 Data layer — Tasks 2 (Mockoon), 7 (SQLite), 17 (SSE bus)
- §8 Frontend — Tasks 9 (scaffold), 18 (api/hooks), 19 (Mission Control), 20 (War Room), 28 (Trading Floor), 29 (Approval), 35 (Chaos)
- §9 Stage script — Task 36 rehearsal
- §10 Project structure — covered file-by-file in File Structure section
- §11 Testing/observability — Tasks 10, 15, 24, 31 add unit/e2e tests
- §12 Risks — acknowledged in task notes (sandbox SDK uncertainty in Task 13)

**Placeholder scan:** none found.

**Type consistency:** `Scorecard`, `TradeIntent`, `OrderResult`, `Phase`, `RiskDecision`, `TradeAction` consistent across tasks 4/14/15/24/26.

**Known small gaps fixed inline:**
- Task 26 imports `check_drift` only inside Task 32 (drift activity didn't exist yet at Task 26). Task 32 documents adding the import in workflow.unsafe block at that time.
- `OrderResult.side` is typed `Literal["BUY", "SELL"]`. Task 25's `place_order` uses `inp.intent.action.value` which is `"BUY"`/`"SELL"` from `TradeAction` enum — consistent.

---

# Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-21-self-evolving-stock-agent-plan.md`. Two execution options:**

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best for vibe-coding through ~36 tasks.

2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints. Best if you want to watch every change.

**Which approach?**
