from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple

from lexer import Token, tokenize
from parser import parse, ParseError


MUTATIONS: Dict[str, List[str]] = {
    "+": ["-", "*"],
    "-": ["+"],
    "*": ["/", "+"],
    "/": ["*", "%"],
    "%": ["/"],
    "==": ["!="],
    "!=": ["=="],
    "<": [">=", "<="],
    ">": ["<=", ">="],
    "<=": [">", "<"],
    ">=": ["<", ">"],
    "&": ["|"],
    "|": ["&"],
    "true": ["false"],
    "false": ["true"],
}


@dataclass
class Mutation:
    id: str
    operator: str
    original: str
    replacement: str
    offset: int
    length: int
    line: int
    col: int

    def to_dict(self) -> dict:
        return asdict(self)


def _test_block_ranges(tokens: List[Token]) -> List[Tuple[int, int]]:
    ranges: List[Tuple[int, int]] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.kind == "test":
            j = i + 1
            while j < len(tokens) and tokens[j].kind != "{":
                j += 1
            if j >= len(tokens):
                break
            depth = 0
            start_offset = tokens[j].offset
            k = j
            while k < len(tokens):
                if tokens[k].kind == "{":
                    depth += 1
                elif tokens[k].kind == "}":
                    depth -= 1
                    if depth == 0:
                        end_offset = tokens[k].offset + tokens[k].length
                        ranges.append((start_offset, end_offset))
                        i = k
                        break
                k += 1
        i += 1
    return ranges


def _in_any_range(offset: int, ranges: List[Tuple[int, int]]) -> bool:
    for start, end in ranges:
        if start <= offset < end:
            return True
    return False


def list_mutations(source: str) -> List[Mutation]:
    tokens = tokenize(source)
    skip_ranges = _test_block_ranges(tokens)
    mutations: List[Mutation] = []
    seq = 0
    for tok in tokens:
        if tok.kind == "EOF":
            continue
        if _in_any_range(tok.offset, skip_ranges):
            continue
        original = source[tok.offset:tok.offset + tok.length]
        replacements = MUTATIONS.get(original)
        if not replacements:
            continue
        for replacement in replacements:
            candidate = source[:tok.offset] + replacement + source[tok.offset + tok.length:]
            try:
                parse(tokenize(candidate))
            except ParseError:
                continue
            mutations.append(
                Mutation(
                    id=f"m{seq:04d}",
                    operator=f"{original}->{replacement}",
                    original=original,
                    replacement=replacement,
                    offset=tok.offset,
                    length=tok.length,
                    line=tok.line,
                    col=tok.col,
                )
            )
            seq += 1
    return mutations


def apply_mutation(source: str, mutation: dict) -> str:
    offset = mutation["offset"]
    length = mutation["length"]
    original = mutation["original"]
    replacement = mutation["replacement"]
    actual = source[offset:offset + length]
    if actual != original:
        raise ValueError(
            f"mutation offset {offset} expected {original!r} but source has {actual!r}"
        )
    return source[:offset] + replacement + source[offset + length:]
