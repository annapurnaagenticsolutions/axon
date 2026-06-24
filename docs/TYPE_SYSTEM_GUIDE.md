# AXON Type System Guide

The AXON type system provides static type checking for declarations and expressions.

## Primitive Types

| Type | Description | Examples |
|------|-------------|----------|
| `Str` | Strings | `"hello"` |
| `Int` | Integers | `42` |
| `Float` | Floating point | `3.14` |
| `Bool` | Booleans | `true`, `false` |
| `Any` | Top type | Any value |
| `Bytes` | Byte arrays | — |
| `()` | Unit type | `()` |

## Generic Types

| Type | Description |
|------|-------------|
| `List<T>` | Ordered collection |
| `Map<K, V>` | Key-value mapping |
| `Set<T>` | Unique collection |
| `Tuple<A, B>` | Fixed-size pair |
| `Vec<T>` | Vector (alias for List) |
| `Dict<K, V>` | Dictionary (alias for Map) |

## Special Types

| Type | Description |
|------|-------------|
| `Option<T>` | Optional value (`Some` or `None`) |
| `Result<T, E>` | Success or error |
| `Stream<T>` | Streaming output |

## Union Types

Union types allow a value to be one of several types:

```axon
type Priority = "low" | "medium" | "high"
type Value = Str | Int | Float
```

Union types support:
- **Subtyping**: `Str <: Str | Int` (Str is subtype of Str | Int)
- **Narrowing**: `Int | Float <: Float` (since Int <: Float)

## Record Types

Record types define structured data:

```axon
type Issue = {
    id: Int,
    title: Str,
    priority: Priority,
    tags: List<Str>
}
```

## Type Aliases

Create reusable type names:

```axon
type IssueId = Int
type TagList = List<Str>
```

## Expression Type Inference

The type checker infers expression types:

```axon
let x = 42       // x: Int
let y = 3.14     // y: Float
let z = x + y    // z: Float (Int widens to Float)
let b = true     // b: Bool
let s = "hello"  // s: Str
```

### List Literals

```axon
let nums = [1, 2, 3]     // nums: List<Int>
let strs = ["a", "b"]    // strs: List<Str>
```

### Map Literals

```axon
let scores = {"alice": 100, "bob": 200}  // scores: Map<Str, Int>
```

### Option Constructors

```axon
let some_val = Some(42)   // some_val: Option<Int>
let none_val = None       // none_val: Option<Any>
```

### Result Constructors

```axon
let ok_val = Ok("hello")       // ok_val: Result<Str, Any>
let err_val = Error("fail")    // err_val: Result<Any, Str>
```

## Subtyping Rules

1. **Any is top**: `T <: Any` for all T
2. **Numeric widening**: `Int <: Float`
3. **Option lifting**: `T <: Option<T>`
4. **Union membership**: `T <: T | U`
5. **Union narrowing**: `T | U <: V` if `T <: V` and `U <: V`
6. **Generic covariance**: `List<Int> <: List<Any>` if `Int <: Any`
7. **Result covariance**: `Result<Int, E> <: Result<Any, E>`

## Type Checking Errors

Common type errors:

- Return type mismatch
- Argument type mismatch in function calls
- Missing required parameters
- Unknown type references
- Record field access on non-record types

## CLI Commands

```bash
# Type check a file
axon type-check my_agent.ax

# Validate with type checking
axon validate my_agent.ax --enable-type-check
```

## Runtime Type Validation

The runtime validates types during execution:

```python
from axon.type_checker import validate_runtime_type

result = validate_runtime_type(value, expected_type)
```
