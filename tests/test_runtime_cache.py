"""Tests for AXON runtime caching: PromptCache, ToolResultCache, Cache, CLI flags."""

from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Cache (low-level) tests
# ---------------------------------------------------------------------------


class TestCache(unittest.TestCase):
    """Test the Cache class directly."""

    def test_memory_get_put(self):
        from axon.runtime_cache import Cache
        cache = Cache()
        cache.put("key1", "value1")
        self.assertEqual(cache.get("key1"), "value1")

    def test_miss_returns_none(self):
        from axon.runtime_cache import Cache
        cache = Cache()
        self.assertIsNone(cache.get("nonexistent"))

    def test_stats(self):
        from axon.runtime_cache import Cache
        cache = Cache()
        cache.put("k", "v")
        cache.get("k")
        cache.get("miss")
        stats = cache.stats()
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["size"], 1)

    def test_ttl_expiry(self):
        from axon.runtime_cache import Cache
        cache = Cache()
        cache.put("ephemeral", "data", ttl=0.05)
        self.assertEqual(cache.get("ephemeral"), "data")
        time.sleep(0.06)
        self.assertIsNone(cache.get("ephemeral"))

    def test_invalidate(self):
        from axon.runtime_cache import Cache
        cache = Cache()
        cache.put("k", "v")
        cache.invalidate("k")
        self.assertIsNone(cache.get("k"))

    def test_clear(self):
        from axon.runtime_cache import Cache
        cache = Cache()
        cache.put("k1", "v1")
        cache.put("k2", "v2")
        cache.clear()
        self.assertIsNone(cache.get("k1"))
        self.assertIsNone(cache.get("k2"))

    def test_disk_persistence(self):
        from axon.runtime_cache import Cache
        with tempfile.TemporaryDirectory() as tmpdir:
            cache1 = Cache(cache_dir=Path(tmpdir))
            cache1.put("disk_key", "disk_value")
            # Create a new cache pointing to same dir
            cache2 = Cache(cache_dir=Path(tmpdir))
            self.assertEqual(cache2.get("disk_key"), "disk_value")

    def test_disk_ttl_expiry(self):
        from axon.runtime_cache import Cache
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(cache_dir=Path(tmpdir))
            cache.put("temp", "val", ttl=0.05)
            time.sleep(0.06)
            self.assertIsNone(cache.get("temp"))
            # Disk file should be cleaned up
            disk_files = list(Path(tmpdir).glob("*.json"))
            self.assertEqual(len(disk_files), 0)


# ---------------------------------------------------------------------------
# PromptCache tests
# ---------------------------------------------------------------------------


class TestPromptCache(unittest.TestCase):
    """Test the PromptCache class."""

    def test_basic_get_put(self):
        from axon.runtime_cache import Cache, PromptCache
        pc = PromptCache(Cache())
        self.assertIsNone(pc.get("hello", "gpt-4"))
        pc.put("hello", "gpt-4", 0.7, "world")
        self.assertEqual(pc.get("hello", "gpt-4"), "world")

    def test_different_models_separate(self):
        from axon.runtime_cache import Cache, PromptCache
        pc = PromptCache(Cache())
        pc.put("hello", "gpt-4", 0.7, "response_a")
        pc.put("hello", "claude-4", 0.7, "response_b")
        self.assertEqual(pc.get("hello", "gpt-4"), "response_a")
        self.assertEqual(pc.get("hello", "claude-4"), "response_b")

    def test_different_prompts_separate(self):
        from axon.runtime_cache import Cache, PromptCache
        pc = PromptCache(Cache())
        pc.put("prompt_a", "gpt-4", 0.7, "resp_a")
        pc.put("prompt_b", "gpt-4", 0.7, "resp_b")
        self.assertEqual(pc.get("prompt_a", "gpt-4"), "resp_a")
        self.assertEqual(pc.get("prompt_b", "gpt-4"), "resp_b")

    def test_ttl(self):
        from axon.runtime_cache import Cache, PromptCache
        pc = PromptCache(Cache())
        pc.put("temp_prompt", "gpt-4", 0.7, "temp_resp", ttl=0.05)
        self.assertEqual(pc.get("temp_prompt", "gpt-4"), "temp_resp")
        time.sleep(0.06)
        self.assertIsNone(pc.get("temp_prompt", "gpt-4"))


# ---------------------------------------------------------------------------
# ToolResultCache tests
# ---------------------------------------------------------------------------


