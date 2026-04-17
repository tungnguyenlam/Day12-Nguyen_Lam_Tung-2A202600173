"""Monthly cost guard for the final production agent."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from fastapi import HTTPException


PRICE_PER_1K_INPUT_TOKENS = 0.00015
PRICE_PER_1K_OUTPUT_TOKENS = 0.0006


@dataclass
class UsageRecord:
    key: str
    input_tokens: int = 0
    output_tokens: int = 0
    request_count: int = 0
    period: str = field(default_factory=lambda: time.strftime("%Y-%m"))

    @property
    def total_cost_usd(self) -> float:
        input_cost = (self.input_tokens / 1000) * PRICE_PER_1K_INPUT_TOKENS
        output_cost = (self.output_tokens / 1000) * PRICE_PER_1K_OUTPUT_TOKENS
        return round(input_cost + output_cost, 6)


class CostGuard:
    def __init__(self, monthly_budget_usd: float):
        self.monthly_budget_usd = monthly_budget_usd
        self._records: dict[str, UsageRecord] = {}

    def _current_period(self) -> str:
        return time.strftime("%Y-%m")

    def _get_record(self, key: str) -> UsageRecord:
        record = self._records.get(key)
        period = self._current_period()
        if not record or record.period != period:
            record = UsageRecord(key=key, period=period)
            self._records[key] = record
        return record

    def check_budget(self, key: str) -> None:
        record = self._get_record(key)
        if record.total_cost_usd >= self.monthly_budget_usd:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "Monthly budget exceeded",
                    "used_usd": record.total_cost_usd,
                    "budget_usd": self.monthly_budget_usd,
                    "period": record.period,
                },
            )

    def record_usage(self, key: str, input_tokens: int, output_tokens: int) -> UsageRecord:
        record = self._get_record(key)
        record.input_tokens += input_tokens
        record.output_tokens += output_tokens
        record.request_count += 1
        return record

    def get_usage(self, key: str) -> dict[str, float | int | str]:
        record = self._get_record(key)
        return {
            "period": record.period,
            "requests": record.request_count,
            "input_tokens": record.input_tokens,
            "output_tokens": record.output_tokens,
            "cost_usd": record.total_cost_usd,
            "budget_usd": self.monthly_budget_usd,
            "budget_remaining_usd": max(0.0, self.monthly_budget_usd - record.total_cost_usd),
            "budget_used_pct": round(record.total_cost_usd / self.monthly_budget_usd * 100, 2),
        }

    def get_global_usage(self) -> dict[str, float | int | str]:
        record = self._get_record("service")
        return self.get_usage(record.key)
