"""Tests for AXON type checker."""

from axon.parser import parse
from axon.type_checker import (
    Type,
    TypeKind,
    PrimitiveType,
    GenericType,
    parse_type,
    types_equal,
    is_subtype,
    check_types,
    TypeChecker,
)
from axon.expression_ast import (
    ActExpr,
    AssignExpr,
    BlockExpr,
    CallExpr,
    DelegateExpr,
    ErrorExpr,
    ForExpr,
    LetExpr,
    LiteralExpr,
    MatchArm,
    MatchExpr,
    TryExpr,
    VariableExpr,
    BinaryOpExpr,
    UnaryOpExpr,
    ListExpr,
    MapExpr,
    OkExpr,
    SomeExpr,
    NoneExpr,
)


def test_parse_primitive_types():
    assert parse_type("Str").name == "Str"
    assert parse_type("Str").kind == TypeKind.PRIMITIVE
    assert parse_type("Int").name == "Int"
    assert parse_type("Float").name == "Float"
    assert parse_type("Bool").name == "Bool"
    assert parse_type("Any").name == "Any"
    assert parse_type("Bytes").name == "Bytes"


def test_parse_unit_type():
    t = parse_type("()")
    assert t.name == "()"
    assert t.kind == TypeKind.PRIMITIVE


def test_parse_generic_list():
    t = parse_type("List<Int>")
    assert t.name == "List"
    assert t.kind == TypeKind.GENERIC
    assert len(t.args) == 1
    assert t.args[0].name == "Int"


def test_parse_generic_map():
    t = parse_type("Map<Str, Int>")
    assert t.name == "Map"
    assert t.kind == TypeKind.GENERIC
    assert len(t.args) == 2
    assert t.args[0].name == "Str"
    assert t.args[1].name == "Int"


def test_parse_nested_generics():
    t = parse_type("List<Map<Str, Int>>")
    assert t.name == "List"
    assert len(t.args) == 1
    assert t.args[0].name == "Map"
    assert len(t.args[0].args) == 2


def test_parse_option():
    t = parse_type("Option<Str>")
    assert t.name == "Option"
    assert t.kind == TypeKind.OPTION
    assert len(t.args) == 1
    assert t.args[0].name == "Str"


def test_parse_result():
    t = parse_type("Result<List<Any>, ToolError>")
    assert t.name == "Result"
    assert t.kind == TypeKind.RESULT
    assert len(t.args) == 2
    assert t.args[0].name == "List"
    assert t.args[1].name == "ToolError"


def test_parse_stream():
    t = parse_type("Stream<Token>")
    assert t.name == "Stream"
    assert t.kind == TypeKind.STREAM
    assert len(t.args) == 1
    assert t.args[0].name == "Token"


def test_parse_union():
    t = parse_type('"low" | "medium" | "high"')
    assert t.name == "Union"
    assert t.kind == TypeKind.UNION
    assert len(t.args) == 3


def test_parse_unknown_type():
    t = parse_type("CustomType")
    assert t.name == "CustomType"
    assert t.kind == TypeKind.UNKNOWN


def test_types_equal_primitives():
    assert types_equal(parse_type("Str"), parse_type("Str"))
    assert types_equal(parse_type("Int"), parse_type("Int"))
    assert not types_equal(parse_type("Str"), parse_type("Int"))


def test_types_equal_generics():
    assert types_equal(parse_type("List<Int>"), parse_type("List<Int>"))
    assert not types_equal(parse_type("List<Int>"), parse_type("List<Str>"))
    assert types_equal(parse_type("Map<Str, Int>"), parse_type("Map<Str, Int>"))


def test_types_equal_nested():
    assert types_equal(parse_type("List<Map<Str, Int>>"), parse_type("List<Map<Str, Int>>"))
    assert not types_equal(parse_type("List<Map<Str, Int>>"), parse_type("List<Map<Str, Str>>"))


def test_is_subtype_any():
    any_type = parse_type("Any")
    assert is_subtype(parse_type("Str"), any_type)
    assert is_subtype(parse_type("Int"), any_type)
    assert is_subtype(parse_type("List<Int>"), any_type)


def test_is_subtype_exact_match():
    assert is_subtype(parse_type("Str"), parse_type("Str"))
    assert not is_subtype(parse_type("Str"), parse_type("Int"))


