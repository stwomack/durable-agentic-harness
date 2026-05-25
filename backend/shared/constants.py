from enum import Enum


class Phase(str, Enum):
    SYNTHESIZING = "SYNTHESIZING"
    WATCHING = "WATCHING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"


class RiskDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    ALLOW_REQUIRES_APPROVAL = "allow_requires_approval"


class TradeAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


RESTRICTED_NEWS_TERMS = ("fraud", "sec probe", "bankruptcy", "trading halt", "delisting")
