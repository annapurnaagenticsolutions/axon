"""Tests for AXON structured logger and observability."""

import io
import json

from axon.structured_logger import StructuredLogger, SpanContext


def test_structured_logger_disabled_by_default():
    logger = StructuredLogger()
    buf = io.StringIO()
    logger._output = buf
    logger.info("test")
    assert buf.getvalue() == ""


def test_structured_logger_emits_json():
    buf = io.StringIO()
    logger = StructuredLogger(enabled=True, output=buf)
    logger.info("hello", agent="Bot", method="run")
    line = buf.getvalue().strip()
    record = json.loads(line)
    assert record["level"] == "info"
    assert record["message"] == "hello"
    assert record["agent"] == "Bot"
    assert record["method"] == "run"
    assert "timestamp" in record


def test_structured_logger_levels():
    buf = io.StringIO()
    logger = StructuredLogger(enabled=True, output=buf)
    logger.debug("d")
    logger.info("i")
    logger.warn("w")
    logger.error("e")
    lines = [json.loads(l) for l in buf.getvalue().strip().split("\n")]
    levels = [l["level"] for l in lines]
    assert levels == ["debug", "info", "warn", "error"]


def test_structured_logger_span():
    buf = io.StringIO()
    logger = StructuredLogger(enabled=True, output=buf)
    with logger.span("tool_dispatch", trace_id="abc", span_id="def", tool="Search") as span:
        assert isinstance(span, SpanContext)
    lines = [json.loads(l) for l in buf.getvalue().strip().split("\n")]
    assert len(lines) == 2
    assert lines[0]["message"] == "span_start: tool_dispatch"
    assert lines[0]["span_name"] == "tool_dispatch"
    assert lines[0]["trace_id"] == "abc"
    assert lines[1]["message"] == "span_end: tool_dispatch"
    assert lines[1]["duration_ms"] >= 0
    assert lines[1]["status"] == "ok"


def test_structured_logger_span_with_error():
    buf = io.StringIO()
    logger = StructuredLogger(enabled=True, output=buf)
    try:
        with logger.span("failing_op"):
            raise ValueError("boom")
    except ValueError:
        pass
    lines = [json.loads(l) for l in buf.getvalue().strip().split("\n")]
    assert lines[1]["status"] == "error"
    assert "boom" in lines[1]["error"]