def test_check_types_simple_tool():
    source = '''
tool Greet(name: Str) -> Str {
    /// Says hello.
    "Hello, {name}!"
}
'''
    decls = parse(source)
    diagnostics = check_types(decls)
    # Should have no errors for valid types
    errors = [d for d in diagnostics if d.severity == "error"]
    assert len(errors) == 0


def test_check_types_tool_with_generic_param():
    source = '''
tool Process(items: List<Int>) -> List<Str> {
    /// Processes items.
    items.map(|x| str(x))
}
'''
    decls = parse(source)
    diagnostics = check_types(decls)
    errors = [d for d in diagnostics if d.severity == "error"]
    assert len(errors) == 0


def test_check_types_tool_with_result():
    source = '''
tool Fetch(url: Str) -> Result<List<Any>, ToolError> {
    /// Fetches data.
    http.get(url)
}
'''
    decls = parse(source)
    diagnostics = check_types(decls)
    errors = [d for d in diagnostics if d.severity == "error"]
    assert len(errors) == 0


def test_check_types_agent_with_method():
    source = '''
agent Bot {
    model: @anthropic/claude-4
    tools: []

    fn run(query: Str) -> Result<Str, AgentError> {
        Ok(query)
    }
}
'''
    decls = parse(source)
    diagnostics = check_types(decls)
    errors = [d for d in diagnostics if d.severity == "error"]
    assert len(errors) == 0


def test_check_types_prompt():
    source = '''
prompt Summarize(text: Str, @budget(tokens: 300)) -> Str {
    """
    Summarize: {text}
    """
}
'''
    decls = parse(source)
    diagnostics = check_types(decls)
    errors = [d for d in diagnostics if d.severity == "error"]
    assert len(errors) == 0


def test_check_types_type_alias():
    source = '''
type IssueId = Int
type Priority = "low" | "medium" | "high"
'''
    decls = parse(source)
    diagnostics = check_types(decls)
    errors = [d for d in diagnostics if d.severity == "error"]
    assert len(errors) == 0


def test_check_types_record_type():
    source = '''
type Issue = {
    id: Int,
    title: Str,
    labels: List<Str>
}
'''
    decls = parse(source)
    diagnostics = check_types(decls)
    errors = [d for d in diagnostics if d.severity == "error"]
    assert len(errors) == 0


def test_check_types_rag():
    source = '''
rag Docs {
    source: "./docs/**/*.md"
    chunker: Chunker::sliding(size: 512, overlap: 64)
    embedder: @openai/text-embed-3
    store: VectorDB::sqlite("./index.db")

    fn retrieve(query: Str, top_k: Int = 5) -> List<Chunk> {
        store.search(embed(query), top_k)
    }
}
'''
    decls = parse(source)
    diagnostics = check_types(decls)
    errors = [d for d in diagnostics if d.severity == "error"]
    assert len(errors) == 0


def test_check_types_flow():
    source = '''
flow Pipeline(input: Str) -> Str {
    stage Process(input: Str) -> Str

    Process -> Process
}
'''
    decls = parse(source)
    diagnostics = check_types(decls)
    errors = [d for d in diagnostics if d.severity == "error"]
    assert len(errors) == 0


def test_check_types_unknown_type_warning():
    source = '''
tool Process(data: UnknownType) -> Str {
    /// Processes data.
    "done"
}
'''
    decls = parse(source)
    diagnostics = check_types(decls)
    # Should warn about unknown type
    warnings = [d for d in diagnostics if d.severity == "warning"]
    assert len(warnings) > 0
    assert any("UnknownType" in d.message for d in warnings)


def test_type_to_string():
    assert str(parse_type("Str")) == "Str"
    assert str(parse_type("List<Int>")) == "List<Int>"
    assert str(parse_type("Map<Str, Int>")) == "Map<Str, Int>"
    assert str(parse_type("Option<Str>")) == "Option<Str>"
    assert str(parse_type("Result<Str, Error>")) == "Result<Str, Error>"
    assert str(parse_type("Stream<Token>")) == "Stream<Token>"


