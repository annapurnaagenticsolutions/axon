"""Built-in evaluation harness for AXON.

Provides ``axon eval`` with regression detection, golden benchmarking,
and performance gates for CI.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from axon.parser import parse
from axon.type_checker import check_types
from axon.validator import validate


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""

    name: str
    avg_ms: float
    min_ms: float
    max_ms: float
    iterations: int
    passed: bool
    threshold_ms: float


@dataclass
class EvalReport:
    """Full evaluation report."""

    benchmarks: list[BenchmarkResult] = field(default_factory=list)
    overall_passed: bool = True
    total_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_passed": self.overall_passed,
            "total_time_ms": round(self.total_time_ms, 3),
            "benchmarks": [
                {
                    "name": b.name,
                    "avg_ms": round(b.avg_ms, 3),
                    "min_ms": round(b.min_ms, 3),
                    "max_ms": round(b.max_ms, 3),
                    "iterations": b.iterations,
                    "passed": b.passed,
                    "threshold_ms": b.threshold_ms,
                }
                for b in self.benchmarks
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


# --- Golden fixtures --------------------------------------------------------

SIMPLE_AGENT = '''
agent Bot {
    model: @anthropic/claude-4
    tools: []

    fn run(query: Str) -> Str {
        "Hello, " + query
    }
}
'''

COMPLEX_AGENT = '''
tool Search(query: Str) -> Result<List<Str>, Error> {
    /// Search for items.
}

tool Fetch(id: Int) -> Result<Str, Error> {
    /// Fetch item by id.
}

agent ResearchBot {
    model: @anthropic/claude-4
    tools: [Search, Fetch]

    fn search(query: Str) -> Result<List<Str>, Error> {
        act Search(query: query)
    }

    fn fetch_item(id: Int) -> Result<Str, Error> {
        act Fetch(id: id)
    }

    fn run(query: Str) -> Result<Str, Error> {
        let results = search(query: query)?
        let first = results[0]
        fetch_item(id: 1)
    }
}
'''

FLOW_SOURCE = '''
flow Pipeline(input: Str) -> Str {
    stage Process(input: Str) -> Str
    stage Analyze(data: Str) -> Str
    stage Format(result: Str) -> Str

    Process -> Analyze
    Analyze -> Format
}
'''

# --- Harness ----------------------------------------------------------------

class EvalHarness:
    """Runs AXON benchmarks and detects regressions."""

    DEFAULT_THRESHOLDS: dict[str, float] = {
        "parse_simple": 10.0,
        "parse_complex": 20.0,
        "parse_flow": 10.0,
        "typecheck_simple": 15.0,
        "typecheck_complex": 30.0,
        "validate_simple": 20.0,
        "validate_complex": 40.0,
    }

    def __init__(
        self,
        thresholds: dict[str, float] | None = None,
        iterations: int = 5,
        baseline_path: Path | None = None,
    ) -> None:
        self.thresholds = {**self.DEFAULT_THRESHOLDS, **(thresholds or {})}
        self.iterations = iterations
        self.baseline_path = baseline_path
        self._baseline: dict[str, float] | None = None
        if baseline_path and baseline_path.exists():
            self._baseline = json.loads(baseline_path.read_text(encoding="utf-8"))

    def run(self) -> EvalReport:
        """Execute all benchmarks and return a report."""
        report = EvalReport()
        t0 = time.perf_counter()

        report.benchmarks.append(self._bench("parse_simple", lambda: parse(SIMPLE_AGENT)))
        report.benchmarks.append(self._bench("parse_complex", lambda: parse(COMPLEX_AGENT)))
        report.benchmarks.append(self._bench("parse_flow", lambda: parse(FLOW_SOURCE)))
        report.benchmarks.append(self._bench("typecheck_simple", lambda: check_types(parse(SIMPLE_AGENT))))
        report.benchmarks.append(self._bench("typecheck_complex", lambda: check_types(parse(COMPLEX_AGENT))))
        report.benchmarks.append(self._bench("validate_simple", lambda: validate(parse(SIMPLE_AGENT))))
        report.benchmarks.append(self._bench("validate_complex", lambda: validate(parse(COMPLEX_AGENT))))

        report.total_time_ms = (time.perf_counter() - t0) * 1000
        report.overall_passed = all(b.passed for b in report.benchmarks)

        if self.baseline_path:
            self._save_baseline(report)

        return report

    def _bench(self, name: str, fn: Callable[[], Any]) -> BenchmarkResult:
        """Run a single benchmark."""
        times: list[float] = []
        for _ in range(self.iterations):
            start = time.perf_counter()
            fn()
            times.append((time.perf_counter() - start) * 1000)

        avg = sum(times) / len(times)
        threshold = self.thresholds.get(name, avg * 2)

        # Regression check against baseline if available
        if self._baseline and name in self._baseline:
            baseline = self._baseline[name]
            # Allow 20% regression before failing
            threshold = min(threshold, baseline * 1.2)

        return BenchmarkResult(
            name=name,
            avg_ms=avg,
            min_ms=min(times),
            max_ms=max(times),
            iterations=self.iterations,
            passed=avg <= threshold,
            threshold_ms=threshold,
        )

    def _save_baseline(self, report: EvalReport) -> None:
        """Write current results as the new baseline."""
        data = {b.name: round(b.avg_ms, 3) for b in report.benchmarks}
        self.baseline_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
