import datetime
from dataclasses import dataclass, field


@dataclass
class RunStats:
    started_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    calls_primary: int = 0
    calls_fallback: int = 0
    total_cost_usd: float = 0.0

    def record_call(self, *, cost_usd: float, tier: str) -> None:
        if tier == "primary":
            self.calls_primary += 1
        else:
            self.calls_fallback += 1
        self.total_cost_usd += cost_usd

    @property
    def total_calls(self) -> int:
        return self.calls_primary + self.calls_fallback

    def format_summary(self, *, query_label: str) -> str:
        elapsed = datetime.datetime.now() - self.started_at
        return (
            f"=== Run Summary: {query_label} ===\n"
            f"Duration:           {self._format_duration(elapsed)}\n"
            f"Total calls:        {self.total_calls}\n"
            f"  Subscription:       {self.calls_primary}\n"
            f"  API fallback:       {self.calls_fallback}\n"
            f"Approx. quota cost: ${self.total_cost_usd:.2f} (would-be API equivalent)\n"
        )

    @staticmethod
    def _format_duration(d: datetime.timedelta) -> str:
        m, s = divmod(int(d.total_seconds()), 60)
        return f"{m}m {s}s"
