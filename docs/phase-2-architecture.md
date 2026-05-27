# Phase 2 Architecture — Trade Intent Loop

The OpenAI Agents SDK trade-intent loop runs **inside** a Temporal workflow. Every tick fetches context, runs the agent, applies a deterministic risk guardrail, and either executes the trade, drops it, or gates it on human approval.

```mermaid
flowchart LR
    Tick([Tick]) --> WF

    subgraph WF["Temporal Workflow — durable, replayable"]
        direction TB
        CTX[Fetch market + news<br/><i>activities</i>]

        subgraph AGENT["OpenAI Agents SDK — Trade Intent Loop"]
            direction TB
            LLM[LLM turn<br/><i>activity</i>]
            TOOLS[Tools: market / news<br/><i>activities</i>]
            LLM <--> TOOLS
        end

        CTX --> AGENT --> INTENT[/TradeIntent<br/>BUY · SELL · HOLD/]
        INTENT --> RISK{{Risk Guardrail<br/><i>deterministic activity</i>}}
    end

    RISK -- BLOCK --> DROP[Drop]
    RISK -- ALLOW --> ORDER[Place Order]
    RISK -- NEEDS APPROVAL --> HUMAN{{Human Approval<br/><i>signal</i>}}
    HUMAN -- approve --> ORDER
    HUMAN -- reject --> DROP

    classDef wf       fill:#E0ECF8,stroke:#5B7FAA,stroke-width:1px,color:#1F2A44;
    classDef agent    fill:#FBEFD9,stroke:#B89466,stroke-width:1px,color:#5C3A12;
    classDef gate     fill:#F4DDE5,stroke:#B07A91,stroke-width:1px,color:#4A1F33;
    classDef ok       fill:#DCEAD9,stroke:#79A074,stroke-width:1px,color:#1F3D1B;
    classDef bad      fill:#E5E7EB,stroke:#9CA3AF,stroke-width:1px,color:#374151;
    classDef neutral  fill:#F5F5F4,stroke:#A8A29E,stroke-width:1px,color:#1C1917;

    class WF wf;
    class AGENT agent;
    class RISK,HUMAN gate;
    class ORDER ok;
    class DROP bad;
    class Tick,CTX,LLM,TOOLS,INTENT neutral;
```

## Key beats

- **Outer box** — durable Temporal workflow; everything inside survives worker crashes and replays from history.
- **Inner box** — the OpenAI Agents SDK loop. Each LLM turn and each tool call is dispatched as a Temporal activity via `OpenAIAgentsPlugin` and `activity_as_tool`, so the multi-turn reasoning loop is durable end-to-end.
- **Risk guardrail** — a deterministic, non-LLM activity. The trustworthy gate sitting between the model and the broker.
- **Three exits** — `BLOCK` drops the intent, `ALLOW` places the order, `ALLOW_REQUIRES_APPROVAL` pauses on a human signal before executing or rejecting.

Implementation: [backend/worker/workflows/parent.py](../backend/worker/workflows/parent.py)
