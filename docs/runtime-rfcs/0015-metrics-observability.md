# RFC #015 — Metrics & Observability

**Status:** Draft  
**Phase:** 4 Sprint 1  
**Owner:** AXON Runtime Team

## Summary

AXON already collects runtime metrics during agent execution (provider calls, tool dispatches, counters, gauges, histograms). Phase 4 makes these metrics observable outside of the `run` command via a standalone `axon metrics` CLI command, per-agent metrics tracking, and structured export formats.

## Motivation

The `--metrics` flag in `axon run` only shows metrics for a single run. For long-lived agents managed by `AgentLifecycleManager` or supervised by `AgentSupervisor`, operators need to query metrics without re-running the source. A standalone metrics command enables observability of the full runtime.

## Goals

- `axon metrics` CLI command with `show` and `export` subcommands
- Per-agent metrics tracking via `AgentLifecycleManager`
- Structured output: JSON and human-readable text
- Export to file for downstream dashboards
- Integration with existing `MetricsCollector`

## Non-Goals

- External metrics backends (Prometheus, StatsD, etc.) — single-process only
- Real-time streaming metrics — pull-based only
- Custom metric aggregation rules — use existing histogram stats

## Design

### MetricsExporter

```python
class MetricsExporter:
    def __init__(self, collector: MetricsCollector) -> None: ...
    def to_json(self) -> str: ...
    def to_text(self) -> str: ...
    def export_to_file(self, path: Path) -> None: ...
```

### AgentLifecycleManager Integration

`AgentLifecycleManager` tracks a `MetricsCollector` per agent. `AgentInstance` stores a reference so that metrics can be queried:

```python
class AgentInstance:
    ...
    metrics: MetricsCollector | None = None
```

### CLI Surface

```bash
# Show global metrics
axon metrics show [--json]

# Export metrics to file
axon metrics export --output metrics.json [--format json|text]
```

### Trace Events

| Event | Fields | Description |
|---|---|---|
| `metrics_export` | `path`, `format` | Metrics exported to file |

## Testing Strategy

- Unit test `MetricsExporter` produces valid JSON and text
- Unit test CLI dispatch for `metrics show` and `metrics export`
- Verify `--metrics` in `axon run` still works

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Global metrics pollution across runs | Use per-executor/per-agent collectors |
| Large histograms in JSON output | Cap histogram raw values; use stats only |
