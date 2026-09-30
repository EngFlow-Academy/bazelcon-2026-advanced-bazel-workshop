from dataclasses import dataclass, field
from typing import List, Optional, Union

from lexer import Token


class ParseError(Exception):
    pass


@dataclass
class IntLit:
    value: int


@dataclass
class BoolLit:
    value: bool


@dataclass
class Ident:
    name: str


@dataclass
class Call:
    name: str
    args: List["Expr"]


@dataclass
class Unary:
    op: str
    operand: "Expr"


@dataclass
class Binary:
    op: str
    left: "Expr"
    right: "Expr"


Expr = Union[IntLit, BoolLit, Ident, Call, Unary, Binary]


@dataclass
class ReturnStmt:
    expr: Expr


@dataclass
class AssertStmt:
    expr: Expr
    line: int


@dataclass
class PrintStmt:
    expr: Expr


@dataclass
class IfStmt:
    cond: Expr
    then_block: "Block"
    else_block: Optional["Block"]


@dataclass
class ExprStmt:
    expr: Expr


Stmt = Union[ReturnStmt, AssertStmt, PrintStmt, IfStmt, ExprStmt]


@dataclass
class Block:
    statements: List[Stmt] = field(default_factory=list)


@dataclass
class FunctionDef:
    name: str
    params: List[str]
    body: Block


@dataclass
class TestDef:
    name: str
    body: Block


@dataclass
class Program:
    functions: List[FunctionDef] = field(default_factory=list)
    tests: List[TestDef] = field(default_factory=list)


class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def peek(self, offset: int = 0) -> Token:
        return self.tokens[self.pos + offset]

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def expect(self, kind: str) -> Token:
        tok = self.peek()
        if tok.kind != kind:
            raise ParseError(
                f"expected {kind} but got {tok.kind} ({tok.value!r}) at line {tok.line}"
            )
        return self.advance()

    def match(self, *kinds: str) -> bool:
        if self.peek().kind in kinds:
            self.advance()
            return True
        return False

    def parse_program(self) -> Program:
        prog = Program()
        while self.peek().kind != "EOF":
            if self.peek().kind == "fn":
                prog.functions.append(self.parse_function())
            elif self.peek().kind == "test":
                prog.tests.append(self.parse_test())
            else:
                tok = self.peek()
                raise ParseError(
                    f"expected fn or test at line {tok.line}, got {tok.kind}"
                )
        return prog

    def parse_function(self) -> FunctionDef:
        self.expect("fn")
        name = self.expect("IDENT").value
        self.expect("(")
        params: List[str] = []
        if self.peek().kind != ")":
            params.append(self.expect("IDENT").value)
            while self.match(","):
                params.append(self.expect("IDENT").value)
        self.expect(")")
        body = self.parse_block()
        return FunctionDef(name, params, body)

    def parse_test(self) -> TestDef:
        self.expect("test")
        name = self.expect("STRING").value
        body = self.parse_block()
        return TestDef(name, body)

    def parse_block(self) -> Block:
        self.expect("{")
        block = Block()
        while self.peek().kind != "}":
            block.statements.append(self.parse_statement())
        self.expect("}")
        return block

    def parse_statement(self) -> Stmt:
        tok = self.peek()
        if tok.kind == "return":
            self.advance()
            expr = self.parse_expression()
            self.expect(";")
            return ReturnStmt(expr)
        if tok.kind == "assert":
            self.advance()
            line = tok.line
            expr = self.parse_expression()
            self.expect(";")
            return AssertStmt(expr, line)
        if tok.kind == "print":
            self.advance()
            expr = self.parse_expression()
            self.expect(";")
            return PrintStmt(expr)
        if tok.kind == "if":
            return self.parse_if()
        expr = self.parse_expression()
        self.expect(";")
        return ExprStmt(expr)

    def parse_if(self) -> IfStmt:
        self.expect("if")
        self.expect("(")
        cond = self.parse_expression()
        self.expect(")")
        then_block = self.parse_block()
        else_block = None
        if self.match("else"):
            else_block = self.parse_block()
        return IfStmt(cond, then_block, else_block)

    def parse_expression(self) -> Expr:
        return self.parse_logic_or()

    def parse_logic_or(self) -> Expr:
        left = self.parse_logic_and()
        while self.peek().kind == "|":
            self.advance()
            right = self.parse_logic_and()
            left = Binary("|", left, right)
        return left

    def parse_logic_and(self) -> Expr:
        left = self.parse_relational()
        while self.peek().kind == "&":
            self.advance()
            right = self.parse_relational()
            left = Binary("&", left, right)
        return left

    def parse_relational(self) -> Expr:
        left = self.parse_additive()
        if self.peek().kind in ("==", "!=", "<", ">", "<=", ">="):
            op = self.advance().kind
            right = self.parse_additive()
            return Binary(op, left, right)
        return left

    def parse_additive(self) -> Expr:
        left = self.parse_multiplicative()
        while self.peek().kind in ("+", "-"):
            op = self.advance().kind
            right = self.parse_multiplicative()
            left = Binary(op, left, right)
        return left

    def parse_multiplicative(self) -> Expr:
        left = self.parse_unary()
        while self.peek().kind in ("*", "/", "%"):
            op = self.advance().kind
            right = self.parse_unary()
            left = Binary(op, left, right)
        return left

    def parse_unary(self) -> Expr:
        if self.peek().kind in ("!", "-"):
            op = self.advance().kind
            operand = self.parse_primary()
            return Unary(op, operand)
        return self.parse_primary()

    def parse_primary(self) -> Expr:
        tok = self.peek()
        if tok.kind == "INT":
            self.advance()
            return IntLit(tok.value)
        if tok.kind == "true":
            self.advance()
            return BoolLit(True)
        if tok.kind == "false":
            self.advance()
            return BoolLit(False)
        if tok.kind == "(":
            self.advance()
            expr = self.parse_expression()
            self.expect(")")
            return expr
        if tok.kind == "IDENT":
            self.advance()
            if self.peek().kind == "(":
                self.advance()
                args: List[Expr] = []
                if self.peek().kind != ")":
                    args.append(self.parse_expression())
                    while self.match(","):
                        args.append(self.parse_expression())
                self.expect(")")
                return Call(tok.value, args)
            return Ident(tok.value)
        raise ParseError(f"unexpected token {tok.kind} ({tok.value!r}) at line {tok.line}")


def parse(tokens: List[Token]) -> Program:
    return Parser(tokens).parse_program()
