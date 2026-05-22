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

    # Always mint a unique id — the LLM tends to echo the strategy id, which would
    # collide with prior approvals in self._approvals and silently auto-approve every
    # subsequent trade. The id is only used to correlate the approval signal, so a
    # fresh uuid per call is correct.
    return TradeIntent(
        id=f"t-{uuid.uuid4().hex[:8]}",
        ticker=str(data.get("ticker", inp.market.ticker)),
        action=action,
        qty=float(data.get("qty", 0)),
        rationale=str(data.get("rationale", "")),
    )