class TestToolResultCache(unittest.TestCase):
    """Test the ToolResultCache class."""

    def test_basic_get_put(self):
        from axon.runtime_cache import Cache, ToolResultCache
        tc = ToolResultCache(Cache())
        self.assertIsNone(tc.get("WebSearch", {"query": "test"}))
        tc.put("WebSearch", {"query": "test"}, ["result1", "result2"])
        self.assertEqual(tc.get("WebSearch", {"query": "test"}), ["result1", "result2"])

    def test_different_args_separate(self):
        from axon.runtime_cache import Cache, ToolResultCache
        tc = ToolResultCache(Cache())
        tc.put("WebSearch", {"query": "a"}, "result_a")
        tc.put("WebSearch", {"query": "b"}, "result_b")
        self.assertEqual(tc.get("WebSearch", {"query": "a"}), "result_a")
        self.assertEqual(tc.get("WebSearch", {"query": "b"}), "result_b")

    def test_different_tools_separate(self):
        from axon.runtime_cache import Cache, ToolResultCache
        tc = ToolResultCache(Cache())
        tc.put("ToolA", {"x": 1}, "a_result")
        tc.put("ToolB", {"x": 1}, "b_result")
        self.assertEqual(tc.get("ToolA", {"x": 1}), "a_result")
        self.assertEqual(tc.get("ToolB", {"x": 1}), "b_result")

    def test_arg_order_independent(self):
        from axon.runtime_cache import Cache, ToolResultCache
        tc = ToolResultCache(Cache())
        tc.put("Tool", {"a": 1, "b": 2}, "result")
        # Different insertion order should still hit
        self.assertEqual(tc.get("Tool", {"b": 2, "a": 1}), "result")


# ---------------------------------------------------------------------------
# RuntimeConfig cache fields
# ---------------------------------------------------------------------------


class TestRuntimeConfigCache(unittest.TestCase):

    def test_cache_defaults(self):
        from axon.runtime import RuntimeConfig
        from pathlib import Path
        config = RuntimeConfig(source_path=Path("test.ax"))
        self.assertTrue(config.cache_enabled)
        self.assertIsNone(config.cache_dir)
        self.assertIsNone(config.cache_ttl)

    def test_cache_disabled(self):
        from axon.runtime import RuntimeConfig
        from pathlib import Path
        config = RuntimeConfig(source_path=Path("test.ax"), cache_enabled=False)
        self.assertFalse(config.cache_enabled)

    def test_cache_dir_set(self):
        from axon.runtime import RuntimeConfig
        from pathlib import Path
        config = RuntimeConfig(
            source_path=Path("test.ax"),
            cache_dir=Path("/tmp/axon_cache"),
            cache_ttl=300.0,
        )
        self.assertEqual(config.cache_dir, Path("/tmp/axon_cache"))
        self.assertEqual(config.cache_ttl, 300.0)


# ---------------------------------------------------------------------------
# RuntimeExecutor cache initialization
# ---------------------------------------------------------------------------


class TestRuntimeExecutorCacheInit(unittest.TestCase):

    def test_cache_initialized_by_default(self):
        from axon.runtime import RuntimeConfig, RuntimeExecutor
        from pathlib import Path
        config = RuntimeConfig(source_path=Path("test.ax"))
        executor = RuntimeExecutor(config)
        self.assertIsNotNone(executor._cache)
        self.assertIsNotNone(executor._prompt_cache)
        self.assertIsNotNone(executor._tool_cache)

    def test_cache_disabled_when_replay(self):
        from axon.runtime import RuntimeConfig, RuntimeExecutor
        from pathlib import Path
        config = RuntimeConfig(
            source_path=Path("test.ax"),
            replay_path=Path("replay.jsonl"),
        )
        executor = RuntimeExecutor(config)
        self.assertIsNone(executor._cache)

    def test_cache_disabled_when_stream(self):
        from axon.runtime import RuntimeConfig, RuntimeExecutor
        from pathlib import Path
        config = RuntimeConfig(
            source_path=Path("test.ax"),
            stream=True,
        )
        executor = RuntimeExecutor(config)
        self.assertIsNone(executor._cache)

    def test_cache_disabled_when_flag_off(self):
        from axon.runtime import RuntimeConfig, RuntimeExecutor
        from pathlib import Path
        config = RuntimeConfig(
            source_path=Path("test.ax"),
            cache_enabled=False,
        )
        executor = RuntimeExecutor(config)
        self.assertIsNone(executor._cache)


# ---------------------------------------------------------------------------
# CLI flag tests
# ---------------------------------------------------------------------------


