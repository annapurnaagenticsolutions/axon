"""Tests for AXON permission-based security sandboxing."""

from axon.ast_nodes import Annotation, Param, ToolDecl
from axon.permission import (
    Permission,
    PermissionChecker,
    extract_permissions,
    build_permission_checker,
)


def _make_tool(name: str, annotations=None) -> ToolDecl:
    return ToolDecl(
        name=name,
        params=[],
        return_type="Str",
        docstrings=[],
        body='"hello"',
        annotations=annotations or [],
        line=0,
    )


def test_permission_from_annotation():
    ann = Annotation(name="permission", args={"scope": "fs", "access": "read"})
    perm = Permission.from_annotation(ann)
    assert perm.scope == "fs"
    assert perm.access == "read"
    assert str(perm) == "fs:read"


def test_permission_checker_grant_explicit():
    checker = PermissionChecker(granted={"fs:read"})
    assert checker.is_granted("fs", "read")
    assert not checker.is_granted("fs", "write")
    assert not checker.is_granted("network", "read")


def test_permission_checker_wildcard_access():
    checker = PermissionChecker(granted={"fs:*"})
    assert checker.is_granted("fs", "read")
    assert checker.is_granted("fs", "write")
    assert not checker.is_granted("network", "read")


def test_permission_checker_grant_method():
    checker = PermissionChecker()
    checker.grant("network", "read")
    assert checker.is_granted("network", "read")
    assert not checker.is_granted("network", "write")


def test_check_tool_allowed():
    tool = _make_tool("ReadFile", [
        Annotation(name="permission", args={"scope": "fs", "access": "read"})
    ])
    checker = PermissionChecker(granted={"fs:read"})
    allowed, denied = checker.check_tool(tool)
    assert allowed
    assert denied is None


def test_check_tool_denied():
    tool = _make_tool("WriteFile", [
        Annotation(name="permission", args={"scope": "fs", "access": "write"})
    ])
    checker = PermissionChecker(granted={"fs:read"})
    allowed, denied = checker.check_tool(tool)
    assert not allowed
    assert denied == "fs:write"


def test_check_tool_no_permissions():
    tool = _make_tool("SimpleTool")
    checker = PermissionChecker(granted=set())
    allowed, denied = checker.check_tool(tool)
    assert allowed
    assert denied is None


def test_check_tool_multiple_permissions():
    tool = _make_tool("NetFs", [
        Annotation(name="permission", args={"scope": "network", "access": "read"}),
        Annotation(name="permission", args={"scope": "fs", "access": "write"}),
    ])
    checker = PermissionChecker(granted={"network:read", "fs:read"})
    allowed, denied = checker.check_tool(tool)
    assert not allowed
    assert denied == "fs:write"


def test_check_tool_wildcard_grant():
    tool = _make_tool("NetTool", [
        Annotation(name="permission", args={"scope": "network", "access": "read"}),
        Annotation(name="permission", args={"scope": "network", "access": "write"}),
    ])
    checker = PermissionChecker(granted={"network:*"})
    allowed, denied = checker.check_tool(tool)
    assert allowed
    assert denied is None


def test_extract_permissions():
    tools = [
        _make_tool("ToolA", [
            Annotation(name="permission", args={"scope": "fs", "access": "read"})
        ]),
        _make_tool("ToolB", [
            Annotation(name="permission", args={"scope": "network", "access": "write"})
        ]),
        _make_tool("ToolC"),
    ]
    perms = extract_permissions(tools)
    assert "ToolA" in perms
    assert perms["ToolA"][0].scope == "fs"
    assert "ToolB" in perms
    assert "ToolC" not in perms


def test_filter_tools():
    tools = [
        _make_tool("Allowed", [
            Annotation(name="permission", args={"scope": "fs", "access": "read"})
        ]),
        _make_tool("Denied", [
            Annotation(name="permission", args={"scope": "fs", "access": "write"})
        ]),
    ]
    checker = PermissionChecker(granted={"fs:read"})
    filtered = checker.filter_tools(tools)
    names = [t.name for t in filtered]
    assert "Allowed" in names
    assert "Denied" not in names
