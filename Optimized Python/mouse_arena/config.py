"""config — Python equivalent of MATLAB config/ma_paths.m (constants only).

Ports the acquisition/analysis constants exactly (fixture 00_params). Path
resolution (arena_root, candidate .mat lists) is kept for the pipeline but the
numeric constants below are the ones pinned by the fixture and must match
exactly.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List


def _normalize_lighting(c: str) -> str:
    c = (c or "").strip().lower()
    if c in ("infrared", "ir"):
        return "infrared"
    if c in ("deep-red", "deepred", "deep red", "red", "dr"):
        return "deep-red"
    if c in ("all", "both", "any", ""):
        return "all"
    raise ValueError(f"lighting must be 'infrared', 'deep-red', or 'all' (got {c!r}).")


@dataclass
class Params:
    Fs: float = 500.0
    sentinel: float = -500.0
    skipRecords: int = 20
    # raw .dat channel maps (offsets after each sentinel)
    chan_pid: Dict[str, int] = field(default_factory=lambda: {
        "time": 1, "TS": 2, "PID": 3, "ETH": 4, "val": 7})
    chan_beh: Dict[str, int] = field(default_factory=lambda: {
        "time": 1, "TS": 2, "ETH": 3})
    # difference-of-exponentials kernel constants
    kernel_sensorChar: Dict[str, float] = field(default_factory=lambda: {
        "tau_rise": 0.002, "tau_decay": 0.5})
    kernel_behavior: Dict[str, float] = field(default_factory=lambda: {
        "tau_rise": 0.02, "tau_decay": 2.0})
    # plume-contact criteria
    contact: Dict[str, float] = field(default_factory=lambda: {
        "win_s": 4, "min_sep_s": 5, "min_dist_px": 10,
        "baseline_s": 1, "reward_px": 15, "prominence_mult": 4.0})
    arena_px: List[float] = field(default_factory=lambda: [0, 580, 0, 280])
    fig8_mode: str = "significance"        # 'significance'(prom x4) | 'count'(prom x1)
    fig8_win_samples: int = 201
    lighting: str = "infrared"

    def __post_init__(self):
        self.lighting = _normalize_lighting(self.lighting)
        if self.fig8_mode.lower() == "count":
            self.contact["prominence_mult"] = 1.0
        elif self.fig8_mode.lower() == "significance":
            self.contact["prominence_mult"] = 4.0
        else:
            raise ValueError("fig8_mode must be 'significance' or 'count'.")

    @property
    def fig8_prominence_mult(self) -> float:
        return self.contact["prominence_mult"]


def get_params(**overrides) -> Params:
    """Return the pipeline constants (optionally overriding fields)."""
    p = Params()
    for k, v in overrides.items():
        setattr(p, k, v)
    p.__post_init__()
    return p


PARAMS = get_params()
