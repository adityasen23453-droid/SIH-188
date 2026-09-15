import time
from typing import Dict, Optional


class StageTimer:
    """
    Centralized high-resolution latency timer and observability tracker for SIH 26188.
    Measures pipeline stages using time.perf_counter() with microsecond precision.
    Enforces privacy compliance: Strictly zero PII logged.
    """

    def __init__(self, document_id: Optional[str] = None):
        self.document_id = document_id
        self._start_time = time.perf_counter()
        self._stage_starts: Dict[str, float] = {}
        self.stage_durations: Dict[str, float] = {}

    def start_stage(self, stage_name: str) -> None:
        self._stage_starts[stage_name] = time.perf_counter()

    def end_stage(self, stage_name: str) -> float:
        if stage_name in self._stage_starts:
            duration_ms = (time.perf_counter() - self._stage_starts[stage_name]) * 1000.0
            self.stage_durations[stage_name] = round(duration_ms, 2)
            return self.stage_durations[stage_name]
        return 0.0

    def total_elapsed_ms(self) -> float:
        return round((time.perf_counter() - self._start_time) * 1000.0, 2)

    def print_summary(self, fast_path: bool = True, recovery_used: str = "none") -> None:
        total_ms = self.total_elapsed_ms()
        self.stage_durations["TOTAL"] = total_ms

        print("\n" + "=" * 55)
        print(f" [PIPELINE TIMING BREAKDOWN] (ID: {self.document_id or 'anonymous'})")
        print("=" * 55)
        for stage, duration in self.stage_durations.items():
            if stage != "TOTAL":
                print(f"  {stage:<18} : {duration:>8.2f} ms")
        print("-" * 55)
        print(f"  {'TOTAL PIPELINE':<18} : {total_ms:>8.2f} ms")
        print(f"  Fast Path: {'YES' if fast_path else 'NO'} | Recovery: {recovery_used}")
        print("=" * 55 + "\n")

    def to_dict(self) -> Dict[str, float]:
        res = dict(self.stage_durations)
        res["TOTAL"] = self.total_elapsed_ms()
        return res