def test_record_type_parsing():
    source = '''
type Issue = {
    id: Int,
    title: Str,
    labels: List<Str>
}
'''
    decls = parse(source)
    diagnostics = check_types(decls)
    errors = [d for d in diagnostics if d.severity == "error"]
    assert len(errors) == 0


def test_record_field_validation():
    source = '''
type Issue = {
    id: Int,
    title: Str
}

tool GetIssue(id: Int) -> Issue {
    /// Gets an issue.
    issue = { id: id, title: "Test" }
    issue.nonexistent_field
}
'''
    decls = parse(source)
    # This test would require expression parsing to validate field access
    # For now, we just check that the type alias is valid
    diagnostics = check_types(decls)
    # Should have no errors for the type alias itself
    type_errors = [d for d in diagnostics if "unknown-type" in d.code]
    assert len(type_errors) == 0


def test_generic_constraint_validation():
    source = '''
type Items = List<Int>

tool Process(items: Items) -> Items {
    /// Processes items.
    items
}
'''
    decls = parse(source)
    diagnostics = check_types(decls)
    errors = [d for d in diagnostics if d.severity == "error"]
    assert len(errors) == 0


def test_expression_type_inference_literal():
    """Test type inference for literal expressions."""
    checker = TypeChecker()
    
    # Integer literal
    int_expr = LiteralExpr(line=1, value=42)
    int_type = checker._infer_literal_type(int_expr)
    assert int_type.name == "Int"
    assert int_type.kind == TypeKind.PRIMITIVE
    
    # String literal
    str_expr = LiteralExpr(line=1, value="hello")
    str_type = checker._infer_literal_type(str_expr)
    assert str_type.name == "Str"
    assert str_type.kind == TypeKind.PRIMITIVE
    
    # Boolean literal
    bool_expr = LiteralExpr(line=1, value=True)
    bool_type = checker._infer_literal_type(bool_expr)
    assert bool_type.name == "Bool"
    assert bool_type.kind == TypeKind.PRIMITIVE
    
    # Float literal
    float_expr = LiteralExpr(line=1, value=3.14)
    float_type = checker._infer_literal_type(float_expr)
    assert float_type.name == "Float"
    assert float_type.kind == TypeKind.PRIMITIVE


def test_expression_type_inference_binary_op():
    """Test type inference for binary operations."""
    checker = TypeChecker()
    
    # Addition of two integers
    add_expr = BinaryOpExpr(
        line=1,
        op="+",
        left=LiteralExpr(line=1, value=1),
        right=LiteralExpr(line=1, value=2)
    )
    add_type = checker._infer_binary_op_type(add_expr, "test")
    assert add_type.name == "Int"
    
    # Comparison operation
    cmp_expr = BinaryOpExpr(
        line=1,
        op="==",
        left=LiteralExpr(line=1, value=1),
        right=LiteralExpr(line=1, value=2)
    )
    cmp_type = checker._infer_binary_op_type(cmp_expr, "test")
    assert cmp_type.name == "Bool"
    
    # Logical operation
    logical_expr = BinaryOpExpr(
        line=1,
        op="&&",
        left=LiteralExpr(line=1, value=True),
        right=LiteralExpr(line=1, value=False)
    )
    logical_type = checker._infer_binary_op_type(logical_expr, "test")
    assert logical_type.name == "Bool"


def test_expression_type_inference_unary_op():
    """Test type inference for unary operations."""
    checker = TypeChecker()
    
    # Negation
    neg_expr = UnaryOpExpr(
        line=1,
        op="-",
        operand=LiteralExpr(line=1, value=42)
    )
    neg_type = checker._infer_unary_op_type(neg_expr, "test")
    assert neg_type.name == "Int"
    
    # Logical not
    not_expr = UnaryOpExpr(
        line=1,
        op="!",
        operand=LiteralExpr(line=1, value=True)
    )
    not_type = checker._infer_unary_op_type(not_expr, "test")
    assert not_type.name == "Bool"


def test_expression_type_inference_list():
    """Test type inference for list literals."""
    checker = TypeChecker()
    
    # Empty list
    empty_list = ListExpr(line=1, elements=[])
    empty_type = checker._infer_list_type(empty_list, "test")
    assert empty_type.name == "List"
    
    # List with integers
    int_list = ListExpr(
        line=1,
        elements=[LiteralExpr(line=1, value=1), LiteralExpr(line=1, value=2)]
    )
    int_list_type = checker._infer_list_type(int_list, "test")
    assert int_list_type.name == "List"
    assert int_list_type.args[0].name == "Int"


