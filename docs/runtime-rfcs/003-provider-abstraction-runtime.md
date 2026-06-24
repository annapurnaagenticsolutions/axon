# AXON Runtime RFC #003 — Provider Abstraction Runtime

**Status:** Accepted
**Created:** 2026-06-03
**Owner:** AXON Maintainers

> This RFC proposes a provider abstraction runtime for AXON that enables calling model providers (e.g., Anthropic, OpenAI) with proper mocking, security, and trace guarantees. This is the first Phase 2 runtime execution capability.

---

## SUMMARY

Propose a provider abstraction runtime that allows AXON agents to call model providers through a plugin protocol. This enables actual LLM inference while maintaining strict security boundaries, provider mocking for tests, and comprehensive trace emission.

## PROBLEM / MOTIVATION

AXON agents currently cannot call model providers. The prototype is non-executing and only parses, validates, and generates stubs. To enable real agent execution, we need:

1. **Provider plugin protocol** - A standard interface for provider implementations
2. **Provider calls** - Ability to invoke LLM APIs with prompts and parameters
3. **Mock providers** - Deterministic test doubles for testing without real API calls
4. **Secret handling** - Secure API key management without exposure
5. **Trace emission** - AEL trace events for all provider interactions
6. **Error handling** - Proper Result<T, E> propagation for provider failures

## CURRENT BOUNDARY CHECK

This RFC proposes to change the execution boundary from `docs/RUNTIME_BOUNDARY.md`:

- [ ] **This RFC enables provider calls** - This is the primary change
- [x] Do not execute AXON agent bodies - Provider calls are controlled, not arbitrary execution
- [x] Do not dispatch `act` calls to real tools - Tool dispatch remains disabled (separate RFC)
- [x] Do not resolve, print, or snapshot API keys - Secrets remain redacted
- [x] Keep FastMCP and provider SDKs outside the compiler-core dependency boundary - Provider SDKs are runtime plugins
- [x] Define deterministic test doubles before adding live provider or tool behavior - Mock providers defined
- [x] Document exactly which AXON syntax subset the runtime will execute - Only provider references in model declarations
- [x] State trace emission guarantees before runtime actions are implemented - AEL events defined

This RFC **changes** the execution boundary by enabling provider calls, which is the first Phase 2 runtime capability.

## PROPOSED RUNTIME SCOPE

Add a provider abstraction runtime that:

1. **Provider plugin protocol** - Standard interface for provider implementations
2. **Provider registry** - Register and discover provider plugins
3. **Provider client** - Invoke providers with prompts, parameters, and streaming
4. **Mock providers** - Deterministic test providers for testing
5. **Secret management** - Secure API key loading from environment/config
6. **Trace emission** - AEL trace events for all provider calls
7. **Error handling** - Convert provider errors to Result<T, E>

The provider runtime will:
- Be invoked via `axon run <source.ax>` CLI command
- Load provider plugins from `axon.toml` configuration
- Support streaming and non-streaming provider calls
- Emit AEL trace events for observability
- Support mock providers for testing
- Never print or log API keys

## NON-GOALS

