"""Tests for StreamingCollector and streaming runtime integration."""

from axon.streaming_collector import StreamingCollector
from axon.trace_emitter import TraceEmitter


def test_collector_buffers_chunks() -> None:
    collector = StreamingCollector()
    collector.start()
    collector.collect("hello ")
    collector.collect("world")
    collector.finish()
    assert collector.to_text() == "hello world"
    assert collector.to_list() == ["hello ", "world"]


def test_collector_emits_trace_events() -> None:
    emitter = TraceEmitter()
    collector = StreamingCollector(emitter=emitter)
    collector.start(method_name="run", model_reference="@mock/gpt")
    collector.collect("chunk1")
    collector.finish(result_type="ok")

    types = [e["event_type"] for e in emitter.events]
    assert "model_stream_start" in types
    assert "model_stream_chunk" in types
    assert "model_stream_end" in types


def test_collector_thread_safe() -> None:
    import threading
    collector = StreamingCollector()
    collector.start()

    def worker() -> None:
        for i in range(10):
            collector.collect(f"c{i}")

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    collector.finish()
    assert len(collector.to_list()) == 50


def test_collector_state_tracking() -> None:
    collector = StreamingCollector()
    assert not collector.is_started()
    assert not collector.is_finished()

    collector.start()
    assert collector.is_started()
    assert not collector.is_finished()

    collector.collect("x")
    collector.finish(result_type="error")
    assert collector.is_finished()

    snapshot = collector.to_dict()
    assert snapshot["started"] is True
    assert snapshot["finished"] is True
    assert snapshot["result_type"] == "error"
    assert snapshot["chunk_count"] == 1
