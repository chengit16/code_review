"""共享逐次费用与用量完整性契约；不计算账单，也不将未知用量视为零。"""

from typing import Literal

from pydantic import BaseModel


class KnownCost(BaseModel):
    """同一币种的已知历史费用，不能当作完整账单。"""

    currency: Literal["CNY", "USD"]
    total: str


class CumulativeUsage(BaseModel):
    """逐次历史单价的累计及完整性，未知用量不填零。"""

    known_usage_attempts: int
    total_attempts: int
    usage_complete: bool
    priced_attempts: int
    known_tokens: dict[str, int] | None
    known_costs: list[KnownCost]
    cost_complete: bool
