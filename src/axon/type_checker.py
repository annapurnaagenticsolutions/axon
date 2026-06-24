"""Type checker for AXON Phase 1.

This module provides static type checking for AXON declarations. It parses type
strings into structured type representations, validates type consistency across
declarations, and checks function signatures against their usage.

The type checker is deliberately conservative for Phase 1: it validates obvious
type mismatches without attempting full Hindley-Milner inference or complex
generic constraint solving.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Optional, Union

from axon.ast_nodes import (
    AgentDecl,
    Annotation,
    FlowDecl,
    MethodDecl,
    Param,
    PromptDecl,
    RagDecl,
    StageDecl,
    ToolDecl,
    TypeAliasDecl,
)
from axon.expression_ast import (
    ActExpr,
    AssignExpr,
    BinaryOpExpr,
    BlockExpr,
    CallExpr,
    DelegateExpr,
    ErrorExpr,
    Expr,
    ForExpr,
    IfExpr,
    IndexExpr,
    LetExpr,
    LiteralExpr,
    ListExpr,
    MapExpr,
    MatchExpr,
    MemberAccessExpr,
    ModelCallExpr,
    NoneExpr,
    ObserveExpr,
    OkExpr,
    ReturnExpr,
    SomeExpr,
    StoreExpr,
    StringInterpolationExpr,
    ThinkExpr,
    TryExpr,
    UnaryOpExpr,
    VariableExpr,
)
from axon.validator import Diagnostic, Severity


class TypeKind(Enum):
    """Categories of AXON types."""
    PRIMITIVE = "primitive"
    GENERIC = "generic"
    RECORD = "record"
    UNION = "union"
    OPTION = "option"
    RESULT = "result"
    STREAM = "stream"
    FUNCTION = "function"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Type:
    """Base class for all AXON types."""
    name: str
    kind: TypeKind
    args: list[Type] = field(default_factory=list)
    
    def __str__(self) -> str:
        if self.kind == TypeKind.PRIMITIVE:
            return self.name
        if self.kind == TypeKind.GENERIC:
            if self.args:
                return f"{self.name}<{', '.join(str(a) for a in self.args)}>"
            return self.name
        if self.kind == TypeKind.OPTION:
            return f"Option<{str(self.args[0]) if self.args else 'T'}>"
        if self.kind == TypeKind.RESULT:
            if len(self.args) == 2:
                return f"Result<{str(self.args[0])}, {str(self.args[1])}>"
            return "Result<T, E>"
        if self.kind == TypeKind.STREAM:
            return f"Stream<{str(self.args[0]) if self.args else 'T'}>"
        if self.kind == TypeKind.UNION:
            return " | ".join(str(a) for a in self.args)
        if self.kind == TypeKind.RECORD:
            return self.name
        return self.name


@dataclass(frozen=True)
class PrimitiveType(Type):
    """Primitive types: Str, Int, Float, Bool, Any, Bytes, ()."""
    kind: TypeKind = TypeKind.PRIMITIVE


@dataclass(frozen=True)
class GenericType(Type):
    """Generic types: List<T>, Map<K, V>, Set<T>, Tuple<A, B>."""
    kind: TypeKind = TypeKind.GENERIC


@dataclass(frozen=True)
class RecordType(Type):
    """Record types defined with type aliases: { id: Int, title: Str }."""
    kind: TypeKind = TypeKind.RECORD
    fields: dict[str, Type] = field(default_factory=dict)


@dataclass(frozen=True)
class UnionType(Type):
    """Union types: "low" | "medium" | "high"."""
    kind: TypeKind = TypeKind.UNION


@dataclass(frozen=True)
class FunctionType(Type):
    """Function types for methods and tools."""
    kind: TypeKind = TypeKind.FUNCTION
    params: list[tuple[str, Type]] = field(default_factory=list)
    return_type: Optional[Type] = None


# Type parsing state
_PRIMITIVE_TYPES = {"Str", "Int", "Float", "Bool", "Any", "Bytes", "Token"}
_GENERIC_TYPES = {"List", "Map", "Set", "Tuple", "Vec", "Dict"}
_SPECIAL_TYPES = {"Option", "Result", "Stream"}


def parse_type(type_str: str) -> Type:
    """Parse an AXON type string into a structured Type object.
    
    Examples:
        "Str" -> PrimitiveType("Str")
        "List<Int>" -> GenericType("List", [PrimitiveType("Int")])
        "Result<List<Any>, ToolError>" -> ResultType with args
        "low" | "medium" | "high" -> UnionType with string literals
    """
    type_str = type_str.strip()
    
    # Handle unit type
    if type_str == "()":
        return PrimitiveType(kind=TypeKind.PRIMITIVE, name="()")
    
    # Handle union types (e.g., "low" | "medium" | "high", or Str | Int)
    if "|" in type_str:
        return _parse_union_type(type_str)
    
    # Handle Option<T>
    if type_str.startswith("Option<"):
        inner = type_str[7:-1].strip()
        return Type(kind=TypeKind.OPTION, name="Option", args=[parse_type(inner)])
    
    # Handle Result<T, E>
    if type_str.startswith("Result<"):
        inner = type_str[7:-1].strip()
        args = _split_type_args(inner)
        return Type(kind=TypeKind.RESULT, name="Result", args=[parse_type(a) for a in args])
    
    # Handle Stream<T>
    if type_str.startswith("Stream<"):
        inner = type_str[7:-1].strip()
        return Type(kind=TypeKind.STREAM, name="Stream", args=[parse_type(inner)])
    
    # Handle generic types List<T>, Map<K, V>, etc.
    if "<" in type_str and type_str.endswith(">"):
        base_name = type_str[:type_str.index("<")].strip()
        inner = type_str[type_str.index("<") + 1:-1].strip()
        args = _split_type_args(inner)
        
        if base_name in _GENERIC_TYPES:
            return GenericType(kind=TypeKind.GENERIC, name=base_name, args=[parse_type(a) for a in args])
        else:
            # Treat unknown generics as generic types
            return GenericType(kind=TypeKind.GENERIC, name=base_name, args=[parse_type(a) for a in args])
    
    # Handle primitives
    if type_str in _PRIMITIVE_TYPES:
        return PrimitiveType(kind=TypeKind.PRIMITIVE, name=type_str)
    
    # Handle unknown types (could be type aliases or records)
    return Type(kind=TypeKind.UNKNOWN, name=type_str)


def _parse_union_type(type_str: str) -> Type:
    """Parse a union type like "low" | "medium" | "high" or Str | Int."""
    # Split by |, but be careful not to split inside generic brackets
    parts: list[str] = []
    current = ""
    depth = 0
    for char in type_str:
        if char == "<":
            depth += 1
            current += char
        elif char == ">":
            depth -= 1
            current += char
        elif char == "|" and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += char
    if current.strip():
        parts.append(current.strip())
    
    # Parse each part as a type
    args = [parse_type(part) for part in parts]
    return Type(kind=TypeKind.UNION, name="Union", args=args)


def _split_type_args(type_str: str) -> list[str]:
    """Split type arguments by comma, respecting nested generics."""
    args: list[str] = []
    current = ""
    depth = 0
    
    for char in type_str:
        if char == "<":
            depth += 1
            current += char
        elif char == ">":
            depth -= 1
            current += char
        elif char == "," and depth == 0:
            args.append(current.strip())
            current = ""
        else:
            current += char
    
    if current.strip():
        args.append(current.strip())
    
    return args


def types_equal(t1: Type, t2: Type) -> bool:
    """Check if two types are structurally equal."""
    if t1.kind != t2.kind:
        return False
    if t1.name != t2.name:
        return False
    if len(t1.args) != len(t2.args):
        return False
    return all(types_equal(a1, a2) for a1, a2 in zip(t1.args, t2.args))


def is_subtype(sub: Type, super_type: Type) -> bool:
    """Check if sub is a subtype of super_type.
    
    Rules:
    - Any is a supertype of everything
    - Union types: sub is subtype if it matches any member of the union
    - Primitives must match exactly
    - Generics must match structurally
    """
    # Any is a supertype of everything
    if super_type.kind == TypeKind.PRIMITIVE and super_type.name == "Any":
        return True
    
    # Exact match
    if types_equal(sub, super_type):
        return True
    
    # Union supertype: sub is subtype if it matches any union member
    if super_type.kind == TypeKind.UNION:
        return any(is_subtype(sub, member) for member in super_type.args)
    
    # Union subtype: union is subtype if all members are subtypes
    if sub.kind == TypeKind.UNION:
        return all(is_subtype(member, super_type) for member in sub.args)
    
    # Option<T> is a supertype of T (you can return T where Option<T> is expected)
    if super_type.kind == TypeKind.OPTION and sub.kind != TypeKind.OPTION:
        if super_type.args:
            return is_subtype(sub, super_type.args[0])
    
    # Result<T, E> covariance: Result<Int, Error> <: Result<Any, Error>
    if super_type.kind == TypeKind.RESULT and sub.kind == TypeKind.RESULT:
        if len(sub.args) == 2 and len(super_type.args) == 2:
            ok_subtype = is_subtype(sub.args[0], super_type.args[0])
            err_subtype = is_subtype(sub.args[1], super_type.args[1])
            return ok_subtype and err_subtype
    
    # Generic covariance: List<Int> <: List<Any> if Int <: Any
    if super_type.kind == TypeKind.GENERIC and sub.kind == TypeKind.GENERIC:
        if sub.name == super_type.name and len(sub.args) == len(super_type.args):
            return all(is_subtype(a, b) for a, b in zip(sub.args, super_type.args))
    
    # Int is subtype of Float (numeric widening)
    if sub.kind == TypeKind.PRIMITIVE and super_type.kind == TypeKind.PRIMITIVE:
        if sub.name == "Int" and super_type.name == "Float":
            return True
    
    return False


class TypeChecker:
    """Type checker for AXON declarations and expressions."""
    
    def __init__(self):
        self.type_aliases: dict[str, Type] = {}
        self.diagnostics: list[Diagnostic] = []
        self.variable_types: dict[str, Type] = {}  # For local variable type inference
        self.tool_signatures: dict[str, Type] = {}   # tool_name -> return_type
        self.agent_methods: dict[str, Type] = {}     # agent_name.method -> return_type
    
    def check(self, declarations: list) -> list[Diagnostic]:
        """Run type checking on all declarations and return diagnostics."""
        self.diagnostics = []
        self.type_aliases = {}
        self.tool_signatures = {}
        self.agent_methods = {}
        
        # First pass: collect type aliases and signatures
        for decl in declarations:
            if isinstance(decl, TypeAliasDecl):
                self._collect_type_alias(decl)
            elif isinstance(decl, ToolDecl):
                self.tool_signatures[decl.name] = parse_type(decl.return_type)
            elif isinstance(decl, AgentDecl):
                for method in decl.methods:
                    key = f"{decl.name}.{method.name}"
                    self.agent_methods[key] = parse_type(method.return_type)
        
        # Second pass: check each declaration
        for decl in declarations:
            if isinstance(decl, ToolDecl):
                self._check_tool(decl)
            elif isinstance(decl, AgentDecl):
                self._check_agent(decl)
            elif isinstance(decl, PromptDecl):
                self._check_prompt(decl)
            elif isinstance(decl, RagDecl):
                self._check_rag(decl)
            elif isinstance(decl, FlowDecl):
                self._check_flow(decl)
        
        return self.diagnostics
    
    def _collect_type_alias(self, decl: TypeAliasDecl) -> None:
        """Collect a type alias definition."""
        # Parse the type value
        parsed_type = parse_type(decl.value)
        
        # If it has fields, it's a record type
        if decl.fields:
            field_types = {param.name: parse_type(param.type_str) for param in decl.fields}
            record_type = RecordType(kind=TypeKind.RECORD, name=decl.name, fields=field_types)
            self.type_aliases[decl.name] = record_type
        else:
            self.type_aliases[decl.name] = parsed_type
    
    def _check_tool(self, tool: ToolDecl) -> None:
        """Type check a tool declaration."""
        # Check parameter types are valid
        for param in tool.params:
            param_type = parse_type(param.type_str)
            self._validate_type(param_type, f"tool '{tool.name}' parameter '{param.name}'", tool.line)
        
        # Check return type is valid
        return_type = parse_type(tool.return_type)
        self._validate_type(return_type, f"tool '{tool.name}' return type", tool.line)
    
    def _check_agent(self, agent: AgentDecl) -> None:
        """Type check an agent declaration."""
        for method in agent.methods:
            self._check_method(method, f"agent '{agent.name}'", agent.line)
    
    def _check_method(self, method: MethodDecl, context: str, line: int) -> None:
        """Type check a method declaration."""
        method_context = f"{context} method '{method.name}'"
        
        # Check parameter types
        for param in method.params:
            param_type = parse_type(param.type_str)
            self._validate_type(param_type, f"{method_context} parameter '{param.name}'", line)
        
        # Check return type
        return_type = parse_type(method.return_type)
        self._validate_type(return_type, f"{method_context} return type", line)
        
        # Check expression body if available
        if method.parsed_body:
            self.variable_types = {}  # Reset for each method
            # Bind parameter types so inference can resolve variable references
            for param in method.params:
                self.variable_types[param.name] = parse_type(param.type_str)
            inferred_type = self._infer_expression_type(method.parsed_body, method_context)
            if inferred_type and not is_subtype(inferred_type, return_type):
                self.diagnostics.append(
                    Diagnostic(
                        severity="error",
                        message=f"{method_context}: inferred return type '{inferred_type}' does not match declared return type '{return_type}'",
                        line=line,
                        code="return-type-mismatch",
                        hint=f"Expected '{return_type}' but inferred '{inferred_type}'",
                    )
                )
    
    def _check_prompt(self, prompt: PromptDecl) -> None:
        """Type check a prompt declaration."""
        # Check parameter types
        for param in prompt.params:
            param_type = parse_type(param.type_str)
            self._validate_type(param_type, f"prompt '{prompt.name}' parameter '{param.name}'", prompt.line)
        
        # Check return type
        return_type = parse_type(prompt.return_type)
        self._validate_type(return_type, f"prompt '{prompt.name}' return type", prompt.line)
    
    def _check_rag(self, rag: RagDecl) -> None:
        """Type check a RAG declaration."""
        for method in rag.methods:
            self._check_method(method, f"rag '{rag.name}'", rag.line)
    
    def _check_flow(self, flow: FlowDecl) -> None:
        """Type check a flow declaration."""
        # Check parameter types
        for param in flow.params:
            param_type = parse_type(param.type_str)
            self._validate_type(param_type, f"flow '{flow.name}' parameter '{param.name}'", flow.line)
        
        # Check return type
        return_type = parse_type(flow.return_type)
        self._validate_type(return_type, f"flow '{flow.name}' return type", flow.line)
        
        # Check stages
        for stage in flow.stages:
            self._check_stage(stage, f"flow '{flow.name}'", flow.line)
    
    def _check_stage(self, stage: StageDecl, context: str, line: int) -> None:
        """Type check a flow stage."""
        stage_context = f"{context} stage '{stage.name}'"
        
        # Check parameter types
        for param in stage.params:
            param_type = parse_type(param.type_str)
            self._validate_type(param_type, f"{stage_context} parameter '{param.name}'", line)
        
        # Check return type
        return_type = parse_type(stage.return_type)
        self._validate_type(return_type, f"{stage_context} return type", line)
    
    def _validate_type(self, type_obj: Type, context: str, line: int) -> None:
        """Validate that a type is well-formed."""
        # Check for unknown type names (that aren't type aliases)
        if type_obj.kind == TypeKind.UNKNOWN and type_obj.name not in self.type_aliases:
            self.diagnostics.append(
                Diagnostic(
                    severity="warning",
                    message=f"{context} uses unknown type '{type_obj.name}'",
                    line=line,
                    code="unknown-type",
                )
            )
        
        # Recursively validate type arguments
        for arg in type_obj.args:
            self._validate_type(arg, context, line)
        
        # Validate record fields if this is a record type
        if type_obj.kind == TypeKind.RECORD and hasattr(type_obj, 'fields'):
            for field_name, field_type in type_obj.fields.items():
                self._validate_type(field_type, f"{context} field '{field_name}'", line)
    
    def _validate_record_field_access(self, record_type: Type, field_name: str, context: str, line: int) -> None:
        """Validate that a field access is valid for a record type."""
        if record_type.kind == TypeKind.RECORD and hasattr(record_type, 'fields'):
            if field_name not in record_type.fields:
                self.diagnostics.append(
                    Diagnostic(
                        severity="error",
                        message=f"{context}: record type '{record_type.name}' has no field '{field_name}'",
                        line=line,
                        code="unknown-field",
                    )
                )
        elif record_type.kind == TypeKind.UNKNOWN and record_type.name in self.type_aliases:
            # Check if the type alias is a record
            alias_type = self.type_aliases[record_type.name]
            if alias_type.kind == TypeKind.RECORD and hasattr(alias_type, 'fields'):
                if field_name not in alias_type.fields:
                    self.diagnostics.append(
                        Diagnostic(
                            severity="error",
                            message=f"{context}: type alias '{record_type.name}' has no field '{field_name}'",
                            line=line,
                            code="unknown-field",
                        )
                    )
        else:
            self.diagnostics.append(
                Diagnostic(
                    severity="error",
                    message=f"{context}: cannot access field '{field_name}' on non-record type '{record_type.name}'",
                    line=line,
                    code="invalid-field-access",
                )
            )
    
    def _infer_expression_type(self, expr: Expr, context: str) -> Optional[Type]:
        """Infer the type of an expression AST node."""
        if isinstance(expr, LiteralExpr):
            return self._infer_literal_type(expr)
        elif isinstance(expr, VariableExpr):
            return self._infer_variable_type(expr, context)
        elif isinstance(expr, BinaryOpExpr):
            return self._infer_binary_op_type(expr, context)
        elif isinstance(expr, UnaryOpExpr):
            return self._infer_unary_op_type(expr, context)
        elif isinstance(expr, CallExpr):
            return self._infer_call_type(expr, context)
        elif isinstance(expr, MemberAccessExpr):
            return self._infer_member_access_type(expr, context)
        elif isinstance(expr, IndexExpr):
            return self._infer_index_type(expr, context)
        elif isinstance(expr, ListExpr):
            return self._infer_list_type(expr, context)
        elif isinstance(expr, MapExpr):
            return self._infer_map_type(expr, context)
        elif isinstance(expr, OkExpr):
            return self._infer_ok_type(expr, context)
        elif isinstance(expr, ErrorExpr):
            return self._infer_error_type(expr, context)
        elif isinstance(expr, SomeExpr):
            return self._infer_some_type(expr, context)
        elif isinstance(expr, NoneExpr):
            return Type(kind=TypeKind.OPTION, name="Option", args=[PrimitiveType(kind=TypeKind.PRIMITIVE, name="Any")])
        elif isinstance(expr, IfExpr):
            return self._infer_if_type(expr, context)
        elif isinstance(expr, LetExpr):
            return self._infer_let_type(expr, context)
        elif isinstance(expr, BlockExpr):
            return self._infer_block_type(expr, context)
        elif isinstance(expr, ReturnExpr):
            return self._infer_return_type(expr, context)
        elif isinstance(expr, StringInterpolationExpr):
            return PrimitiveType(kind=TypeKind.PRIMITIVE, name="Str")
        elif isinstance(expr, ActExpr):
            return self._infer_act_type(expr, context)
        elif isinstance(expr, DelegateExpr):
            return self._infer_delegate_type(expr, context)
        elif isinstance(expr, ModelCallExpr):
            return PrimitiveType(kind=TypeKind.PRIMITIVE, name="Str")
        elif isinstance(expr, TryExpr):
            return self._infer_try_type(expr, context)
        elif isinstance(expr, ForExpr):
            return self._infer_for_type(expr, context)
        elif isinstance(expr, AssignExpr):
            return self._infer_assign_type(expr, context)
        elif isinstance(expr, MatchExpr):
            return self._infer_match_type(expr, context)
        elif isinstance(expr, StoreExpr):
            return PrimitiveType(kind=TypeKind.PRIMITIVE, name="()")
        elif isinstance(expr, ThinkExpr):
            return PrimitiveType(kind=TypeKind.PRIMITIVE, name="()")
        elif isinstance(expr, ObserveExpr):
            return PrimitiveType(kind=TypeKind.PRIMITIVE, name="()")
        else:
            # Unknown expression type
            return Type(kind=TypeKind.UNKNOWN, name="Unknown")
    
    def _infer_literal_type(self, expr: LiteralExpr) -> Type:
        """Infer type from a literal expression."""
        if expr.value is None:
            return Type(kind=TypeKind.OPTION, name="Option", args=[PrimitiveType(kind=TypeKind.PRIMITIVE, name="Any")])
        elif isinstance(expr.value, bool):
            return PrimitiveType(kind=TypeKind.PRIMITIVE, name="Bool")
        elif isinstance(expr.value, int):
            return PrimitiveType(kind=TypeKind.PRIMITIVE, name="Int")
        elif isinstance(expr.value, float):
            return PrimitiveType(kind=TypeKind.PRIMITIVE, name="Float")
        elif isinstance(expr.value, str):
            return PrimitiveType(kind=TypeKind.PRIMITIVE, name="Str")
        else:
            return PrimitiveType(kind=TypeKind.PRIMITIVE, name="Any")
    
    def _infer_variable_type(self, expr: VariableExpr, context: str) -> Type:
        """Infer type from a variable expression."""
        # Check if it's a known variable
        if expr.name in self.variable_types:
            return self.variable_types[expr.name]
        
        # Otherwise, it's an unknown type
        return Type(kind=TypeKind.UNKNOWN, name=expr.name)
    
    def _infer_binary_op_type(self, expr: BinaryOpExpr, context: str) -> Type:
        """Infer type from a binary operation."""
        left_type = self._infer_expression_type(expr.left, context)
        right_type = self._infer_expression_type(expr.right, context)
        
        # Arithmetic operators
        if expr.op in ["+", "-", "*", "/"]:
            # If both operands are Int, result is Int
            if (left_type.kind == TypeKind.PRIMITIVE and left_type.name == "Int" and
                right_type.kind == TypeKind.PRIMITIVE and right_type.name == "Int"):
                return PrimitiveType(kind=TypeKind.PRIMITIVE, name="Int")
            # If both operands are Float, result is Float
            elif (left_type.kind == TypeKind.PRIMITIVE and left_type.name == "Float" and
                  right_type.kind == TypeKind.PRIMITIVE and right_type.name == "Float"):
                return PrimitiveType(kind=TypeKind.PRIMITIVE, name="Float")
            # Otherwise, result is Any
            else:
                return PrimitiveType(kind=TypeKind.PRIMITIVE, name="Any")
        
        # Comparison operators
        elif expr.op in ["==", "!=", "<", ">", "<=", ">="]:
            return PrimitiveType(kind=TypeKind.PRIMITIVE, name="Bool")
        
        # Logical operators
        elif expr.op in ["&&", "||"]:
            return PrimitiveType(kind=TypeKind.PRIMITIVE, name="Bool")
        
        # String concatenation
        elif expr.op == "+":
            if (left_type.kind == TypeKind.PRIMITIVE and left_type.name == "Str" and
                right_type.kind == TypeKind.PRIMITIVE and right_type.name == "Str"):
                return PrimitiveType(kind=TypeKind.PRIMITIVE, name="Str")
        
        return PrimitiveType(kind=TypeKind.PRIMITIVE, name="Any")
    
    def _infer_unary_op_type(self, expr: UnaryOpExpr, context: str) -> Type:
        """Infer type from a unary operation."""
        operand_type = self._infer_expression_type(expr.operand, context)
        
        if expr.op == "-":
            if operand_type.kind == TypeKind.PRIMITIVE and operand_type.name in ["Int", "Float"]:
                return operand_type
        elif expr.op in ["!", "not"]:
            return PrimitiveType(kind=TypeKind.PRIMITIVE, name="Bool")
        
        return operand_type
    
    def _infer_call_type(self, expr: CallExpr, context: str) -> Type:
        """Infer type from a function/method call."""
        # For now, return unknown type since we don't have function signatures
        # In a full implementation, we would look up the function signature
        return Type(kind=TypeKind.UNKNOWN, name="CallResult")
    
    def _infer_member_access_type(self, expr: MemberAccessExpr, context: str) -> Type:
        """Infer type from member access (obj.field)."""
        object_type = self._infer_expression_type(expr.object, context)
        
        # If the object is a record type, check the field
        if object_type.kind == TypeKind.RECORD and hasattr(object_type, 'fields'):
            if expr.member in object_type.fields:
                return object_type.fields[expr.member]
        
        # If it's a type alias that's a record
        if object_type.kind == TypeKind.UNKNOWN and object_type.name in self.type_aliases:
            alias_type = self.type_aliases[object_type.name]
            if alias_type.kind == TypeKind.RECORD and hasattr(alias_type, 'fields'):
                if expr.member in alias_type.fields:
                    return alias_type.fields[expr.member]
        
        return Type(kind=TypeKind.UNKNOWN, name=expr.member)
    
    def _infer_index_type(self, expr: IndexExpr, context: str) -> Type:
        """Infer type from index operation (array[index])."""
        object_type = self._infer_expression_type(expr.object, context)
        
        # If the object is a List<T>, return T
        if object_type.kind == TypeKind.GENERIC and object_type.name == "List" and object_type.args:
            return object_type.args[0]
        
        # If the object is a Map<K, V>, return V
        if object_type.kind == TypeKind.GENERIC and object_type.name == "Map" and len(object_type.args) >= 2:
            return object_type.args[1]
        
        return Type(kind=TypeKind.UNKNOWN, name="IndexResult")
    
    def _infer_list_type(self, expr: ListExpr, context: str) -> Type:
        """Infer type from a list literal."""
        if not expr.elements:
            return GenericType(kind=TypeKind.GENERIC, name="List", args=[PrimitiveType(kind=TypeKind.PRIMITIVE, name="Any")])
        
        # Infer type from first element
        first_type = self._infer_expression_type(expr.elements[0], context)
        return GenericType(kind=TypeKind.GENERIC, name="List", args=[first_type])
    
    def _infer_map_type(self, expr: MapExpr, context: str) -> Type:
        """Infer type from a map literal."""
        if not expr.pairs:
            return GenericType(kind=TypeKind.GENERIC, name="Map", args=[
                PrimitiveType(kind=TypeKind.PRIMITIVE, name="Str"),
                PrimitiveType(kind=TypeKind.PRIMITIVE, name="Any")
            ])
        
        # Infer types from first pair
        first_key_type = self._infer_expression_type(expr.pairs[0][0], context)
        first_value_type = self._infer_expression_type(expr.pairs[0][1], context)
        return GenericType(kind=TypeKind.GENERIC, name="Map", args=[first_key_type, first_value_type])
    
    def _infer_ok_type(self, expr: OkExpr, context: str) -> Type:
        """Infer type from Ok constructor."""
        value_type = self._infer_expression_type(expr.value, context)
        return Type(kind=TypeKind.RESULT, name="Result", args=[value_type, PrimitiveType(kind=TypeKind.PRIMITIVE, name="Any")])
    
    def _infer_error_type(self, expr: ErrorExpr, context: str) -> Type:
        """Infer type from Error constructor."""
        value_type = self._infer_expression_type(expr.value, context)
        return Type(kind=TypeKind.RESULT, name="Result", args=[PrimitiveType(kind=TypeKind.PRIMITIVE, name="Any"), value_type])
    
    def _infer_some_type(self, expr: SomeExpr, context: str) -> Type:
        """Infer type from Some constructor."""
        value_type = self._infer_expression_type(expr.value, context)
        return Type(kind=TypeKind.OPTION, name="Option", args=[value_type])
    
    def _infer_if_type(self, expr: IfExpr, context: str) -> Type:
        """Infer type from if expression."""
        then_type = self._infer_expression_type(expr.then_branch, context)
        if expr.else_branch:
            else_type = self._infer_expression_type(expr.else_branch, context)
            # For now, return then_type if they match, otherwise Any
            if types_equal(then_type, else_type):
                return then_type
            return PrimitiveType(kind=TypeKind.PRIMITIVE, name="Any")
        return then_type
    
    def _infer_let_type(self, expr: LetExpr, context: str) -> Type:
        """Infer type from let expression."""
        value_type = self._infer_expression_type(expr.value, context)
        # Bind the variable
        self.variable_types[expr.name] = value_type
        # Infer body type
        return self._infer_expression_type(expr.body, context)
    
    def _infer_block_type(self, expr: BlockExpr, context: str) -> Type:
        """Infer type from block expression."""
        if not expr.statements:
            return PrimitiveType(kind=TypeKind.PRIMITIVE, name="()")
        
        # Return type of last statement
        return self._infer_expression_type(expr.statements[-1], context)
    
    def _infer_return_type(self, expr: ReturnExpr, context: str) -> Type:
        """Infer type from return expression."""
        return self._infer_expression_type(expr.value, context)

    def _infer_act_type(self, expr: ActExpr, context: str) -> Type:
        """Infer type from tool invocation (act)."""
        if expr.tool_name in self.tool_signatures:
            return self.tool_signatures[expr.tool_name]
        return Type(kind=TypeKind.UNKNOWN, name="CallResult")

    def _infer_delegate_type(self, expr: DelegateExpr, context: str) -> Type:
        """Infer type from agent delegation."""
        for key, return_type in self.agent_methods.items():
            if key.endswith(f".{expr.agent_name}") or key == expr.agent_name:
                return return_type
        return Type(kind=TypeKind.UNKNOWN, name="DelegateResult")

    def _infer_try_type(self, expr: TryExpr, context: str) -> Type:
        """Infer type from try operator (expr?).

        Unwraps Result<T, E> -> T or Option<T> -> T.
        """
        operand_type = self._infer_expression_type(expr.operand, context)
        if operand_type.kind == TypeKind.RESULT and operand_type.args:
            return operand_type.args[0]
        if operand_type.kind == TypeKind.OPTION and operand_type.args:
            return operand_type.args[0]
        return operand_type

    def _infer_for_type(self, expr: ForExpr, context: str) -> Type:
        """Infer type from for-in loop.

        Binds loop variable type from iterable element type.
        Returns the type of the body expression.
        """
        iterable_type = self._infer_expression_type(expr.iterable, context)
        element_type: Type = PrimitiveType(kind=TypeKind.PRIMITIVE, name="Any")
        if iterable_type.kind == TypeKind.GENERIC and iterable_type.name == "List" and iterable_type.args:
            element_type = iterable_type.args[0]
        elif iterable_type.kind == TypeKind.GENERIC and iterable_type.name == "Map" and len(iterable_type.args) >= 2:
            # For Map, iterating yields (key, value) or just keys depending on convention
            element_type = iterable_type.args[0]
        # Bind loop variable
        self.variable_types[expr.var_name] = element_type
        return self._infer_expression_type(expr.body, context)

    def _infer_assign_type(self, expr: AssignExpr, context: str) -> Type:
        """Infer type from assignment (name = value).

        Binds the variable to the inferred value type.
        """
        value_type = self._infer_expression_type(expr.value, context)
        self.variable_types[expr.name] = value_type
        return value_type

    def _infer_match_type(self, expr: MatchExpr, context: str) -> Type:
        """Infer type from match expression.

        Returns a union of all arm types (simplified if all identical).
        """
        arm_types: list[Type] = []
        for arm in expr.arms:
            arm_type = self._infer_expression_type(arm.body, context)
            arm_types.append(arm_type)
        if not arm_types:
            return PrimitiveType(kind=TypeKind.PRIMITIVE, name="Any")
        if len(arm_types) == 1:
            return arm_types[0]
        # If all arm types are the same, return that type directly
        first = arm_types[0]
        if all(types_equal(first, t) for t in arm_types[1:]):
            return first
        # Return union of all arm types
        return Type(kind=TypeKind.UNION, name="Union", args=arm_types)

    def _infer_call_type(self, expr: CallExpr, context: str) -> Type:
        """Infer type from a function/method call."""
        # If callee is a VariableExpr, try to resolve as tool or method
        if isinstance(expr.callee, VariableExpr):
            name = expr.callee.name
            if name in self.tool_signatures:
                return self.tool_signatures[name]
            if name in self.agent_methods:
                return self.agent_methods[name]
        return Type(kind=TypeKind.UNKNOWN, name="CallResult")


def check_types(declarations: list) -> list[Diagnostic]:
    """Convenience function to type check declarations."""
    checker = TypeChecker()
    return checker.check(declarations)


# -- Runtime type validation --------------------------------------

def validate_runtime_type(value: Any, type_str: str) -> Optional[str]:
    """Validate a Python runtime value against an AXON type string.

    Returns None if valid, or an error message string if invalid.

    Examples:
        validate_runtime_type("hello", "Str") -> None
        validate_runtime_type(42, "Str") -> "expected Str, got int"
        validate_runtime_type([1, 2], "List<Int>") -> None
        validate_runtime_type([1, "a"], "List<Int>") -> "List element 1: expected Int, got str"
        validate_runtime_type(None, "Option<Str>") -> None
        validate_runtime_type("x", "Option<Str>") -> None
    """
    type_obj = parse_type(type_str)
    return _validate_value(value, type_obj)


def _validate_value(value: Any, type_obj: Type) -> Optional[str]:
    """Recursively validate a value against a parsed Type."""
    # Option<T> — None is always valid
    if type_obj.kind == TypeKind.OPTION:
        if value is None:
            return None
        if type_obj.args:
            return _validate_value(value, type_obj.args[0])
        return None

    # Result<Ok, Err> — accept Ok/Err dicts or plain values for now
    if type_obj.kind == TypeKind.RESULT:
        if isinstance(value, dict) and ("ok" in value or "err" in value):
            return None
        # Plain values are also accepted (wrapped by Ok/Err constructors)
        return None

    # Any — always valid
    if type_obj.kind == TypeKind.PRIMITIVE and type_obj.name == "Any":
        return None

    # Primitive types
    if type_obj.kind == TypeKind.PRIMITIVE:
        expected_pytype = _PRIMITIVE_PYTYPES.get(type_obj.name)
        if expected_pytype is not None:
            if not isinstance(value, expected_pytype):
                return f"expected {type_obj.name}, got {type(value).__name__}"
            return None
        # Unknown primitive — permissive
        return None

    # List<T>
    if type_obj.kind == TypeKind.GENERIC and type_obj.name == "List":
        if not isinstance(value, list):
            return f"expected List, got {type(value).__name__}"
        if type_obj.args:
            element_type = type_obj.args[0]
            for i, item in enumerate(value):
                err = _validate_value(item, element_type)
                if err:
                    return f"List element {i}: {err}"
        return None

    # Map<K, V> / Dict<K, V>
    if type_obj.kind == TypeKind.GENERIC and type_obj.name in ("Map", "Dict"):
        if not isinstance(value, dict):
            return f"expected {type_obj.name}, got {type(value).__name__}"
        if len(type_obj.args) >= 2:
            key_type = type_obj.args[0]
            val_type = type_obj.args[1]
            for k, v in value.items():
                err = _validate_value(k, key_type)
                if err:
                    return f"Map key {k!r}: {err}"
                err = _validate_value(v, val_type)
                if err:
                    return f"Map value for key {k!r}: {err}"
        return None

    # Set<T>
    if type_obj.kind == TypeKind.GENERIC and type_obj.name == "Set":
        if not isinstance(value, (set, frozenset)):
            return f"expected Set, got {type(value).__name__}"
        if type_obj.args:
            element_type = type_obj.args[0]
            for i, item in enumerate(value):
                err = _validate_value(item, element_type)
                if err:
                    return f"Set element {i}: {err}"
        return None

    # Tuple<A, B, ...>
    if type_obj.kind == TypeKind.GENERIC and type_obj.name == "Tuple":
        if not isinstance(value, tuple):
            return f"expected Tuple, got {type(value).__name__}"
        if len(type_obj.args) != len(value):
            return f"expected Tuple of length {len(type_obj.args)}, got {len(value)}"
        for i, (item, arg_type) in enumerate(zip(value, type_obj.args)):
            err = _validate_value(item, arg_type)
            if err:
                return f"Tuple element {i}: {err}"
        return None

    # Unknown / fallback — permissive
    return None


_PRIMITIVE_PYTYPES: dict[str, type] = {
    "Str": str,
    "Int": int,
    "Float": float,
    "Bool": bool,
    "Bytes": bytes,
}
