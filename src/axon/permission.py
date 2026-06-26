"""Permission-based security sandboxing for AXON runtime.

Parses @permission annotations from tool declarations and enforces
access control at runtime. Permissions are declared as:

    @permission(scope: "fs", access: "read")
    @permission(scope: "network", access: "write")
    tool FetchUrl { ... }

The PermissionChecker validates tool dispatches against a granted
permission set, blocking unauthorized access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from axon.ast_nodes import Annotation, ToolDecl


@dataclass(frozen=True)
class Permission:
    """A single permission grant or requirement."""

    scope: str        # e.g. "fs", "network", "subprocess", "memory"
    access: str       # e.g. "read", "write", "execute"

    def __str__(self) -> str:
        return f"{self.scope}:{self.access}"

    @classmethod
    def from_annotation(cls, ann: Annotation) -> "Permission":
        scope = ann.args.get("scope", "any")
        access = ann.args.get("access", "any")
        if isinstance(scope, str) and len(scope) >= 2 and scope[0] in '"\'' and scope[-1] == scope[0]:
            scope = scope[1:-1]
        if isinstance(access, str) and len(access) >= 2 and access[0] in '"\'' and access[-1] == access[0]:
            access = access[1:-1]
        return cls(scope=scope, access=access)


@dataclass
class PermissionChecker:
    """Checks tool dispatches against a granted permission set.

    Usage::

        checker = PermissionChecker(granted={"fs:read", "network:write"})
        allowed = checker.check_tool(tool_decl)  # True/False
    """

    granted: set[str] = field(default_factory=set)
    # Wildcard permissions: "fs:*" grants all fs accesses, "*:*" grants everything
    _wildcards: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        for perm in self.granted:
            if perm.endswith(":*"):
                self._wildcards.add(perm[:-2])

    def grant(self, scope: str, access: str) -> None:
        """Grant a permission."""
        perm = f"{scope}:{access}"
        self.granted.add(perm)
        if access == "*":
            self._wildcards.add(scope)

    def is_granted(self, scope: str, access: str) -> bool:
        """Check if a specific permission is granted."""
        if f"{scope}:{access}" in self.granted:
            return True
        if scope in self._wildcards:
            return True
        if "*" in self._wildcards:
            return True
        return False

    def check_tool(self, tool: ToolDecl) -> tuple[bool, Optional[str]]:
        """Check if a tool's required permissions are all granted.

        Returns:
            (allowed, denied_permission) — denied_permission is the first
            permission that was not granted, or None if all are granted.
        """
        for ann in tool.annotations:
            if ann.name != "permission":
                continue
            perm = Permission.from_annotation(ann)
            if not self.is_granted(perm.scope, perm.access):
                return False, str(perm)
        return True, None

    def filter_tools(self, tools: list[ToolDecl]) -> list[ToolDecl]:
        """Return only the tools whose permissions are all granted."""
        return [t for t in tools if self.check_tool(t)[0]]


def extract_permissions(declarations: list[Any]) -> dict[str, list[Permission]]:
    """Extract @permission annotations from all tool declarations.

    Returns:
        Mapping of tool name -> list of required permissions.
    """
    result: dict[str, list[Permission]] = {}
    for decl in declarations:
        if isinstance(decl, ToolDecl):
            perms = [
                Permission.from_annotation(ann)
                for ann in decl.annotations
                if ann.name == "permission"
            ]
            if perms:
                result[decl.name] = perms
    return result


def build_permission_checker(
    declarations: list[Any],
    granted: set[str] | None = None,
) -> PermissionChecker:
    """Build a PermissionChecker from declarations and optional granted set."""
    checker = PermissionChecker(granted=granted or set())
    return checker