def test_expression_type_inference_map():
    """Test type inference for map literals."""
    checker = TypeChecker()
    
    # Empty map
    empty_map = MapExpr(line=1, pairs=[])
    empty_type = checker._infer_map_type(empty_map, "test")
    assert empty_type.name == "Map"
    
    # Map with string keys and int values
    str_int_map = MapExpr(
        line=1,
        pairs=[(LiteralExpr(line=1, value="key"), LiteralExpr(line=1, value=42))]
    )
    str_int_type = checker._infer_map_type(str_int_map, "test")
    assert str_int_type.name == "Map"
    assert str_int_type.args[0].name == "Str"
    assert str_int_type.args[1].name == "Int"


def test_expression_type_inference_ok():
    """Test type inference for Ok constructor."""
    checker = TypeChecker()
    
    ok_expr = OkExpr(
        line=1,
        value=LiteralExpr(line=1, value="success")
    )
    ok_type = checker._infer_ok_type(ok_expr, "test")
    assert ok_type.name == "Result"
    assert ok_type.kind == TypeKind.RESULT
    assert ok_type.args[0].name == "Str"


def test_expression_type_inference_error():
    """Test type inference for Error constructor."""
    checker = TypeChecker()
    
    error_expr = ErrorExpr(
        line=1,
        value=LiteralExpr(line=1, value="failure")
    )
    error_type = checker._infer_error_type(error_expr, "test")
    assert error_type.name == "Result"
    assert error_type.kind == TypeKind.RESULT
    assert error_type.args[1].name == "Str"


def test_expression_type_inference_some():
    """Test type inference for Some constructor."""
    checker = TypeChecker()
    
    some_expr = SomeExpr(
        line=1,
        value=LiteralExpr(line=1, value=42)
    )
    some_type = checker._infer_some_type(some_expr, "test")
    assert some_type.name == "Option"
    assert some_type.kind == TypeKind.OPTION
    assert some_type.args[0].name == "Int"


def test_expression_type_inference_none():
    """Test type inference for None literal."""
    checker = TypeChecker()
    
    none_expr = NoneExpr(line=1)
    none_type = checker._infer_expression_type(none_expr, "test")
    assert none_type.name == "Option"
    assert none_type.kind == TypeKind.OPTION


def test_expression_type_inference_variable():
    """Test type inference for variable expressions."""
    checker = TypeChecker()
    
    # Unknown variable
    var_expr = VariableExpr(line=1, name="x")
    var_type = checker._infer_variable_type(var_expr, "test")
    assert var_type.name == "x"
    assert var_type.kind == TypeKind.UNKNOWN
    
    # Known variable
    checker.variable_types["y"] = PrimitiveType(kind=TypeKind.PRIMITIVE, name="Str")
    known_var = VariableExpr(line=1, name="y")
    known_type = checker._infer_variable_type(known_var, "test")
    assert known_type.name == "Str"


def test_expression_type_inference_let():
    """Test type inference for let expressions."""
    checker = TypeChecker()
    
    let_expr = LetExpr(
        line=1,
        name="x",
        value=LiteralExpr(line=1, value=42),
        body=VariableExpr(line=1, name="x")
    )
    let_type = checker._infer_let_type(let_expr, "test")
    assert let_type.name == "Int"
    assert "x" in checker.variable_types


def test_expression_type_inference_block():
    """Test type inference for block expressions."""
    checker = TypeChecker()
    
    # Empty block
    empty_block = BlockExpr(line=1, statements=[])
    empty_type = checker._infer_block_type(empty_block, "test")
    assert empty_type.name == "()"
    
    # Block with statements
    block = BlockExpr(
        line=1,
        statements=[
            LiteralExpr(line=1, value=1),
            LiteralExpr(line=1, value=2),
            LiteralExpr(line=1, value="last")
        ]
    )
    block_type = checker._infer_block_type(block, "test")
    assert block_type.name == "Str"


