# Phase 2 Architecture — Trade Intent Loop

Phase 2 is where the **OpenAI Agents SDK** runs **inside** a **Temporal Workflow**. Every tick: fetch context, run the agent loop, apply a deterministic risk guardrail, then execute, drop, or gate the trade on a human signal. The bridge between the two SDKs is two primitives — `OpenAIAgentsPlugin` and `activity_as_tool`.

```mermaid
flowchart LR
    Tick([Tick]) --> WF

    subgraph WF["Temporal · Workflow — durable, replayable"]
        direction TB
        CTX["Temporal · Activities<br/><b>fetch_market_snapshot</b><br/><b>fetch_news_snapshot</b>"]

        subgraph AGENT["OpenAI Agents SDK · Runner.run — multi-turn agent loop"]
            direction TB
            LLM["Agents SDK · Agent<br/><i>each LLM turn →</i><br/>Bridge · OpenAIAgentsPlugin<br/><i>dispatches as Temporal Activity</i>"]
            TOOLS["Agents SDK · Tools<br/><i>wrapped via</i><br/>Bridge · activity_as_tool<br/><b>fetch_market_snapshot</b> · <b>fetch_news_snapshot</b>"]
            LLM <--> TOOLS
        end

        CTX --> AGENT --> INTENT[/Agents SDK · structured output<br/><b>TradeIntent</b> — BUY · SELL · HOLD/]
        INTENT --> RISK{{"Temporal · Activity<br/><b>risk_check</b><br/><i>deterministic guardrail</i>"}}
    end

    RISK -- BLOCK --> DROP[Drop]
    RISK -- ALLOW --> ORDER["Temporal · Activity<br/><b>place_order</b>"]
    RISK -- NEEDS APPROVAL --> HUMAN{{"Temporal · Signal<br/><b>approve_trade</b> / <b>reject_trade</b>"}}
    HUMAN -- approve --> ORDER
    HUMAN -- reject --> DROP

    classDef temporal  fill:#E0ECF8,stroke:#5B7FAA,stroke-width:1px,color:#1F2A44;
    classDef agents    fill:#DDEEE3,stroke:#6B9D7E,stroke-width:1px,color:#1F3D2E;
    classDef bridge    fill:#E8E0F4,stroke:#8B7AAA,stroke-width:1px,color:#2E1F4A;
    classDef gate      fill:#F4DDE5,stroke:#B07A91,stroke-width:1px,color:#4A1F33;
    classDef ok        fill:#DCEAD9,stroke:#79A074,stroke-width:1px,color:#1F3D1B;
    classDef bad       fill:#E5E7EB,stroke:#9CA3AF,stroke-width:1px,color:#374151;
    classDef neutral   fill:#F5F5F4,stroke:#A8A29E,stroke-width:1px,color:#1C1917;

    class WF,CTX temporal;
    class AGENT,INTENT agents;
    class LLM,TOOLS bridge;
    class RISK,HUMAN gate;
    class ORDER ok;
    class DROP bad;
    class Tick neutral;
```

## Legend

| Color | Meaning |
| --- | --- |
| 🟦 Soft blue | **Temporal primitive** (Workflow · Activity · Signal) |
| 🟩 Sage green | **OpenAI Agents SDK primitive** (Agent · Runner · structured output) |
| 🟪 Lavender | **Bridge primitive** — where the two SDKs meet (`OpenAIAgentsPlugin`, `activity_as_tool`) |
| 🌸 Dusty rose | Deterministic gate (risk check, human approval) |
| 🟢 Sage | Success path |
| ⬜ Light gray | Drop / dead-end |

## Key beats

- **Outer shell** — `Temporal · Workflow`. Every signal, every activity, every LLM turn is recorded in history. A worker crash mid-conversation just replays.
- **Inner loop** — `OpenAI Agents SDK · Runner.run`. Plain SDK code: `Agent(...)`, `Runner.run(agent, ...)`, `output_type=TradeIntent`. No Temporal-specific code in the agent definition.
- **Bridge · `OpenAIAgentsPlugin`** — installed on the worker. Transparently dispatches every LLM turn inside `Runner.run` as a `Temporal · Activity`. The multi-turn reasoning loop becomes durable end-to-end.
- **Bridge · `activity_as_tool`** — wraps a `Temporal · Activity` so the Agent sees it as a normal function tool. Tool calls become activity executions in workflow history.
- **`risk_check`** — `Temporal · Activity`, deterministic. The trustworthy guardrail sitting between the model's intent and the broker.
- **Human gate** — `Temporal · Signal` (`approve_trade` / `reject_trade`). The workflow `wait_condition`s on the approval map; a restart resumes the wait, not the LLM call.
- **`place_order`** — `Temporal · Activity` with an idempotency key derived from workflow ID + intent ID, so retries don't double-trade.

Implementation: [backend/worker/workflows/parent.py](../backend/worker/workflows/parent.py)
