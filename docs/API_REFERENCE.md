# AXON API Reference

## Provider Plugin API

### ProviderPlugin

Base class for all LLM providers.

```python
from axon.provider_plugin import ProviderPlugin

class MyProvider(ProviderPlugin):
    def name(self) -> str:
        return "my_provider"
    
    def call(self, prompt, model, max_tokens, temperature=0.7, stream=False):
        # Return Result[str, ProviderError]
        pass
    
    def call_stream(self, prompt, model, max_tokens, temperature=0.7):
        # Yield Result[str, ProviderError]
        pass
```

### Built-in Providers

| Class | Module | Package |
|-------|--------|---------|
| `OpenAIProvider` | `axon.providers.openai_provider` | `openai` |
| `AnthropicProvider` | `axon.providers.anthropic_provider` | `anthropic` |
| `MockProviderPlugin` | `axon.providers.mock_provider` | None |

### Provider Registry

```python
from axon.provider_registry import register_provider, resolve_provider_reference

# Register a provider
register_provider(OpenAIProvider())

# Resolve by reference string
provider = resolve_provider_reference("@openai/gpt-4")
```

## Type System API

### Type Parsing

```python
from axon.type_checker import parse_type

t = parse_type("List<Map<Str, Int>>")
assert t.kind == TypeKind.GENERIC
assert t.name == "List"
```

### Type Checking

```python
from axon.type_checker import check_types, TypeChecker

# Check parsed declarations
decls = parse(source)
diagnostics = check_types(decls)
errors = [d for d in diagnostics if d.severity == "error"]
```

### Subtyping

```python
from axon.type_checker import is_subtype, parse_type

assert is_subtype(parse_type("Int"), parse_type("Float"))  # Numeric widening
assert is_subtype(parse_type("Str"), parse_type("Option<Str>"))
assert is_subtype(parse_type("Str"), parse_type("Str | Int"))
```

## Resilience API

### Retry with Backoff

```python
from axon.resilience import RetryConfig

config = RetryConfig(
    max_retries=3,
    base_delay_seconds=1.0,
    exponential_base=2.0,
)
```

### Circuit Breaker

```python
from axon.resilience import CircuitBreaker, CircuitBreakerConfig

cb = CircuitBreaker("openai", CircuitBreakerConfig(
    failure_threshold=5,
    recovery_timeout_seconds=30.0,
))

result = cb.call(lambda: provider.call(prompt, model, max_tokens))
```

### Resilient Provider Wrapper

```python
from axon.resilience import ResilientProviderWrapper

wrapper = ResilientProviderWrapper("openai")
result = wrapper.execute_with_retry(
    lambda: provider.call(prompt, model, max_tokens)
)
```

## Memory API

```python
from axon.memory_store import MemoryStore

store = MemoryStore()

# Key-value
store.remember("key", value="value", section="working")
value = store.recall("key", section="working")

# Semantic search
store.remember("doc1", vector=[0.1, 0.2, ...])
results = store.recall_similar("query", top_k=5)
```

## Tool Registry API

```python
from axon.tool_registry import MockToolRegistry

registry = MockToolRegistry()
registry.register("Search", search_impl)
registry.register_all(declarations)
```

## Trace Emitter API

```python
from axon.trace_emitter import TraceEmitter

emitter = TraceEmitter()
emitter.emit_model_call(prompt="hello", model="gpt-4")
emitter.emit_tool_dispatch(name="Search", kwargs={"query": "test"})
```

## RAG Registry API

```python
from axon.rag_registry import RagRegistry

registry = RagRegistry()
registry.register(rag_decl)
documents = registry.query("docs", "search query", top_k=5)
```
