import time
from dataclasses import dataclass, field


@dataclass
class CallMetrics:
    step: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    time_seconds: float = 0.0
    attempts: int = 1
    finish_reason: str = ""
    reasoning_tokens: int = 0
    resolved_model: str = ""


@dataclass
class SessionMetrics:
    model: str = ""
    calls: list[CallMetrics] = field(default_factory=list)
    _start_time: float = field(default=0.0, repr=False)

    @property
    def total_tokens_in(self) -> int:
        return sum(c.tokens_in for c in self.calls)

    @property
    def total_tokens_out(self) -> int:
        return sum(c.tokens_out for c in self.calls)

    @property
    def total_reasoning_tokens(self) -> int:
        return sum(c.reasoning_tokens for c in self.calls)

    @property
    def resolved_models(self) -> list[str]:
        return list(dict.fromkeys(c.resolved_model for c in self.calls if c.resolved_model))

    @property
    def total_cost_usd(self) -> float:
        return sum(c.cost_usd for c in self.calls)

    @property
    def total_time_seconds(self) -> float:
        return sum(c.time_seconds for c in self.calls)

    def start_timer(self):
        self._start_time = time.perf_counter()

    def elapsed(self) -> float:
        if self._start_time == 0.0:
            return 0.0
        return time.perf_counter() - self._start_time

    def add_call(self, call: CallMetrics):
        self.calls.append(call)

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "total_time_seconds": round(self.total_time_seconds, 2),
            "total_tokens_in": self.total_tokens_in,
            "total_tokens_out": self.total_tokens_out,
            "total_reasoning_tokens": self.total_reasoning_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "resolved_models": self.resolved_models,
            "calls": [
                {
                    "step": c.step,
                    "tokens_in": c.tokens_in,
                    "tokens_out": c.tokens_out,
                    "cost_usd": round(c.cost_usd, 6),
                    "time_seconds": round(c.time_seconds, 2),
                    "attempts": c.attempts,
                    "finish_reason": c.finish_reason,
                    "reasoning_tokens": c.reasoning_tokens,
                    "resolved_model": c.resolved_model,
                }
                for c in self.calls
            ],
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "SessionMetrics":
        if not data:
            return cls()
        session = cls(model=str(data.get("model") or ""))
        for call_data in data.get("calls") or []:
            if not isinstance(call_data, dict):
                continue
            session.add_call(
                CallMetrics(
                    step=str(call_data.get("step") or ""),
                    model=session.model,
                    tokens_in=int(call_data.get("tokens_in") or 0),
                    tokens_out=int(call_data.get("tokens_out") or 0),
                    cost_usd=float(call_data.get("cost_usd") or 0),
                    time_seconds=float(call_data.get("time_seconds") or 0),
                    attempts=int(call_data.get("attempts") or 1),
                    finish_reason=str(call_data.get("finish_reason") or ""),
                    reasoning_tokens=int(call_data.get("reasoning_tokens") or 0),
                    resolved_model=str(call_data.get("resolved_model") or ""),
                )
            )
        return session