- Do not implement tool dispatch (separate RFC #004)
- Do not implement memory mutation (separate RFC #005)
- Do not implement RAG indexing/retrieval (separate RFC #006)
- Do not implement flow execution (separate RFC #007)
- Do not implement trace replay (separate RFC #008)
- Do not add provider-specific features beyond standard protocol
- Do not implement provider-side prompt caching or optimization

## AXON SYNTAX EXECUTED

This RFC enables execution of provider references in model declarations:

```axon
agent ResearchAgent {
    model: @anthropic/claude-4
    tools: [Search]
    
    fn run(query: Str) -> Result<Str, Error> {
        let response = act Search(query: query)?
        Ok(response.summary)
    }
}
```

The `@anthropic/claude-4` reference will be resolved to a provider plugin and invoked during agent execution.

## PROVIDER PLUGIN IMPACT

**Plugin Protocol:**

```python
class ProviderPlugin(Protocol):
    """Standard interface for provider plugins."""
    
    def name(self) -> str:
        """Provider name (e.g., 'anthropic', 'openai')."""
    
    def call(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float = 0.7,
        stream: bool = False,
    ) -> Result[str, ProviderError]:
        """Invoke the provider with a prompt."""
    
    def call_stream(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float = 0.7,
    ) -> Iterator[Result[str, ProviderError]]:
        """Invoke the provider with streaming."""
```

**Mock Provider:**

```python
class MockProviderPlugin:
    """Deterministic mock provider for testing."""
    
    def __init__(self, responses: dict[str, str]):
        self.responses = responses
    
    def call(self, prompt: str, model: str, ...) -> Result[str, ProviderError]:
        key = f"{model}:{prompt[:100]}"
        if key in self.responses:
            return Ok(self.responses[key])
        return Ok("Mock response for testing")
```

**Timeout Behavior:**
- Default timeout: 120 seconds
- Configurable via `axon.toml`
- Timeout errors return `Err(ProviderError.Timeout)`

**Cost Tracking:**
- Optional cost estimation per provider
- Emitted as trace metadata
- Not enforced (observability only)

**Redaction Rules:**
- API keys never printed or logged
- Provider responses may contain secrets - redaction is caller's responsibility
- Trace events contain request metadata but not full prompts with secrets

## TOOL DISPATCH IMPACT

**None** - Tool dispatch remains disabled in this RFC and will be addressed in RFC #004.

## MEMORY / RAG / FLOW IMPACT

**None** - Memory, RAG, and flow subsystems are not involved in provider calls.

## TRACE AND OBSERVABILITY GUARANTEES

**AEL Trace Events:**

```python
class ProviderCallEvent(TraceEvent):
    """Trace event for provider call."""
    event_type: str = "provider_call"
    provider: str  # e.g., "anthropic"
    model: str  # e.g., "claude-4"
    prompt_hash: str  # SHA256 of prompt for deduplication
    prompt_length: int  # Character count
    max_tokens: int
    temperature: float
    stream: bool
    duration_ms: int
    status: str  # "success" | "error" | "timeout"
    error_message: Optional[str]
    tokens_used: Optional[int]  # If available from provider
    cost_estimate: Optional[float]  # If available
```

**Required Fields:**
- provider, model, prompt_hash, prompt_length, duration_ms, status

**Ordering Guarantees:**
- Provider call events are emitted in order of execution
- Streaming events are emitted as chunks arrive
- Events are written to trace log before provider call completes

**Replay Boundaries:**
- Provider calls are not replayable (requires real provider or mock)
- Trace logs contain enough metadata to identify calls but not reproduce them
- Mock providers enable deterministic replay in tests

**Intentionally Not Recorded:**
- Full prompt text (may contain secrets)
- Full response text (may contain secrets)
- API keys or authentication tokens
- Provider-specific metadata not in standard protocol

## SECURITY AND SECRET HANDLING

**API Key Management:**
- API keys loaded from environment variables only (e.g., `ANTHROPIC_API_KEY`)
- Never stored in `.ax` files
- Never printed or logged
- Redacted from trace events
- Provider plugins receive keys via secure parameter

**Network Access:**
- Provider plugins make HTTPS calls to provider APIs
- No other network access
- Configurable proxy support via environment variables

**File Access:**
- Provider plugins may read provider-specific config files
- No arbitrary file access
- Config files must be in project directory or standard locations

**Provider Responses:**
- Responses may contain sensitive data
- Redaction is caller's responsibility
- Trace events contain metadata only, not full responses

## TESTING STRATEGY

- [x] Unit tests for provider plugin protocol
- [x] Unit tests for provider registry
- [x] Unit tests for mock provider
- [x] Integration tests with real provider (optional, requires API key)
- [x] Provider calls mocked by default in tests
- [x] Secret redaction tests
- [x] Trace emission tests
- [x] Failure-path tests for provider errors
- [x] Timeout tests
- [x] No accidental network calls in compiler-core tests
- [x] Docs updated with provider runtime boundary

## ROLLBACK PLAN

Provider runtime can be disabled by:
1. Removing the `axon run` CLI command
2. Keeping provider plugin code but not invoking it
3. Existing parser, validator, codegen, formatter workflows remain unchanged
4. Type checking remains available (RFC #002)

The rollback is safe because provider runtime is a new command and doesn't modify existing behavior.

## ACCEPTANCE CRITERIA

- [x] Runtime boundary documentation updated to include provider calls
- [x] Provider runtime is behind explicit CLI entrypoint (`axon run`)
- [x] Provider calls are mocked by default in tests
- [x] No secrets are printed, snapshotted, or included in traces
- [x] Existing non-runtime commands remain non-executing
- [x] Relevant docs and CLI help are updated
- [x] Provider plugin protocol is documented
- [x] Mock provider is implemented and tested
- [x] AEL trace events are emitted for all provider calls
- [x] All tests pass including integration tests
- [x] Implementation complete: `src/axon/provider_plugin.py`, `src/axon/provider_registry.py`, `src/axon/providers/`
- [x] Runtime executor integrates provider calls

## OPEN QUESTIONS

- Should provider plugins be distributed via PyPI or bundled with AXON? (Recommendation: PyPI for separation of concerns)
- Should we support async provider calls? (Recommendation: Yes, for streaming support)
- Should we implement provider-side prompt caching? (Recommendation: Defer to future RFC)
- Should we enforce cost limits? (Recommendation: Observability only, defer enforcement to future RFC)
- Which future RFC should handle tool dispatch? (Recommendation: RFC #004)

## IMPLEMENTATION PLAN

1. **Provider plugin protocol** (`src/axon/provider_plugin.py`)
   - Define ProviderPlugin protocol
   - Define ProviderError types
   - Define ProviderConfig dataclass

2. **Provider registry** (`src/axon/provider_registry.py`)
   - Register provider plugins
   - Discover provider plugins from configuration
   - Resolve provider references (e.g., `@anthropic/claude-4`)

3. **Mock provider** (`src/axon/providers/mock_provider.py`)
   - Implement deterministic mock provider
   - Support configurable responses
   - Support streaming simulation

4. **Anthropic provider** (`src/axon/providers/anthropic_provider.py`)
   - Optional: Implement Anthropic provider plugin
   - Use Anthropic SDK (runtime dependency only)
   - Support streaming

5. **OpenAI provider** (`src/axon/providers/openai_provider.py`)
   - Optional: Implement OpenAI provider plugin
   - Use OpenAI SDK (runtime dependency only)
   - Support streaming

6. **Runtime executor** (`src/axon/runtime.py`)
   - Implement `axon run` command
   - Load provider configuration
   - Execute agent methods with provider calls
   - Handle errors and emit traces

7. **CLI integration** (`src/axon/cli.py`)
   - Add `run` command
   - Add `--mock-provider` flag for testing
   - Add `--provider-config` flag

8. **Trace emission** (`src/axon/trace_emitter.py`)
   - Emit AEL provider call events
   - Handle streaming events
   - Write to trace log

9. **Testing** (`tests/test_provider_runtime.py`)
   - Unit tests for provider protocol
   - Unit tests for provider registry
   - Integration tests with mock provider
   - Optional: Integration tests with real provider (requires API key)

10. **Documentation**
    - Update `docs/RUNTIME_BOUNDARY.md` to include provider calls
    - Add provider plugin documentation to `docs/`
    - Update CLI reference
    - Add provider configuration guide

## REFERENCES

- Runtime boundary: `docs/RUNTIME_BOUNDARY.md`
- Runtime RFC #001: `docs/runtime-rfcs/0001-minimal-non-executing-runtime.md`
- Runtime RFC #002: `docs/runtime-rfcs/002-expression-type-checking.md`
- AEL trace format: `docs/TRACE_FORMAT.md`
- Provider configuration: `docs/PROVIDER_CONFIG.md`
