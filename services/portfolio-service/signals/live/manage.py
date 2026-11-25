"""Follows one virtual position candle by candle (15m). Pure: the live ledger and the replay of the past use the same code.

Inside one candle the stop counts before any target. After the half is closed the stop is the entry; if that same candle closes beyond the entry
again, the rest is closed there. A candle that opens beyond the stop fills at its open (a gap costs more than the stop).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from signals.live.plan import FEE_PERCENT

FEE_SIDE = FEE_PERCENT / 2          # % of the part of the position that is opened or closed


@dataclass
class Fill:
    kind: str                      # a step of the plan, STOP or ENTRY_STOP
    price: float
    units: float
    units_left: float
    percent: float                 # result of this part in % of the whole position, after its fee


@dataclass
class Position:
    side: int
    entry: float
    stop: float                    # the first stop
    steps: list[dict]
    stop_now: float = 0.0
    units_left: float = 100.0
    best: float = 0.0              # most favourable / unfavourable price so far
    worst: float = 0.0
    net_percent: float = -FEE_SIDE          # of the position; the opening fee is paid at once
    exit_reason: str | None = None
    fills: list[Fill] = field(default_factory=list)
    taken: set[str] = field(default_factory=set)          # steps already closed

    def __post_init__(self):
        self.stop_now = self.stop_now or self.stop
        self.best = self.best or self.entry
        self.worst = self.worst or self.entry

    @property
    def stop_percent(self) -> float:
        return 100 * abs(self.entry - self.stop) / self.entry

    @property
    def closed(self) -> bool:
        return self.units_left <= 1e-9

    @property
    def result_r(self) -> float:
        return self.net_percent / self.stop_percent

    def open_percent(self, price: float) -> float:
        """Result of what is still open at this price, in % of the whole position, before its closing fee."""
        return self.units_left / 100 * 100 * self.side * (price - self.entry) / self.entry

    def _close(self, kind: str, price: float, units: float) -> Fill:
        units = min(units, self.units_left)
        percent = units / 100 * (100 * self.side * (price - self.entry) / self.entry - FEE_SIDE)
        self.units_left = max(0.0, round(self.units_left - units, 6))
        self.net_percent += percent
        f = Fill(kind, price, units, self.units_left, percent)
        self.fills.append(f)
        self.taken.add(kind)
        if self.closed:
            self.exit_reason = kind
        return f

    def _stopped(self, opened: float) -> Fill:
        gap = self.side * (opened - self.stop_now) < 0
        return self._close("ENTRY_STOP" if self.stop_now == self.entry else "STOP", opened if gap else self.stop_now, self.units_left)

    def candle(self, opened: float, high: float, low: float, close: float) -> list[Fill]:
        """What this closed candle did to the position."""
        if self.closed:
            return []
        against, favour = (low, high) if self.side == 1 else (high, low)
        stopped = self._stopped(opened) if self.side * (against - self.stop_now) <= 0 else None
        reached = stopped.price if stopped else against
        if self.side * (reached - self.worst) < 0:
            self.worst = reached
        if stopped:
            return [stopped]
        if self.side * (favour - self.best) > 0:
            self.best = favour
        out = []
        for s in self.steps:
            if self.closed or s["zone"] in self.taken or self.side * (favour - s["price"]) < 0:
                continue
            out.append(self._close(s["zone"], s["price"], s["units"]))
            if s["moves_stop"] and not self.closed:
                self.stop_now = self.entry
        if out and not self.closed and self.stop_now == self.entry and self.side * (close - self.entry) <= 0:
            out.append(self._close("ENTRY_STOP", self.entry, self.units_left))
        return out
