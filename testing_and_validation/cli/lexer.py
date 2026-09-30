from dataclasses import dataclass
from typing import List


KEYWORDS = {"fn", "test", "return", "assert", "print", "if", "else", "true", "false"}


@dataclass
class Token:
    kind: str
    value: object
    line: int
    col: int
    offset: int = 0
    length: int = 0


class LexError(Exception):
    pass


def tokenize(source: str) -> List[Token]:
    tokens: List[Token] = []
    i = 0
    line = 1
    col = 1
    n = len(source)

    def advance(k: int = 1) -> None:
        nonlocal i, col
        i += k
        col += k

    while i < n:
        c = source[i]

        if c == "\n":
            i += 1
            line += 1
            col = 1
            continue
        if c in " \t\r":
            advance()
            continue

        if c == "/" and i + 1 < n and source[i + 1] == "/":
            while i < n and source[i] != "\n":
                i += 1
            continue

        start_line, start_col = line, col

        if c.isalpha() or c == "_":
            j = i
            while j < n and (source[j].isalnum() or source[j] == "_"):
                j += 1
            word = source[i:j]
            kind = word if word in KEYWORDS else "IDENT"
            tokens.append(Token(kind, word, start_line, start_col, i, j - i))
            col += j - i
            i = j
            continue

        if c.isdigit():
            j = i
            while j < n and source[j].isdigit():
                j += 1
            tokens.append(Token("INT", int(source[i:j]), start_line, start_col, i, j - i))
            col += j - i
            i = j
            continue

        if c == '"':
            j = i + 1
            buf = []
            while j < n and source[j] != '"':
                if source[j] == "\\" and j + 1 < n:
                    esc = source[j + 1]
                    buf.append({"n": "\n", "t": "\t", "\\": "\\", '"': '"'}.get(esc, esc))
                    j += 2
                elif source[j] == "\n":
                    raise LexError(f"unterminated string at line {start_line}")
                else:
                    buf.append(source[j])
                    j += 1
            if j >= n:
                raise LexError(f"unterminated string at line {start_line}")
            tokens.append(Token("STRING", "".join(buf), start_line, start_col, i, (j + 1) - i))
            col += (j + 1) - i
            i = j + 1
            continue

        two = source[i:i + 2]
        if two in ("==", "!=", "<=", ">="):
            tokens.append(Token(two, two, start_line, start_col, i, 2))
            advance(2)
            continue

        if c in "+-*/%<>!&|(){},;":
            tokens.append(Token(c, c, start_line, start_col, i, 1))
            advance()
            continue

        raise LexError(f"unexpected character {c!r} at line {line} col {col}")

    tokens.append(Token("EOF", None, line, col, n, 0))
    return tokens