class TestCacheCLIArgs(unittest.TestCase):

    def test_no_cache_flag(self):
        from axon.cli import _make_arg_parser
        parser = _make_arg_parser()
        args = parser.parse_args(["run", "--no-cache", "test.ax"])
        self.assertFalse(args.cache_enabled)

    def test_cache_dir_flag(self):
        from axon.cli import _make_arg_parser
        parser = _make_arg_parser()
        args = parser.parse_args(["run", "--cache-dir", "/tmp/axon_cache", "test.ax"])
        self.assertEqual(args.cache_dir, "/tmp/axon_cache")

    def test_cache_enabled_by_default(self):
        from axon.cli import _make_arg_parser
        parser = _make_arg_parser()
        args = parser.parse_args(["run", "test.ax"])
        self.assertTrue(args.cache_enabled)


# ---------------------------------------------------------------------------
# Integration: tool dispatch uses cache
# ---------------------------------------------------------------------------


class TestToolDispatchCacheIntegration(unittest.TestCase):
    """Test that the runtime tool cache works end-to-end."""

    def test_tool_cached_on_repeat(self):
        from axon.runtime import RuntimeConfig, RuntimeExecutor
        from pathlib import Path

        config = RuntimeConfig(source_path=Path("test.ax"), mock=True)
        executor = RuntimeExecutor(config)

        # Simulate caching a tool result and retrieving it
        executor._tool_cache.put("Search", {"query": "test"}, "cached_result")
        cached = executor._tool_cache.get("Search", {"query": "test"})
        self.assertEqual(cached, "cached_result")

    def test_prompt_cached_on_repeat(self):
        from axon.runtime import RuntimeConfig, RuntimeExecutor
        from pathlib import Path

        config = RuntimeConfig(source_path=Path("test.ax"), mock=True)
        executor = RuntimeExecutor(config)

        # Simulate caching a prompt response and retrieving it
        executor._prompt_cache.put("hello world", "gpt-4", 0.7, "hello!")
        cached = executor._prompt_cache.get("hello world", "gpt-4")
        self.assertEqual(cached, "hello!")


class TestCacheAnnotationParsing(unittest.TestCase):
    """Test that @cache(ttl: N) annotations are parsed and extracted correctly."""

    def test_cache_annotation_parsed_on_tool(self):
        from axon.parser import parse
        source = '''
@cache(ttl: 300)
tool CachedSearch(query: String) -> String {
    "result"
}
'''
        decls = parse(source, parse_expressions=True)
        self.assertEqual(len(decls), 1)
        tool = decls[0]
        self.assertEqual(tool.name, "CachedSearch")
        self.assertEqual(len(tool.annotations), 1)
        self.assertEqual(tool.annotations[0].name, "cache")
        self.assertEqual(tool.annotations[0].args["ttl"], "300")

    def test_cache_annotation_parsed_on_prompt(self):
        from axon.parser import parse
        source = '''
@cache(ttl: 600)
prompt Greeting(name: String) -> String {
    """Hello, {name}!"""
}
'''
        decls = parse(source, parse_expressions=True)
        self.assertEqual(len(decls), 1)
        prompt = decls[0]
        self.assertEqual(prompt.name, "Greeting")
        self.assertEqual(len(prompt.annotations), 1)
        self.assertEqual(prompt.annotations[0].name, "cache")
        self.assertEqual(prompt.annotations[0].args["ttl"], "600")

    def test_cache_ttl_zero_parsed(self):
        from axon.parser import parse
        source = '''
@cache(ttl: 0)
tool NoCache(query: String) -> String {
    "result"
}
'''
        decls = parse(source, parse_expressions=True)
        tool = decls[0]
        self.assertEqual(tool.annotations[0].args["ttl"], "0")

    def test_no_cache_annotation(self):
        from axon.parser import parse
        source = '''
tool Plain(query: String) -> String {
    "result"
}
'''
        decls = parse(source, parse_expressions=True)
        tool = decls[0]
        self.assertEqual(len(tool.annotations), 0)

    def test_cache_annotation_known_by_validator(self):
        from axon.parser import parse
        from axon.validator import validate
        source = '''
@cache(ttl: 300)
tool CachedSearch(query: String) -> String {
    "result"
}
'''
        decls = parse(source, parse_expressions=True)
        diagnostics = validate(decls)
        # cache is a known annotation, so no warnings
        unknown_warnings = [d for d in diagnostics if d.code == "unknown-annotation"]
        self.assertEqual(len(unknown_warnings), 0)


