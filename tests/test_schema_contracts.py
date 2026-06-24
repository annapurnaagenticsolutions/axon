"""Tests for AXON runtime schema contracts (type validation)."""

from result import Ok, Err

from axon.type_checker import validate_runtime_type, parse_type, TypeKind
from axon.tool_registry import MockToolRegistry
from axon.ast_nodes import ToolDecl, Param
from axon.tool_registry_errors import ToolErrorKind


# -- validate_runtime_type unit tests -----------------------------

def test_validate_str_ok():
    assert validate_runtime_type("hello", "Str") is None


def test_validate_str_fail():
    assert validate_runtime_type(42, "Str") == "expected Str, got int"


def test_validate_int_ok():
    assert validate_runtime_type(42, "Int") is None


def test_validate_int_fail():
    assert validate_runtime_type("42", "Int") == "expected Int, got str"


def test_validate_bool_ok():
    assert validate_runtime_type(True, "Bool") is None


def test_validate_float_ok():
    assert validate_runtime_type(3.14, "Float") is None


def test_validate_any_permissive():
    assert validate_runtime_type([1, 2, 3], "Any") is None
    assert validate_runtime_type("hello", "Any") is None
    assert validate_runtime_type(None, "Any") is None


def test_validate_list_str_ok():
    assert validate_runtime_type(["a", "b"], "List<Str>") is None


def test_validate_list_str_fail():
    err = validate_runtime_type(["a", 1], "List<Str>")
    assert err is not None
    assert "List element 1" in err


def test_validate_list_int_ok():
    assert validate_runtime_type([1, 2, 3], "List<Int>") is None


def test_validate_option_none():
    assert validate_runtime_type(None, "Option<Str>") is None


def test_validate_option_some_ok():
    assert validate_runtime_type("hello", "Option<Str>") is None


def test_validate_option_some_fail():
    assert validate_runtime_type(42, "Option<Str>") == "expected Str, got int"


def test_validate_dict_ok():
    assert validate_runtime_type({"a": 1, "b": 2}, "Dict<Str, Int>") is None


def test_validate_dict_fail_key():
    err = validate_runtime_type({1: "a"}, "Dict<Str, Int>")
    assert err is not None
    assert "Map key" in err


def test_validate_dict_fail_value():
    err = validate_runtime_type({"a": "b"}, "Dict<Str, Int>")
    assert err is not None
    assert "Map value" in err


def test_validate_result_permissive():
    assert validate_runtime_type({"ok": "hello"}, "Result<Str, Error>") is None
    assert validate_runtime_type("plain", "Result<Str, Error>") is None


# -- MockToolRegistry dispatch type validation --------------------

def test_tool_dispatch_type_ok():
    registry = MockToolRegistry()
    tool = ToolDecl(
        name="Greet",
        params=[Param(name="name", type_str="Str")],
        return_type="Str",
        docstrings=[],
        body='"Hello"',
    )
    registry.register(tool)
    res = registry.dispatch("Greet", {"name": "Alice"})
    assert isinstance(res, Ok)


def test_tool_dispatch_type_mismatch():
    registry = MockToolRegistry()
    tool = ToolDecl(
        name="Greet",
        params=[Param(name="name", type_str="Str")],
        return_type="Str",
        docstrings=[],
        body='"Hello"',
    )
    registry.register(tool)
    res = registry.dispatch("Greet", {"name": 42})
    assert isinstance(res, Err)
    assert res.err_value.kind == ToolErrorKind.TYPE_MISMATCH
    assert "expected Str" in res.err_value.message


def test_tool_dispatch_list_type_ok():
    registry = MockToolRegistry()
    tool = ToolDecl(
        name="Sum",
        params=[Param(name="nums", type_str="List<Int>")],
        return_type="Int",
        docstrings=[],
        body="0",
    )
    registry.register(tool)
    res = registry.dispatch("Sum", {"nums": [1, 2, 3]})
    assert isinstance(res, Ok)


def test_tool_dispatch_list_type_fail():
    registry = MockToolRegistry()
    tool = ToolDecl(
        name="Sum",
        params=[Param(name="nums", type_str="List<Int>")],
        return_type="Int",
        docstrings=[],
        body="0",
    )
    registry.register(tool)
    res = registry.dispatch("Sum", {"nums": [1, "two", 3]})
    assert isinstance(res, Err)
    assert res.err_value.kind == ToolErrorKind.TYPE_MISMATCH


def test_tool_dispatch_option_type_ok():
    registry = MockToolRegistry()
    tool = ToolDecl(
        name="MaybeGreet",
        params=[Param(name="name", type_str="Option<Str>")],
        return_type="Str",
        docstrings=[],
        body='"Hello"',
    )
    registry.register(tool)
    # None is valid for Option
    res = registry.dispatch("MaybeGreet", {"name": None})
    assert isinstance(res, Ok)
    # Str is also valid for Option<Str>
    res = registry.dispatch("MaybeGreet", {"name": "Alice"})
    assert isinstance(res, Ok)


def test_tool_dispatch_option_type_fail():
    registry = MockToolRegistry()
    tool = ToolDecl(
        name="MaybeGreet",
        params=[Param(name="name", type_str="Option<Str>")],
        return_type="Str",
        docstrings=[],
        body='"Hello"',
    )
    registry.register(tool)
    res = registry.dispatch("MaybeGreet", {"name": 42})
    assert isinstance(res, Err)
    assert res.err_value.kind == ToolErrorKind.TYPE_MISMATCH
