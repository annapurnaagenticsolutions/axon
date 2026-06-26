"""Expression parser for AXON method bodies.

This module parses AXON expressions from raw text into structured AST nodes.
It is a recursive descent parser that handles literals, variables, operators,
function calls, and control structures without requiring runtime execution.
"""

from __future__ import annotations

import re
from typing import Optional, Union

from axon.expression_ast import (
    AssignExpr,
    BinaryOpExpr,
    BlockExpr,
    CallExpr,
    ErrorExpr,
    Expr,
    ForExpr,
    IfExpr,
    IndexExpr,
    LetExpr,
    LiteralExpr,
    ListExpr,
    MapExpr,
    MatchArm,
    MatchExpr,
    MemberAccessExpr,
    NoneExpr,
    OkExpr,
    ReturnExpr,
    SomeExpr,
    StoreExpr,
    StringInterpolationExpr,
    ThinkExpr,
    ObserveExpr,
    TryExpr,
    UnaryOpExpr,
    VariableExpr,
    ActExpr,
    ModelCallExpr,
    DelegateExpr,
    ParExpr,
    StructuredOutputExpr,
)


class ExpressionParser:
    """Parser for AXON expressions."""
    
    def __init__(self, source: str, line_offset: int = 0):
        self.source = source
        self.line_offset = line_offset
        self.pos = 0
        self.current_char = self.source[0] if source else None
    
    def advance(self) -> None:
        """Move to the next character."""
        self.pos += 1
        if self.pos < len(self.source):
            self.current_char = self.source[self.pos]
        else:
            self.current_char = None
    
    def skip_whitespace(self) -> None:
        """Skip whitespace characters."""
        while self.current_char and self.current_char.isspace():
            self.advance()
    
    def peek(self, offset: int = 1) -> Optional[str]:
        """Peek at the next character without advancing."""
        peek_pos = self.pos + offset
        if peek_pos < len(self.source):
            return self.source[peek_pos]
        return None
    
    def _is_expression_start(self, char: str | None) -> bool:
        """Check if the current character can start a new expression."""
        if char is None:
            return False
        # Identifier, string literal, number/bool/None literal, list/map/paren
        if char.isalnum() or char == '_' or char == '-' or char in '"[{(':
            return True
        return False

    def parse(self) -> Expr:
        """Parse the entire source as an expression.

        Supports semicolon- or newline-separated statements, returning a
        BlockExpr when multiple statements are present.
        """
        self.skip_whitespace()
        if not self.current_char:
            return LiteralExpr(line=self.line_offset, value=None)

        statements = []
        while self.current_char:
            stmt = self.parse_expression()
            statements.append(stmt)
            self.skip_whitespace()

            if self.current_char == ';':
                self.advance()
                self.skip_whitespace()
                continue

            # If there's more content that looks like a new statement, continue
            if self._is_expression_start(self.current_char):
                continue

            break

        if len(statements) == 1:
            return statements[0]
        return BlockExpr(line=self.line_offset, statements=statements)
    
    def parse_expression(self) -> Expr:
        """Parse an expression (lowest precedence)."""
        expr = self.parse_assignment()
        self.skip_whitespace()
        while self.current_char == '?':
            self.advance()
            self.skip_whitespace()
            expr = TryExpr(line=self.line_offset, operand=expr)
        return expr

    def parse_assignment(self) -> Expr:
        """Parse assignment (lowest precedence, right-associative)."""
        left = self.parse_logical_or()
        self.skip_whitespace()

        # Check for single = (not ==, not =>)
        if self.current_char == '=' and self.peek() not in ('=', '>'):
            # Only allow assignment when LHS is a simple variable
            if isinstance(left, VariableExpr):
                self.advance()  # consume =
                self.skip_whitespace()
                right = self.parse_assignment()
                return AssignExpr(
                    line=self.line_offset,
                    name=left.name,
                    value=right,
                )

        return left

    def parse_logical_or(self) -> Expr:
        """Parse logical OR (||)."""
        left = self.parse_logical_and()
        
        while True:
            self.skip_whitespace()
            if self.current_char == '|' and self.peek() == '|':
                self.advance()  # consume first |
                self.advance()  # consume second |
                self.skip_whitespace()
                right = self.parse_logical_and()
                left = BinaryOpExpr(op="||", left=left, right=right, line=self.line_offset)
            else:
                break
        
        return left
    
    def parse_logical_and(self) -> Expr:
        """Parse logical AND (&&)."""
        left = self.parse_equality()
        
        while True:
            self.skip_whitespace()
            if self.current_char == '&' and self.peek() == '&':
                self.advance()  # consume first &
                self.advance()  # consume second &
                self.skip_whitespace()
                right = self.parse_equality()
                left = BinaryOpExpr(line=self.line_offset, op="&&", left=left, right=right)
            else:
                break
        
        return left
    
    def parse_equality(self) -> Expr:
        """Parse equality operators (==, !=)."""
        left = self.parse_comparison()
        
        while True:
            self.skip_whitespace()
            if self.current_char == '=' and self.peek() == '=':
                self.advance()
                self.advance()
                self.skip_whitespace()
                right = self.parse_comparison()
                left = BinaryOpExpr(line=self.line_offset, op="==", left=left, right=right)
            elif self.current_char == '!' and self.peek() == '=':
                self.advance()
                self.advance()
                self.skip_whitespace()
                right = self.parse_comparison()
                left = BinaryOpExpr(line=self.line_offset, op="!=", left=left, right=right)
            else:
                break
        
        return left
    
    def parse_comparison(self) -> Expr:
        """Parse comparison operators (<, >, <=, >=)."""
        left = self.parse_additive()
        
        while True:
            self.skip_whitespace()
            if self.current_char == '<' and self.peek() == '=':
                self.advance()
                self.advance()
                self.skip_whitespace()
                right = self.parse_additive()
                left = BinaryOpExpr(line=self.line_offset, op="<=", left=left, right=right)
            elif self.current_char == '>' and self.peek() == '=':
                self.advance()
                self.advance()
                self.skip_whitespace()
                right = self.parse_additive()
                left = BinaryOpExpr(line=self.line_offset, op=">=", left=left, right=right)
            elif self.current_char == '<':
                self.advance()
                self.skip_whitespace()
                right = self.parse_additive()
                left = BinaryOpExpr(line=self.line_offset, op="<", left=left, right=right)
            elif self.current_char == '>':
                self.advance()
                self.skip_whitespace()
                right = self.parse_additive()
                left = BinaryOpExpr(line=self.line_offset, op=">", left=left, right=right)
            else:
                break
        
        return left
    
    def parse_additive(self) -> Expr:
        """Parse additive operators (+, -)."""
        left = self.parse_multiplicative()
        
        while True:
            self.skip_whitespace()
            if self.current_char == '+':
                self.advance()
                self.skip_whitespace()
                right = self.parse_multiplicative()
                left = BinaryOpExpr(line=self.line_offset, op="+", left=left, right=right)
            elif self.current_char == '-':
                self.advance()
                self.skip_whitespace()
                right = self.parse_multiplicative()
                left = BinaryOpExpr(line=self.line_offset, op="-", left=left, right=right)
            else:
                break
        
        return left
    
    def parse_multiplicative(self) -> Expr:
        """Parse multiplicative operators (*, /)."""
        left = self.parse_unary()
        
        while True:
            self.skip_whitespace()
            if self.current_char == '*':
                self.advance()
                self.skip_whitespace()
                right = self.parse_unary()
                left = BinaryOpExpr(line=self.line_offset, op="*", left=left, right=right)
            elif self.current_char == '/':
                self.advance()
                self.skip_whitespace()
                right = self.parse_unary()
                left = BinaryOpExpr(line=self.line_offset, op="/", left=left, right=right)
            else:
                break
        
        return left
    
    def parse_unary(self) -> Expr:
        """Parse unary operators (-, !, not)."""
        if self.current_char == '-':
            self.advance()
            self.skip_whitespace()
            operand = self.parse_unary()
            return UnaryOpExpr(line=self.line_offset, op="-", operand=operand)
        elif self.current_char == '!':
            self.advance()
            self.skip_whitespace()
            operand = self.parse_unary()
            return UnaryOpExpr(line=self.line_offset, op="!", operand=operand)
        
        return self.parse_primary()
    
    def _match_keyword(self, keyword: str) -> bool:
        """Check if current position starts with keyword followed by a word boundary."""
        end = self.pos + len(keyword)
        if self.source.startswith(keyword, self.pos):
            # Must be followed by non-alphanumeric or end of string
            if end >= len(self.source) or not self.source[end].isalnum():
                return True
        return False

    def parse_primary(self) -> Expr:
        """Parse primary expressions (literals, variables, parentheses, calls)."""
        self.skip_whitespace()

        # Parenthesized expression
        if self.current_char == '(':
            self.advance()
            expr = self.parse_expression()
            self.skip_whitespace()
            if self.current_char == ')':
                self.advance()
            self.skip_whitespace()
            return expr

        # Control-flow keywords
        if self.current_char == 'd' and self._match_keyword("delegate"):
            return self.parse_delegate()
        if self.current_char == 'a' and self._match_keyword("act"):
            return self.parse_act()
        if self.current_char == 's' and self._match_keyword("store"):
            # Peek ahead: if followed by . or (, treat as variable name (e.g. store.search(...))
            after_pos = self.pos + 5
            while after_pos < len(self.source) and self.source[after_pos].isspace():
                after_pos += 1
            if after_pos < len(self.source) and self.source[after_pos] in '.(':
                pass  # fall through to variable parsing
            else:
                return self.parse_store()
        if self.current_char == 't' and self._match_keyword("think_as"):
            return self.parse_think_as()
        if self.current_char == 't' and self._match_keyword("think"):
            return self.parse_think()
        if self.current_char == 'o' and self._match_keyword("observe"):
            return self.parse_observe()
        if self.current_char == 'i' and self._match_keyword("if"):
            return self.parse_if()
        if self.current_char == 'f' and self._match_keyword("for"):
            return self.parse_for()
        if self.current_char == 'p' and self._match_keyword("par"):
            return self.parse_par()
        if self.current_char == 'm' and self._match_keyword("match"):
            return self.parse_match()
        if self.current_char == 'l' and self._match_keyword("let"):
            return self.parse_let()
        if self.current_char == 'r' and self._match_keyword("return"):
            return self.parse_return()

        # String literal
        if self.current_char == '"':
            return self.parse_string_literal()

        # Number literal
        if self.current_char and (self.current_char.isdigit() or self.current_char == '-'):
            return self.parse_number_literal()

        # Boolean literals
        if self.current_char == 't' and self.source.startswith("true", self.pos):
            self.pos += 4
            self.current_char = self.source[self.pos] if self.pos < len(self.source) else None
            self.skip_whitespace()
            return LiteralExpr(line=self.line_offset, value=True)

        if self.current_char == 'f' and self.source.startswith("false", self.pos):
            self.pos += 5
            self.current_char = self.source[self.pos] if self.pos < len(self.source) else None
            self.skip_whitespace()
            return LiteralExpr(line=self.line_offset, value=False)

        # None literal
        if self.current_char == 'N' and self.source.startswith("None", self.pos):
            self.pos += 4
            self.current_char = self.source[self.pos] if self.pos < len(self.source) else None
            self.skip_whitespace()
            return NoneExpr(line=self.line_offset)

        # List literal
        if self.current_char == '[':
            return self.parse_list_literal()

        # Map literal
        if self.current_char == '{':
            return self.parse_map_literal()

        # Ok/Err constructors
        if self.current_char == 'O' and self.source.startswith("Ok(", self.pos):
            return self.parse_ok_constructor()

        if self.current_char == 'E' and self.source.startswith("Err(", self.pos):
            return self.parse_err_constructor()

        # Some constructor
        if self.current_char == 'S' and self.source.startswith("Some(", self.pos):
            return self.parse_some_constructor()

        # Variable or function call
        if self.current_char and (self.current_char.isalpha() or self.current_char == '_'):
            return self.parse_variable_or_call()

        # Default: return a literal with None
        return LiteralExpr(line=self.line_offset, value=None)
    
    def parse_string_literal(self) -> Expr:
        """Parse a string literal, handling interpolation."""
        if self.current_char != '"':
            return LiteralExpr(line=self.line_offset, value="")
        
        self.advance()  # consume opening quote
        parts = []
        current_str = ""
        
        while self.current_char and self.current_char != '"':
            if self.current_char == '\\' and self.peek():
                # Escape sequence
                self.advance()
                current_str += self.current_char
                self.advance()
            elif self.current_char == '{' and self.peek() == '}':
                # Simple interpolation {var}
                if current_str:
                    parts.append(LiteralExpr(line=self.line_offset, value=current_str))
                    current_str = ""
                self.advance()  # consume {
                self.advance()  # consume }
                # For now, just skip the variable name
                while self.current_char and self.current_char != '}':
                    self.advance()
                if self.current_char == '}':
                    self.advance()
            else:
                current_str += self.current_char
                self.advance()
        
        if current_str:
            parts.append(LiteralExpr(line=self.line_offset, value=current_str))
        
        if self.current_char == '"':
            self.advance()  # consume closing quote
        
        if len(parts) == 1 and isinstance(parts[0], LiteralExpr):
            return parts[0]
        
        return StringInterpolationExpr(line=self.line_offset, parts=parts)
    
    def parse_number_literal(self) -> Expr:
        """Parse a number literal (integer or float)."""
        start = self.pos
        
        if self.current_char == '-':
            self.advance()
        
        while self.current_char and (self.current_char.isdigit() or self.current_char == '.'):
            self.advance()
        
        num_str = self.source[start:self.pos]
        
        try:
            if '.' in num_str:
                value = float(num_str)
            else:
                value = int(num_str)
        except ValueError:
            value = 0
        
        self.skip_whitespace()
        return LiteralExpr(line=self.line_offset, value=value)
    
    def parse_list_literal(self) -> Expr:
        """Parse a list literal: [1, 2, 3]."""
        if self.current_char != '[':
            return ListExpr(line=self.line_offset, elements=[])
        
        self.advance()  # consume [
        elements = []
        
        self.skip_whitespace()
        while self.current_char and self.current_char != ']':
            if self.current_char == ',':
                self.advance()
                self.skip_whitespace()
                continue
            
            elem = self.parse_expression()
            elements.append(elem)
            self.skip_whitespace()
        
        if self.current_char == ']':
            self.advance()
        
        return ListExpr(line=self.line_offset, elements=elements)
    
    def parse_map_literal(self) -> Expr:
        """Parse a map literal: {key: value, ...}."""
        if self.current_char != '{':
            return MapExpr(line=self.line_offset, pairs=[])
        
        self.advance()  # consume {
        pairs = []
        
        self.skip_whitespace()
        while self.current_char and self.current_char != '}':
            if self.current_char == ',':
                self.advance()
                self.skip_whitespace()
                continue
            
            key = self.parse_expression()
            self.skip_whitespace()
            
            if self.current_char == ':':
                self.advance()
                self.skip_whitespace()
            
            value = self.parse_expression()
            pairs.append((key, value))
            self.skip_whitespace()
        
        if self.current_char == '}':
            self.advance()
        
        return MapExpr(line=self.line_offset, pairs=pairs)
    
    def parse_ok_constructor(self) -> Expr:
        """Parse Ok(expr) constructor."""
        self.pos += 3  # consume "Ok("
        self.current_char = self.source[self.pos] if self.pos < len(self.source) else None
        
        value = self.parse_expression()
        
        if self.current_char == ')':
            self.advance()
        
        return OkExpr(line=self.line_offset, value=value)
    
    def parse_err_constructor(self) -> Expr:
        """Parse Err(expr) constructor."""
        self.pos += 4  # consume "Err("
        self.current_char = self.source[self.pos] if self.pos < len(self.source) else None
        
        value = self.parse_expression()
        
        if self.current_char == ')':
            self.advance()
        
        return ErrorExpr(line=self.line_offset, value=value)
    
    def parse_some_constructor(self) -> Expr:
        """Parse Some(expr) constructor."""
        self.pos += 5  # consume "Some("
        self.current_char = self.source[self.pos] if self.pos < len(self.source) else None
        
        value = self.parse_expression()
        
        if self.current_char == ')':
            self.advance()
        
        return SomeExpr(line=self.line_offset, value=value)
    
    def parse_variable_or_call(self) -> Expr:
        """Parse a variable reference, function call, or chained member/index access."""
        start = self.pos

        while self.current_char and (self.current_char.isalnum() or self.current_char == '_'):
            self.advance()

        name = self.source[start:self.pos]
        self.skip_whitespace()

        # Check if it's a function call
        if self.current_char == '(':
            self.advance()
            args = []

            self.skip_whitespace()
            while self.current_char and self.current_char != ')':
                if self.current_char == ',':
                    self.advance()
                    self.skip_whitespace()
                    continue

                arg = self.parse_expression()
                args.append(arg)
                self.skip_whitespace()

            if self.current_char == ')':
                self.advance()

            callee = VariableExpr(name=name, line=self.line_offset)
            expr: Expr = CallExpr(line=self.line_offset, callee=callee, args=args)

            # After a call, allow chained member access / indexing / call
            while True:
                self.skip_whitespace()
                if self.current_char == '.':
                    self.advance()
                    member_start = self.pos
                    while self.current_char and (self.current_char.isalnum() or self.current_char == '_'):
                        self.advance()
                    member = self.source[member_start:self.pos]
                    expr = MemberAccessExpr(line=self.line_offset, object=expr, member=member)
                elif self.current_char == '[':
                    self.advance()
                    index = self.parse_expression()
                    if self.current_char == ']':
                        self.advance()
                    expr = IndexExpr(line=self.line_offset, object=expr, index=index)
                elif self.current_char == '(':
                    self.advance()
                    args = []
                    self.skip_whitespace()
                    while self.current_char and self.current_char != ')':
                        if self.current_char == ',':
                            self.advance()
                            self.skip_whitespace()
                            continue
                        arg = self.parse_expression()
                        args.append(arg)
                        self.skip_whitespace()
                    if self.current_char == ')':
                        self.advance()
                    expr = CallExpr(line=self.line_offset, callee=expr, args=args)
                else:
                    break
            return expr

        # Start with a variable
        expr = VariableExpr(line=self.line_offset, name=name)

        # Allow chained member access / indexing / call
        while True:
            self.skip_whitespace()
            if self.current_char == '.':
                self.advance()
                member_start = self.pos
                while self.current_char and (self.current_char.isalnum() or self.current_char == '_'):
                    self.advance()
                member = self.source[member_start:self.pos]

                # Special case: model.complete(...) -> ModelCallExpr
                if name == "model" and member == "complete":
                    self.skip_whitespace()
                    if self.current_char == '(':
                        self.advance()  # consume (
                        self.skip_whitespace()
                        prompt = self.parse_expression()
                        self.skip_whitespace()
                        if self.current_char == ')':
                            self.advance()
                        return ModelCallExpr(line=self.line_offset, prompt=prompt)

                expr = MemberAccessExpr(line=self.line_offset, object=expr, member=member)
            elif self.current_char == '[':
                self.advance()
                index = self.parse_expression()
                if self.current_char == ']':
                    self.advance()
                expr = IndexExpr(line=self.line_offset, object=expr, index=index)
            elif self.current_char == '(':
                self.advance()
                args = []
                self.skip_whitespace()
                while self.current_char and self.current_char != ')':
                    if self.current_char == ',':
                        self.advance()
                        self.skip_whitespace()
                        continue
                    arg = self.parse_expression()
                    args.append(arg)
                    self.skip_whitespace()
                if self.current_char == ')':
                    self.advance()
                expr = CallExpr(line=self.line_offset, callee=expr, args=args)
            else:
                break

        return expr
    
    def parse_block(self) -> Expr:
        """Parse a block of expressions: { expr1; expr2; expr3 }."""
        if self.current_char != '{':
            return BlockExpr(line=self.line_offset, statements=[])
        
        self.advance()  # consume {
        statements = []
        
        self.skip_whitespace()
        while self.current_char and self.current_char != '}':
            if self.current_char == ';':
                self.advance()
                self.skip_whitespace()
                continue
            
            stmt = self.parse_expression()
            statements.append(stmt)
            self.skip_whitespace()
        
        if self.current_char == '}':
            self.advance()
        
        return BlockExpr(line=self.line_offset, statements=statements)

    def parse_par(self) -> ParExpr:
        """Parse parallel dispatch: par { expr1, expr2, ... }."""
        self.pos += 3  # consume "par"
        self.current_char = self.source[self.pos] if self.pos < len(self.source) else None
        self.skip_whitespace()

        if self.current_char != '{':
            return ParExpr(line=self.line_offset, expressions=[])

        self.advance()  # consume {
        expressions = []

        self.skip_whitespace()
        while self.current_char and self.current_char != '}':
            if self.current_char == ',':
                self.advance()
                self.skip_whitespace()
                continue

            expr = self.parse_expression()
            expressions.append(expr)
            self.skip_whitespace()

        if self.current_char == '}':
            self.advance()

        return ParExpr(line=self.line_offset, expressions=expressions)

    def parse_think_as(self) -> StructuredOutputExpr:
        """Parse structured output: think_as(Type, prompt_expr)."""
        self.pos += 8  # consume "think_as"
        self.current_char = self.source[self.pos] if self.pos < len(self.source) else None
        self.skip_whitespace()

        if self.current_char != '(':
            return StructuredOutputExpr(line=self.line_offset, type_str="Any", prompt=LiteralExpr(line=self.line_offset, value=None))

        self.advance()  # consume (
        self.skip_whitespace()

        # Parse type identifier (may include <>, {}, nested commas)
        type_start = self.pos
        if self.current_char == '{':
            # Record type: { field: Type, ... } — track brace depth
            brace_depth = 0
            while self.current_char:
                if self.current_char == '{':
                    brace_depth += 1
                elif self.current_char == '}':
                    brace_depth -= 1
                    if brace_depth == 0:
                        self.advance()
                        break
                self.advance()
        else:
            # Simple or generic type: Str, List<Int>, Option<Str>, etc.
            angle_depth = 0
            while self.current_char:
                if self.current_char == '<':
                    angle_depth += 1
                elif self.current_char == '>':
                    angle_depth -= 1
                elif self.current_char == ',' and angle_depth == 0:
                    break
                self.advance()
        type_str = self.source[type_start:self.pos].strip()

        if self.current_char == ',':
            self.advance()
            self.skip_whitespace()

        # Parse prompt expression
        prompt = self.parse_expression()
        self.skip_whitespace()

        if self.current_char == ')':
            self.advance()

        return StructuredOutputExpr(line=self.line_offset, type_str=type_str, prompt=prompt)

    def parse_if(self) -> IfExpr:
        """Parse if expression: if cond { then } else { else }."""
        self.pos += 2  # consume "if"
        self.current_char = self.source[self.pos] if self.pos < len(self.source) else None
        self.skip_whitespace()

        condition = self.parse_expression()
        self.skip_whitespace()

        then_branch = self.parse_block()
        self.skip_whitespace()

        else_branch = None
        if self.current_char == 'e' and self.source.startswith("else", self.pos):
            self.pos += 4
            self.current_char = self.source[self.pos] if self.pos < len(self.source) else None
            self.skip_whitespace()
            else_branch = self.parse_block()

        return IfExpr(
            line=self.line_offset,
            condition=condition,
            then_branch=then_branch,
            else_branch=else_branch,
        )

    def parse_for(self) -> ForExpr:
        """Parse for-in loop: for var in iterable { body }."""
        self.pos += 3  # consume "for"
        self.current_char = self.source[self.pos] if self.pos < len(self.source) else None
        self.skip_whitespace()

        # Parse variable name
        var_start = self.pos
        while self.current_char and (self.current_char.isalnum() or self.current_char == '_'):
            self.advance()
        var_name = self.source[var_start:self.pos]
        self.skip_whitespace()

        # Expect 'in'
        if self.source.startswith("in", self.pos):
            self.pos += 2
            self.current_char = self.source[self.pos] if self.pos < len(self.source) else None
        self.skip_whitespace()

        iterable = self.parse_expression()
        self.skip_whitespace()

        body = self.parse_block()

        return ForExpr(
            line=self.line_offset,
            var_name=var_name,
            iterable=iterable,
            body=body,
        )

    def parse_match(self) -> MatchExpr:
        """Parse match expression: match value { pat => expr, ... }."""
        self.pos += 5  # consume "match"
        self.current_char = self.source[self.pos] if self.pos < len(self.source) else None
        self.skip_whitespace()

        value = self.parse_expression()
        self.skip_whitespace()

        arms: list[MatchArm] = []
        if self.current_char == '{':
            self.advance()  # consume {
            self.skip_whitespace()
            while self.current_char and self.current_char != '}':
                if self.current_char == ',':
                    self.advance()
                    self.skip_whitespace()
                    continue

                pattern = self.parse_expression()
                self.skip_whitespace()

                guard = None
                if self.current_char == 'i' and self.source[self.pos:self.pos + 2] == 'if':
                    self.advance_by(2)  # consume 'if'
                    self.skip_whitespace()
                    guard = self.parse_expression()
                    self.skip_whitespace()

                if self.current_char == '=' and self.peek() == '>':
                    self.advance()
                    self.advance()
                    self.skip_whitespace()

                arm_expr = self.parse_expression()
                arms.append(MatchArm(pattern=pattern, body=arm_expr, guard=guard))
                self.skip_whitespace()

            if self.current_char == '}':
                self.advance()

        return MatchExpr(line=self.line_offset, value=value, arms=arms)

    def parse_let(self) -> LetExpr:
        """Parse let binding: let name = value in body."""
        self.pos += 3  # consume "let"
        self.current_char = self.source[self.pos] if self.pos < len(self.source) else None
        self.skip_whitespace()

        name_start = self.pos
        while self.current_char and (self.current_char.isalnum() or self.current_char == '_'):
            self.advance()
        name = self.source[name_start:self.pos]
        self.skip_whitespace()

        if self.current_char == '=':
            self.advance()
            self.skip_whitespace()

        value = self.parse_expression()
        self.skip_whitespace()

        if self.source.startswith("in", self.pos):
            self.pos += 2
            self.current_char = self.source[self.pos] if self.pos < len(self.source) else None
            self.skip_whitespace()
            body = self.parse_expression()
        else:
            # Standalone let without 'in': body is a no-op placeholder
            body = NoneExpr(line=self.line_offset)

        return LetExpr(line=self.line_offset, name=name, value=value, body=body)

    def parse_return(self) -> ReturnExpr:
        """Parse return statement: return expr."""
        self.pos += 6  # consume "return"
        self.current_char = self.source[self.pos] if self.pos < len(self.source) else None
        self.skip_whitespace()

        value = self.parse_expression()
        return ReturnExpr(line=self.line_offset, value=value, is_ok=True)

    def parse_act(self) -> ActExpr:
        """Parse act expression: act ToolName(key: expr, ...)."""
        self.pos += 3  # consume "act"
        self.current_char = self.source[self.pos] if self.pos < len(self.source) else None
        self.skip_whitespace()

        # Parse tool name (supports dot-separated names like KnowledgeBase.retrieve)
        name_start = self.pos
        while self.current_char and (self.current_char.isalnum() or self.current_char == '_' or self.current_char == '.'):
            self.advance()
        tool_name = self.source[name_start:self.pos]
        self.skip_whitespace()

        args: list[tuple[str, Expr]] = []
        if self.current_char == '(':
            self.advance()  # consume (
            self.skip_whitespace()

            while self.current_char and self.current_char != ')':
                if self.current_char == ',':
                    self.advance()
                    self.skip_whitespace()
                    continue

                # Parse key
                key_start = self.pos
                while self.current_char and (self.current_char.isalnum() or self.current_char == '_'):
                    self.advance()
                key = self.source[key_start:self.pos]
                self.skip_whitespace()

                if self.current_char == ':':
                    self.advance()
                    self.skip_whitespace()

                # Parse value expression
                val = self.parse_expression()
                args.append((key, val))
                self.skip_whitespace()

            if self.current_char == ')':
                self.advance()

        return ActExpr(line=self.line_offset, tool_name=tool_name, args=args)

    def parse_delegate(self) -> DelegateExpr:
        """Parse delegate expression: delegate AgentName(key: expr, ...)."""
        self.pos += 8  # consume "delegate"
        self.current_char = self.source[self.pos] if self.pos < len(self.source) else None
        self.skip_whitespace()

        # Parse agent name
        name_start = self.pos
        while self.current_char and (self.current_char.isalnum() or self.current_char == '_'):
            self.advance()
        agent_name = self.source[name_start:self.pos]
        self.skip_whitespace()

        args: list[tuple[str, Expr]] = []
        if self.current_char == '(':
            self.advance()  # consume (
            self.skip_whitespace()

            while self.current_char and self.current_char != ')':
                if self.current_char == ',':
                    self.advance()
                    self.skip_whitespace()
                    continue

                # Parse key
                key_start = self.pos
                while self.current_char and (self.current_char.isalnum() or self.current_char == '_'):
                    self.advance()
                key = self.source[key_start:self.pos]
                self.skip_whitespace()

                if self.current_char == ':':
                    self.advance()
                    self.skip_whitespace()

                # Parse value expression
                val = self.parse_expression()
                args.append((key, val))
                self.skip_whitespace()

            if self.current_char == ')':
                self.advance()

        return DelegateExpr(line=self.line_offset, agent_name=agent_name, args=args)

    def parse_store(self) -> StoreExpr:
        """Parse store expression: store target = value."""
        self.pos += 5  # consume "store"
        self.current_char = self.source[self.pos] if self.pos < len(self.source) else None
        self.skip_whitespace()

        # Parse target expression without assignment (e.g. memory.working["key"])
        target = self.parse_logical_or()
        self.skip_whitespace()

        # Expect =
        if self.current_char == '=':
            self.advance()
            self.skip_whitespace()

        # Parse value expression
        value = self.parse_expression()

        return StoreExpr(line=self.line_offset, target=target, value=value)

    def parse_think(self) -> ThinkExpr:
        """Parse think expression: think "message"."""
        self.pos += 5  # consume "think"
        self.current_char = self.source[self.pos] if self.pos < len(self.source) else None
        self.skip_whitespace()

        message = self.parse_expression()
        return ThinkExpr(line=self.line_offset, message=message)

    def parse_observe(self) -> ObserveExpr:
        """Parse observe expression: observe name: value_expr."""
        self.pos += 7  # consume "observe"
        self.current_char = self.source[self.pos] if self.pos < len(self.source) else None
        self.skip_whitespace()

        # Parse identifier name
        name_start = self.pos
        while self.current_char and (self.current_char.isalnum() or self.current_char == '_'):
            self.advance()
        name = self.source[name_start:self.pos]
        self.skip_whitespace()

        if self.current_char == ':':
            self.advance()
            self.skip_whitespace()

        value = self.parse_expression()
        return ObserveExpr(line=self.line_offset, name=name, value=value)


def parse_expression(source: str, line_offset: int = 0) -> Expr:
    """Parse an AXON expression from source text.
    
    Args:
        source: The source text to parse
        line_offset: Line number offset for error reporting
        
    Returns:
        The parsed expression AST
    """
    parser = ExpressionParser(source, line_offset)
    return parser.parse()
