"""Tests for AXON OTel exporter."""

from axon.otel_exporter import OTelExporter, Span


def test_otel_start_and_end_span():
    exporter = OTelExporter(service_name="test")
    span = exporter.start_span("op1", attributes={"key": "val"})
    assert isinstance(span, Span)
    assert span.name == "op1"
    assert span.attributes["key"] == "val"
    assert span.end_time_ns == 0
    exporter.end_span(status="OK")
    assert span.end_time_ns > 0
    assert span.status == "OK"


def test_otel_nested_spans():
    exporter = OTelExporter()
    parent = exporter.start_span("parent")
    child = exporter.start_span("child")
    assert child.trace_id == parent.trace_id
    assert child.parent_id == parent.span_id
    exporter.end_span()
    exporter.end_span()


def test_otel_add_event():
    exporter = OTelExporter()
    exporter.start_span("op")
    exporter.add_event("checkpoint", {"phase": "after_tools"})
    assert len(exporter._current_spans[-1].events) == 1
    assert exporter._current_spans[-1].events[0]["name"] == "checkpoint"
    exporter.end_span()


def test_otel_flush_without_endpoint_is_noop():
    exporter = OTelExporter()
    exporter.start_span("op")
    exporter.end_span()
    exporter.flush()  # should not raise


def test_otel_build_otlp_payload():
    exporter = OTelExporter(service_name="axon-test")
    exporter.start_span("op", attributes={"agent": "Bot"})
    payload = exporter._build_otlp_payload()
    assert payload is not None
    assert "resourceSpans" in payload
    rs = payload["resourceSpans"][0]
    assert rs["resource"]["attributes"][0]["key"] == "service.name"
    assert rs["resource"]["attributes"][0]["value"]["stringValue"] == "axon-test"
    exporter.end_span()
