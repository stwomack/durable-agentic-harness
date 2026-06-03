# Phase 1 Architecture — Strategy Discovery

Phase 1 is **pure Temporal** — no LLM, no Agents SDK. The parent workflow fans out N child workflows in parallel, each running a backtest activity in a sandbox. Scorecards come back, the parent deterministically picks a winner, and persists it before Phase 2 begins.

```mermaid
flowchart LR
    INPUT([AgentInput<br/>ticker · candidates · range]) --> WF

    subgraph WF["Temporal · Workflow — durable, replayable"]
        direction TB
        FETCH["Temporal · Activity<br/><b>fetch_historical_data</b>"]

        subgraph FANOUT["Temporal · Child Workflows — fan-out, one per candidate"]
            direction TB
            C1["BacktestSandbox #1"]
            C2["BacktestSandbox #2"]
            CN["BacktestSandbox #N"]
        end

        FETCH --> FANOUT --> CARDS[/Scorecards<br/>sharpe · roi · drawdown/]
        CARDS --> SELECT{{Deterministic workflow logic<br/><b>select_winner</b>}}
        SELECT --> PERSIST["Temporal · Activity<br/><b>persist_strategy</b>"]
    end

    PERSIST --> NEXT([Transition to Phase 2<br/>WATCHING])

    classDef temporal  fill:#E0ECF8,stroke:#5B7FAA,stroke-width:1px,color:#1F2A44;
    classDef logic     fill:#F4DDE5,stroke:#B07A91,stroke-width:1px,color:#4A1F33;
    classDef ok        fill:#DCEAD9,stroke:#79A074,stroke-width:1px,color:#1F3D1B;
    classDef neutral   fill:#F5F5F4,stroke:#A8A29E,stroke-width:1px,color:#1C1917;

    class WF,FANOUT,FETCH,PERSIST,C1,C2,CN temporal;
    class SELECT logic;
    class NEXT ok;
    class INPUT,CARDS neutral;
```

## Legend

| Color | Meaning |
| --- | --- |
| 🟦 Soft blue | **Temporal primitive** (Workflow · Child Workflow · Activity) |
| 🟪 Dusty rose | **Deterministic workflow logic** — runs inside the workflow, replay-safe |
| 🟩 Sage | **Phase transition** |

## Key beats

- **Outer box** — `Temporal · Workflow`. The entire discovery phase is durable; if a worker dies mid-fanout, the workflow replays from event history.
- **`fetch_historical_data`** — `Temporal · Activity`. Side-effectful I/O isolated outside workflow code.
- **`BacktestSandbox` #1…N** — `Temporal · Child Workflows`. One per candidate strategy. A bad strategy can't poison its siblings or the parent.
- **`select_winner`** — plain Python inside the workflow. Deterministic: identical scorecards always produce the same winner, which is what makes replay safe.
- **`persist_strategy`** — `Temporal · Activity`. The winner is written before Phase 2 starts so a restart picks up trading on the right strategy.

Implementation: [backend/worker/workflows/parent.py](../backend/worker/workflows/parent.py) · [backend/worker/workflows/backtest.py](../backend/worker/workflows/backtest.py)
