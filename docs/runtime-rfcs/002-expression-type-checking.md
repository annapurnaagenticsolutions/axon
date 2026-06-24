# AXON Runtime RFC #002 — Expression Type Checking

**Status:** Accepted
**Created:** 2026-06-03
**Accepted:** 2026-06-03
**Owner:** AXON Maintainers

> This RFC proposes static type checking for AXON expressions using the expression AST. It remains non-executing: no method bodies run, no providers are called, no tools are dispatched, no memory is mutated, no RAG data is indexed or retrieved, no flows are executed, no traces are replayed, no secrets are resolved, and FastMCP is not imported by compiler core.

---

## SUMMARY

Propose a static type checking system for AXON expressions that uses the expression AST to infer and validate types without executing code. This enables early error detection, improved IDE support, and better documentation while maintaining strict adherence to the runtime boundary.

## PROBLEM / MOTIVATION

The expression parser (RFC foundation work) provides AST nodes for expressions but no type checking. Currently:
- Type errors are only detected at runtime (if at all)
- IDEs cannot provide type-aware autocomplete
- Documentation cannot show expected types
- Static analysis tools cannot verify type safety

Type checking is a foundational compiler feature that should be available before runtime execution to ensure safety and improve developer experience.

## CURRENT BOUNDARY CHECK

This RFC confirms strict adherence to the current non-executing boundary from `docs/RUNTIME_BOUNDARY.md`:

- [x] Do not execute AXON agent bodies - type checking is static analysis only
- [x] Do not call model providers from compiler-core modules - no provider calls
- [x] Do not dispatch `act` calls to real tools - no tool dispatch
- [x] Do not resolve, print, or snapshot API keys or other secrets - no secret handling
- [x] Keep FastMCP and provider SDKs outside the compiler-core dependency boundary - no runtime imports
- [x] Define deterministic test doubles before adding live provider or tool behavior - not applicable (no execution)
- [x] Document exactly which AXON syntax subset the runtime will execute - N/A (static analysis only)
- [x] State trace emission guarantees before runtime actions are implemented - N/A (no runtime actions)

This RFC proposes **no changes** to the execution boundary. It adds only static type checking that operates on parsed AST nodes without execution.

## PROPOSED RUNTIME SCOPE

Add a type checking subsystem that:

1. **Infers types** from expression AST nodes using standard type inference rules
2. **Validates types** against declared parameter and return types
3. **Reports type errors** as diagnostics with line numbers and suggestions
4. **Supports type annotations** in the form of type hints in expressions
5. **Integrates with validator** to run type checking as part of validation

The type checker will:
- Operate on the expression AST produced by `parse_expression()`
- Use the existing `Type` system from `src/axon/types.py`
- Report errors through the existing diagnostic system
- Be invoked via `axon check-types <source.ax>` CLI command
- Be optional (can be disabled for backward compatibility)

## NON-GOALS

- Do not implement runtime type checking or dynamic type enforcement
- Do not execute expressions to determine types
- Do not add type inference that requires runtime values
- Do not implement dependent types or advanced type system features
- Do not change the AXON language syntax
- Do not require type annotations (types are inferred where possible)
- Do not implement generic type specialization beyond current `Type` system

## AXON SYNTAX EXECUTED

**None** - this RFC does not execute any AXON syntax. It operates on parsed AST nodes only.

The type checker will analyze expressions like:

```axon
tool Search(query: Str) -> SearchResult
agent ResearchAgent {
    model: @anthropic/claude-haiku
    tools: [Search]
    
    fn run(query: Str) -> Result<Str, Error> {
        let results = Search(query: query)?
        // Type checker infers: results is SearchResult
        // Type checker validates: query parameter matches Str
        Ok(results.summary)
    }
}
```

But will not execute the `Search` call or the `run` method.

## PROVIDER PLUGIN IMPACT

**None** - no provider calls are made during type checking.

## TOOL DISPATCH IMPACT

**None** - no tools are dispatched during type checking.

## MEMORY / RAG / FLOW IMPACT

**None** - memory, RAG, and flow subsystems are not involved in type checking.

## TRACE AND OBSERVABILITY GUARANTEES

**None** - no traces are emitted during type checking. Type errors are reported as diagnostics, not trace events.

## SECURITY AND SECRET HANDLING

No security impact - type checking operates on parsed AST nodes only and does not:
- Access API keys or secrets
- Make network calls
- Read or write files beyond source files
- Execute code

## TESTING STRATEGY

- [x] Unit tests for type inference rules (literal types, variable types, operator types)
- [x] Unit tests for type validation (parameter types, return types)
- [x] Integration tests with existing validator
- [x] Golden snapshot tests for type error diagnostics
- [x] Tests for type checking with expression parser enabled
- [x] Tests for type checking with expression parser disabled (backward compatibility)
- [x] No accidental network calls in type checker tests
- [x] Docs updated with type checking CLI command

## ROLLBACK PLAN

Type checking can be disabled by:
1. Removing the `--check-types` flag from validator
2. Removing the `axon check-types` CLI command
3. Keeping the type checker module but not invoking it
4. Existing parser, validator, codegen, formatter workflows remain unchanged

The rollback is safe because type checking is optional and does not modify any existing behavior.

## ACCEPTANCE CRITERIA

- [x] Runtime boundary documentation updated to include type checking as allowed static analysis
- [x] Type checker is behind explicit CLI entrypoints (`axon check-types`)
- [x] Type checking is optional and can be disabled
- [x] No secrets are printed, snapshotted, or included in diagnostics
- [x] Existing non-runtime commands remain non-executing
- [x] Relevant docs and CLI help are updated
- [x] Type checker integrates with existing validator
- [x] Type error diagnostics follow existing diagnostic format
- [x] All tests pass including golden snapshot tests

## OPEN QUESTIONS

- Should type checking be enabled by default or opt-in? (Recommendation: opt-in initially)
- Should type annotations be required for function parameters? (Recommendation: no, infer where possible)
- Should type checking support generic type parameters? (Recommendation: defer to future RFC)
- Should type checking support union types and option types? (Recommendation: yes, using existing Type system)
- Which future RFC should handle runtime type enforcement? (Recommendation: RFC #003 or later)

## IMPLEMENTATION PLAN

1. **Type inference engine** (`src/axon/type_checker.py`)
   - Implement type inference for literals, variables, operators
   - Implement type inference for function calls and member access
   - Handle Result<T, E> and Option<T> types

2. **Type validation** (`src/axon/type_checker.py`)
   - Validate parameter types against inferred argument types
   - Validate return types against inferred expression types
   - Report type errors as diagnostics

3. **CLI integration** (`src/axon/cli.py`)
   - Add `check-types` command
   - Add `--check-types` flag to existing commands

4. **Validator integration** (`src/axon/validator.py`)
   - Add type checking as optional validation step
   - Report type errors alongside other validation errors

5. **Testing** (`tests/test_type_checker.py`)
   - Unit tests for type inference
   - Unit tests for type validation
   - Integration tests with validator
   - Golden snapshot tests for type errors

6. **Documentation**
   - Update `docs/RUNTIME_BOUNDARY.md` to include type checking
   - Add type checking documentation to `docs/`
   - Update CLI reference

## REFERENCES

- Expression AST: `src/axon/expression_ast.py`
- Expression parser: `src/axon/expression_parser.py`
- Type system: `src/axon/types.py`
- Runtime boundary: `docs/RUNTIME_BOUNDARY.md`
- Runtime RFC #001: `docs/runtime-rfcs/0001-minimal-non-executing-runtime.md`