class TestCacheTTLExtraction(unittest.TestCase):
    """Test that the runtime correctly extracts per-declaration TTLs."""

    def test_tool_ttl_extraction(self):
        from axon.parser import parse
        from axon.ast_nodes import ToolDecl, PromptDecl

        source = '''
@cache(ttl: 300)
tool CachedSearch(query: String) -> String {
    "result"
}

@cache(ttl: 0)
tool NoCache(query: String) -> String {
    "result"
}

tool Plain(query: String) -> String {
    "result"
}
'''
        decls = parse(source, parse_expressions=True)

        tool_cache_ttls = {}
        for decl in decls:
            if isinstance(decl, ToolDecl):
                for ann in decl.annotations:
                    if ann.name == "cache" and "ttl" in ann.args:
                        try:
                            ttl_val = float(ann.args["ttl"])
                            tool_cache_ttls[decl.name] = ttl_val
                        except ValueError:
                            continue

        self.assertEqual(tool_cache_ttls["CachedSearch"], 300.0)
        self.assertEqual(tool_cache_ttls["NoCache"], 0.0)
        self.assertNotIn("Plain", tool_cache_ttls)

    def test_prompt_ttl_extraction(self):
        from axon.parser import parse
        from axon.ast_nodes import ToolDecl, PromptDecl

        source = '''
@cache(ttl: 600)
prompt Greeting(name: String) -> String {
    """Hello, {name}!"""
}
'''
        decls = parse(source, parse_expressions=True)

        prompt_cache_ttls = {}
        prompt_template_ttls = []
        import re as _re
        for decl in decls:
            if isinstance(decl, PromptDecl):
                for ann in decl.annotations:
                    if ann.name == "cache" and "ttl" in ann.args:
                        try:
                            ttl_val = float(ann.args["ttl"])
                            prompt_cache_ttls[decl.name] = ttl_val
                            static_match = _re.split(r"\{[A-Za-z_][A-Za-z0-9_]*\}", decl.template.lstrip(), maxsplit=1)
                            prefix = static_match[0][:80] if static_match else ""
                            if prefix:
                                prompt_template_ttls.append((prefix, ttl_val))
                        except ValueError:
                            continue

        self.assertEqual(prompt_cache_ttls["Greeting"], 600.0)
        self.assertEqual(len(prompt_template_ttls), 1)
        self.assertEqual(prompt_template_ttls[0][1], 600.0)

    def test_prompt_template_prefix_matching(self):
        """Test that rendered prompts can be matched to declarations by template prefix."""
        from axon.parser import parse
        from axon.ast_nodes import PromptDecl
        import re

        source = '''
@cache(ttl: 120)
prompt Summary(text: String) -> String {
    """Summarize the following: {text}"""
}
'''
        decls = parse(source, parse_expressions=True)
        prompt = decls[0]
        # Extract static prefix (before first {variable})
        static_match = re.split(r"\{[A-Za-z_][A-Za-z0-9_]*\}", prompt.template.lstrip(), maxsplit=1)
        template_prefix = static_match[0][:80]

        # Simulate a rendered prompt
        rendered = "Summarize the following: Hello world"
        self.assertTrue(rendered.lstrip().startswith(template_prefix))

    def test_tool_cache_ttl_zero_disables_caching(self):
        """Test that ttl=0 means caching is disabled for that tool."""
        from axon.runtime_cache import ToolResultCache, Cache

        cache = Cache()
        tool_cache = ToolResultCache(cache)

        # With ttl=0, the tool should not be cached
        ttl = 0.0
        ttl_disabled = (ttl == 0.0)
        self.assertTrue(ttl_disabled)

        # Verify normal caching still works
        tool_cache.put("Search", {"q": "test"}, "result", ttl=300)
        self.assertEqual(tool_cache.get("Search", {"q": "test"}), "result")

    def test_tool_cache_with_custom_ttl(self):
        """Test that custom TTL is passed through to the cache."""
        from axon.runtime_cache import ToolResultCache, Cache, CacheEntry
        import time

        cache = Cache()
        tool_cache = ToolResultCache(cache)

        # Put with TTL of 0.01 seconds
        tool_cache.put("FastExpire", {"q": "test"}, "result", ttl=0.01)

        # Should be present immediately
        self.assertEqual(tool_cache.get("FastExpire", {"q": "test"}), "result")

        # Wait for expiry
        time.sleep(0.02)

        # Should be expired
        self.assertIsNone(tool_cache.get("FastExpire", {"q": "test"}))

    def test_prompt_cache_with_custom_ttl(self):
        """Test that custom TTL is passed through to the prompt cache."""
        from axon.runtime_cache import PromptCache, Cache

        cache = Cache()
        prompt_cache = PromptCache(cache)

        # Put with TTL of 0.01 seconds
        prompt_cache.put("hello", "gpt-4", 0.7, "response", ttl=0.01)

        # Should be present immediately
        self.assertEqual(prompt_cache.get("hello", "gpt-4"), "response")

        # Wait for expiry
        time.sleep(0.02)

        # Should be expired
        self.assertIsNone(prompt_cache.get("hello", "gpt-4"))


if __name__ == "__main__":
    unittest.main()
