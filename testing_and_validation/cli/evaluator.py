import io
import time
from contextlib import redirect_stdout
from dataclasses import dataclass
from typing import Dict, List

from parser import (
    AssertStmt,
    Binary,
    Block,
    BoolLit,
    Call,
    ExprStmt,
    FunctionDef,
    Ident,
    IfStmt,
    IntLit,
    PrintStmt,
    Program,
    ReturnStmt,
    Unary,
)


class RuntimeMinilangError(Exception):
    pass


class AssertionFailure(Exception):
    def __init__(self, line: int):
        super().__init__(f"assertion failed at line {line}")
        self.line = line


class _Return(Exception):
    def __init__(self, value):
        self.value = value


@dataclass
class TestResult:
    name: str
    passed: bool
    message: str = ""
    failure_type: str = ""  # "failure" or "error"
    duration_s: float = 0.0
    stdout: str = ""


class Interpreter:
    def __init__(self, program: Program):
        self.functions: Dict[str, FunctionDef] = {f.name: f for f in program.functions}
        self.program = program

    def run_tests(self, shard_index: int = 0, shard_count: int = 1) -> List[TestResult]:
        results: List[TestResult] = []
        for i, test in enumerate(self.program.tests):
            if i % shard_count != shard_index:
                continue
            buf = io.StringIO()
            start = time.perf_counter()
            passed = True
            message = ""
            failure_type = ""
            try:
                with redirect_stdout(buf):
                    self.exec_block(test.body, {})
            except AssertionFailure as e:
                passed = False
                message = str(e)
                failure_type = "failure"
            except RuntimeMinilangError as e:
                passed = False
                message = f"runtime error: {e}"
                failure_type = "error"
            duration = time.perf_counter() - start
            captured = buf.getvalue()
            print(captured, end="")
            results.append(TestResult(
                name=test.name,
                passed=passed,
                message=message,
                failure_type=failure_type,
                duration_s=duration,
                stdout=captured,
            ))
        return results

    def exec_block(self, block: Block, env: Dict[str, object]) -> None:
        for stmt in block.statements:
            self.exec_stmt(stmt, env)

    def exec_stmt(self, stmt, env: Dict[str, object]) -> None:
        if isinstance(stmt, ReturnStmt):
            raise _Return(self.eval_expr(stmt.expr, env))
        if isinstance(stmt, AssertStmt):
            value = self.eval_expr(stmt.expr, env)
            if not self._truthy(value):
                raise AssertionFailure(stmt.line)
            return
        if isinstance(stmt, PrintStmt):
            value = self.eval_expr(stmt.expr, env)
            print(self._format(value))
            return
        if isinstance(stmt, IfStmt):
            cond = self.eval_expr(stmt.cond, env)
            if self._truthy(cond):
                self.exec_block(stmt.then_block, env)
            elif stmt.else_block is not None:
                self.exec_block(stmt.else_block, env)
            return
        if isinstance(stmt, ExprStmt):
            self.eval_expr(stmt.expr, env)
            return
        raise RuntimeMinilangError(f"unknown statement {type(stmt).__name__}")

    def eval_expr(self, expr, env: Dict[str, object]):
        if isinstance(expr, IntLit):
            return expr.value
        if isinstance(expr, BoolLit):
            return expr.value
        if isinstance(expr, Ident):
            if expr.name not in env:
                raise RuntimeMinilangError(f"undefined variable {expr.name!r}")
            return env[expr.name]
        if isinstance(expr, Call):
            return self.eval_call(expr, env)
        if isinstance(expr, Unary):
            operand = self.eval_expr(expr.operand, env)
            if expr.op == "-":
                if not isinstance(operand, int) or isinstance(operand, bool):
                    raise RuntimeMinilangError("unary '-' requires integer")
                return -operand
            if expr.op == "!":
                return not self._truthy(operand)
            raise RuntimeMinilangError(f"unknown unary op {expr.op}")
        if isinstance(expr, Binary):
            return self.eval_binary(expr, env)
        raise RuntimeMinilangError(f"unknown expression {type(expr).__name__}")

    def eval_call(self, call: Call, env: Dict[str, object]):
        fn = self.functions.get(call.name)
        if fn is None:
            raise RuntimeMinilangError(f"undefined function {call.name!r}")
        if len(call.args) != len(fn.params):
            raise RuntimeMinilangError(
                f"function {call.name!r} expects {len(fn.params)} args, got {len(call.args)}"
            )
        args = [self.eval_expr(a, env) for a in call.args]
        new_env: Dict[str, object] = dict(zip(fn.params, args))
        try:
            self.exec_block(fn.body, new_env)
        except _Return as r:
            return r.value
        return 0

    def eval_binary(self, expr: Binary, env: Dict[str, object]):
        op = expr.op
        if op == "&":
            left = self.eval_expr(expr.left, env)
            if not self._truthy(left):
                return False
            return self._truthy(self.eval_expr(expr.right, env))
        if op == "|":
            left = self.eval_expr(expr.left, env)
            if self._truthy(left):
                return True
            return self._truthy(self.eval_expr(expr.right, env))

        left = self.eval_expr(expr.left, env)
        right = self.eval_expr(expr.right, env)

        if op in ("+", "-", "*", "/", "%"):
            if not (isinstance(left, int) and isinstance(right, int)) or isinstance(left, bool) or isinstance(right, bool):
                raise RuntimeMinilangError(f"arithmetic '{op}' requires integers")
            if op == "+":
                return left + right
            if op == "-":
                return left - right
            if op == "*":
                return left * right
            if op == "/":
                if right == 0:
                    raise RuntimeMinilangError("division by zero")
                q = left // right
                if (left % right != 0) and ((left < 0) != (right < 0)):
                    q += 1
                return q
            if op == "%":
                if right == 0:
                    raise RuntimeMinilangError("modulo by zero")
                q = left // right
                if (left % right != 0) and ((left < 0) != (right < 0)):
                    q += 1
                return left - q * right
        if op in ("==", "!="):
            eq = left == right and type(left) is type(right)
            return eq if op == "==" else not eq
        if op in ("<", ">", "<=", ">="):
            if isinstance(left, bool) or isinstance(right, bool) or not isinstance(left, int) or not isinstance(right, int):
                raise RuntimeMinilangError(f"relational '{op}' requires integers")
            if op == "<":
                return left < right
            if op == ">":
                return left > right
            if op == "<=":
                return left <= right
            if op == ">=":
                return left >= right
        raise RuntimeMinilangError(f"unknown binary op {op}")

    @staticmethod
    def _truthy(value) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value != 0
        return bool(value)

    @staticmethod
    def _format(value) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)