def test_check_types_with_expression_parsing():
    """Test type checking with expression parsing enabled."""
    source = '''
agent Bot {
    model: @anthropic/claude-4
    tools: []

    fn run(query: Str) -> Result<Str, Error> {
        42
    }
}
'''
    decls = parse(source, parse_expressions=True)
    diagnostics = check_types(decls)
    errors = [d for d in diagnostics if d.severity == "error"]
    # Should have a type mismatch error (Int vs Result<Str, Error>)
    assert len(errors) > 0


def test_parse_union_type_with_primitives():
    """Test parsing union types with primitive types."""
    t = parse_type("Str | Int")
    assert t.kind == TypeKind.UNION
    assert len(t.args) == 2
    assert t.args[0].name == "Str"
    assert t.args[1].name == "Int"


def test_parse_union_type_with_generics():
    """Test parsing union types with generic types."""
    t = parse_type("List<Int> | List<Str>")
    assert t.kind == TypeKind.UNION
    assert len(t.args) == 2
    assert t.args[0].kind == TypeKind.GENERIC
    assert t.args[1].kind == TypeKind.GENERIC


def test_union_type_to_string():
    """Test union type string representation."""
    t = parse_type("Str | Int | Float")
    assert str(t) == "Str | Int | Float"


def test_is_subtype_union():
    """Test is_subtype with union types."""
    union_type = parse_type("Str | Int")
    assert is_subtype(parse_type("Str"), union_type)
    assert is_subtype(parse_type("Int"), union_type)
    assert not is_subtype(parse_type("Float"), union_type)


def test_is_subtype_union_all_members():
    """Test union subtype where all members are subtypes."""
    # Int | Float <: Float (since Int <: Float and Float <: Float)
    assert is_subtype(parse_type("Int | Float"), parse_type("Float"))


def test_is_subtype_int_to_float():
    """Test numeric widening: Int is subtype of Float."""
    assert is_subtype(parse_type("Int"), parse_type("Float"))
    assert not is_subtype(parse_type("Float"), parse_type("Int"))


def test_is_subtype_option():
    """Test Option<T> supertype of T."""
    assert is_subtype(parse_type("Str"), parse_type("Option<Str>"))
    assert is_subtype(parse_type("Int"), parse_type("Option<Int>"))


def test_is_subtype_result_covariance():
    """Test Result covariance: Result<Int, Error> <: Result<Any, Error>."""
    assert is_subtype(parse_type("Result<Int, Error>"), parse_type("Result<Any, Error>"))


def test_is_subtype_generic_covariance():
    """Test generic covariance: List<Int> <: List<Any>."""
    assert is_subtype(parse_type("List<Int>"), parse_type("List<Any>"))
    assert not is_subtype(parse_type("List<Str>"), parse_type("List<Int>"))


def test_expression_type_inference_act_expr():
    """Test type inference for tool invocation (act)."""
    checker = TypeChecker()
    checker.tool_signatures["Greet"] = PrimitiveType(kind=TypeKind.PRIMITIVE, name="Str")

    act = ActExpr(line=1, tool_name="Greet", args=[("name", LiteralExpr(line=1, value="World"))])
    act_type = checker._infer_act_type(act, "test")
    assert act_type.name == "Str"


def test_expression_type_inference_act_expr_unknown_tool():
    """Test act on unknown tool returns Unknown."""
    checker = TypeChecker()
    act = ActExpr(line=1, tool_name="UnknownTool", args=[])
    act_type = checker._infer_act_type(act, "test")
    assert act_type.kind == TypeKind.UNKNOWN


def test_expression_type_inference_try_expr_result():
    """Test type inference for try operator on Result."""
    checker = TypeChecker()
    try_expr = TryExpr(line=1, operand=OkExpr(line=1, value=LiteralExpr(line=1, value="hello")))
    try_type = checker._infer_try_type(try_expr, "test")
    assert try_type.name == "Str"


def test_expression_type_inference_try_expr_option():
    """Test type inference for try operator on Option."""
    checker = TypeChecker()
    try_expr = TryExpr(line=1, operand=SomeExpr(line=1, value=LiteralExpr(line=1, value=42)))
    try_type = checker._infer_try_type(try_expr, "test")
    assert try_type.name == "Int"


