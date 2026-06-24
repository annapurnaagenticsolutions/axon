# Expression Parser

The expression parser is a Phase 2 feature for AXON that enables static analysis of method bodies by parsing them into structured AST nodes. This is a foundational step for future runtime planning and static analysis enhancements, while maintaining strict adherence to the runtime boundary (no actual execution of AXON code).

## Overview

The expression parser (`src/axon/expression_parser.py`) implements a recursive descent parser that converts AXON method body text into a structured Abstract Syntax Tree (AST). This enables:

- **Static analysis**: Analyze method bodies without executing them
- **Type checking**: Verify expression types before runtime
- **Code navigation**: Enable LSP features for expressions
- **Future runtime planning**: Prepare for eventual runtime execution (requires RFC approval)

## Expression AST Nodes

All expression nodes are defined in `src/axon/expression_ast.py` and inherit from the base `Expr` class:

### Literal Expressions
- `LiteralExpr`: Strings, numbers, booleans
- `NoneExpr`: The `None` value

### Variable and Access Expressions
- `VariableExpr`: Variable references
- `MemberAccessExpr`: Field/method access (e.g., `obj.field`)
- `IndexExpr`: Index operations (e.g., `array[index]`)

### Operator Expressions
- `BinaryOpExpr`: Binary operations (`+`, `-`, `*`, `/`, `==`, `!=`, `<`, `>`, `<=`, `>=`, `&&`, `||`)
- `UnaryOpExpr`: Unary operations (`-`, `!`, `not`)

### Control Flow Expressions
- `IfExpr`: Conditional expressions
- `MatchExpr`: Pattern matching
- `BlockExpr`: Block of expressions
- `LetExpr`: Variable bindings
- `ReturnExpr`: Return statements

### Collection Expressions
- `ListExpr`: List literals (`[1, 2, 3]`)
- `MapExpr`: Map literals (`{key: value}`)

### Result Type Expressions
- `OkExpr`: Ok constructor (`Ok(expr)`)
- `ErrorExpr`: Error constructor (`Err(expr)`)
- `SomeExpr`: Some constructor (`Some(expr)`)

### Other Expressions
- `CallExpr`: Function/method calls
- `StringInterpolationExpr`: String interpolation (`"Hello, {name}!"`)

## Usage

### Basic Parsing

```python
from axon.expression_parser import parse_expression

# Parse a simple expression
expr = parse_expression("1 + 2")
# Returns: BinaryOpExpr(op="+", left=LiteralExpr(value=1), right=LiteralExpr(value=2))

# Parse a function call
expr = parse_expression("foo(1, 2)")
# Returns: CallExpr(callee=VariableExpr(name="foo"), args=[LiteralExpr(value=1), LiteralExpr(value=2)])
```

### Integration with Main Parser

The expression parser can be integrated with the main AXON parser to parse method bodies:

```python
from axon.parser import parse

# Parse with expression parsing enabled
decls = parse(source, parse_expressions=True)

# ToolDecl, MethodDecl, and FlowDecl will now have parsed_body field
for decl in decls:
    if hasattr(decl, 'parsed_body') and decl.parsed_body:
        print(f"Parsed body for {decl.name}: {decl.parsed_body}")
```

## Operator Precedence

The parser follows standard operator precedence (from highest to lowest):

1. Parentheses `()`
2. Member access `.`, index `[]`
3. Unary operators `-`, `!`, `not`
4. Multiplicative `*`, `/`
5. Additive `+`, `-`
6. Comparison `<`, `>`, `<=`, `>=`
7. Equality `==`, `!=`
8. Logical AND `&&`
9. Logical OR `||`

## Limitations

The expression parser is designed for static analysis and has the following limitations:

- **No execution**: Expressions are parsed but not evaluated
- **No type checking**: The parser builds AST nodes but doesn't verify types
- **Limited error recovery**: Syntax errors may not provide detailed error messages
- **Keyword handling**: Some keywords like `None` may be parsed as variables in certain contexts

## Runtime Boundary

The expression parser maintains strict adherence to the AXON runtime boundary:

- **No actual execution**: Expressions are parsed but never executed
- **No provider calls**: No external services are called during parsing
- **RFC required**: Any future runtime execution requires formal RFC approval

See `docs/RUNTIME_BOUNDARY.md` for more details on the runtime boundary.

## Testing

Expression parser tests are in `tests/test_expression_parser.py`:

```bash
python -m pytest tests/test_expression_parser.py -v
```

All 24 tests currently pass, covering:
- Literals (numbers, strings, booleans, None)
- Variables
- Binary operations
- Unary operations
- Function calls
- Member access
- Index operations
- List and map literals
- Result type constructors (Ok, Err, Some)
- Complex expressions with operator precedence

## Future Enhancements

Potential future improvements (require RFC approval):

- **Type checking**: Add type inference and verification
- **Error recovery**: Improve error messages and recovery
- **Pattern matching**: Full support for match expressions
- **String interpolation**: Complete interpolation parsing
- **Execution**: Runtime evaluation of expressions (requires RFC)