def test_expression_type_inference_assign_expr():
    """Test type inference for assignment (name = value)."""
    checker = TypeChecker()
    assign = AssignExpr(line=1, name="x", value=LiteralExpr(line=1, value=42))
    assign_type = checker._infer_assign_type(assign, "test")
    assert assign_type.name == "Int"
    assert checker.variable_types["x"].name == "Int"


def test_expression_type_inference_for_expr():
    """Test type inference for for-in loop with List."""
    checker = TypeChecker()
    checker.variable_types["items"] = GenericType(kind=TypeKind.GENERIC, name="List", args=[PrimitiveType(kind=TypeKind.PRIMITIVE, name="Str")])
    for_expr = ForExpr(
        line=1,
        var_name="item",
        iterable=VariableExpr(line=1, name="items"),
        body=VariableExpr(line=1, name="item"),
    )
    for_type = checker._infer_for_type(for_expr, "test")
    assert for_type.name == "Str"
    assert checker.variable_types["item"].name == "Str"


def test_expression_type_inference_match_expr():
    """Test type inference for match expression."""
    checker = TypeChecker()
    match_expr = MatchExpr(
        line=1,
        value=VariableExpr(line=1, name="x"),
        arms=[
            MatchArm(pattern=LiteralExpr(line=1, value=1), body=LiteralExpr(line=1, value="one")),
            MatchArm(pattern=LiteralExpr(line=1, value=2), body=LiteralExpr(line=1, value="two")),
        ],
    )
    match_type = checker._infer_match_type(match_expr, "test")
    assert match_type.kind == TypeKind.PRIMITIVE
    assert match_type.name == "Str"


def test_expression_type_inference_call_expr_tool():
    """Test type inference for CallExpr resolving tool signature."""
    checker = TypeChecker()
    checker.tool_signatures["Fetch"] = PrimitiveType(kind=TypeKind.PRIMITIVE, name="Str")
    call = CallExpr(line=1, callee=VariableExpr(line=1, name="Fetch"), args=[LiteralExpr(line=1, value="url")])
    call_type = checker._infer_call_type(call, "test")
    assert call_type.name == "Str"


def test_check_types_parameter_bound_in_body():
    """Test that method parameters are bound and used in body inference."""
    source = '''
agent Bot {
    model: @mock/gpt
    fn run(name: Str) -> Str {
        name
    }
}
'''
    decls = parse(source, parse_expressions=True)
    diagnostics = check_types(decls)
    errors = [d for d in diagnostics if d.severity == "error"]
    assert len(errors) == 0


def test_check_types_parameter_type_mismatch_in_body():
    """Test type mismatch when parameter is used with wrong operation."""
    source = '''
agent Bot {
    model: @mock/gpt
    fn run(count: Int) -> Str {
        count
    }
}
'''
    decls = parse(source, parse_expressions=True)
    diagnostics = check_types(decls)
    errors = [d for d in diagnostics if d.severity == "error"]
    # Int is not subtype of Str — should error
    assert len(errors) > 0
    assert any("return-type-mismatch" in d.code for d in errors)


def test_check_types_tool_act_return_type():
    """Test that act ToolName infers correct return type."""
    source = '''
tool Greet(name: Str) -> Str {
    "Hello, {name}!"
}

agent Bot {
    model: @mock/gpt
    tools: [Greet]
    fn run(name: Str) -> Str {
        act Greet(name: name)
    }
}
'''
    decls = parse(source, parse_expressions=True)
    diagnostics = check_types(decls)
    errors = [d for d in diagnostics if d.severity == "error"]
    # act Greet returns Str which matches run's return type Str
    assert len(errors) == 0


def test_check_types_tool_act_wrong_return_type():
    """Test error when act ToolName return type doesn't match method return type."""
    source = '''
tool GetCount() -> Int {
    42
}

agent Bot {
    model: @mock/gpt
    tools: [GetCount]
    fn run() -> Str {
        act GetCount()
    }
}
'''
    decls = parse(source, parse_expressions=True)
    diagnostics = check_types(decls)
    errors = [d for d in diagnostics if d.severity == "error"]
    # act GetCount returns Int but run expects Str
    assert len(errors) > 0
    assert any("return-type-mismatch" in d.code for d in errors)
