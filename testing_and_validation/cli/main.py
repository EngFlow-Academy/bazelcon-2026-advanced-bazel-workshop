import argparse
import json
import os
import sys

from lexer import LexError, tokenize
from parser import ParseError, parse
from evaluator import Interpreter, TestResult
from junit import build_junit_xml
from mutator import apply_mutation, list_mutations


def _read_source(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read(), 0
    except OSError as e:
        print(f"error: cannot read {path}: {e}", file=sys.stderr)
        return None, 2


def _write_junit(path: str, suite_name: str, results) -> None:
    xml_bytes = build_junit_xml(suite_name, results)
    with open(path, "wb") as f:
        f.write(xml_bytes)


def _mutation_summary(mutation_json_path: str, source_path: str) -> str:
    try:
        with open(mutation_json_path, "r", encoding="utf-8") as f:
            m = json.load(f)
    except (OSError, json.JSONDecodeError):
        return f"survived: {source_path}"
    return (
        f"survived: {m.get('id', '?')} {m.get('operator', '?')} "
        f"at {os.path.basename(source_path)}:{m.get('line', '?')}:{m.get('col', '?')}"
    )


def _load_program(path: str, xml_path: str):
    """Read + parse a .mini file. Returns (program, exit_code)."""
    suite_name = os.path.basename(path)
    source, err = _read_source(path)
    if source is None:
        return None, err
    try:
        tokens = tokenize(source)
        return parse(tokens), 0
    except LexError as e:
        message = f"lex error: {e}"
    except ParseError as e:
        message = f"parse error: {e}"
    print(message, file=sys.stderr)
    if xml_path:
        err_result = TestResult(name=suite_name, passed=False, message=message,
                                failure_type="error")
        _write_junit(xml_path, suite_name, [err_result])
    return None, 2


def cmd_test(path: str, shard_index: int, shard_count: int, junit_xml: str) -> int:
    if shard_count < 1:
        print(f"error: --shard-count must be >= 1 (got {shard_count})", file=sys.stderr)
        return 2
    if not (0 <= shard_index < shard_count):
        print(
            f"error: --shard-index must be in [0, {shard_count}) (got {shard_index})",
            file=sys.stderr,
        )
        return 2

    xml_path = junit_xml
    program, err = _load_program(path, xml_path)
    if program is None:
        return err

    interpreter = Interpreter(program)
    results = interpreter.run_tests(shard_index=shard_index, shard_count=shard_count)

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    if shard_count > 1:
        print(f"shard {shard_index + 1}/{shard_count}: {len(results)} of {len(program.tests)} tests")
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        line = f"[{status}] {r.name}"
        if not r.passed and r.message:
            line += f" — {r.message}"
        print(line)
    print(f"\n{passed} passed, {failed} failed, {len(results)} total")

    if xml_path:
        _write_junit(xml_path, os.path.basename(path), results)

    return 0 if failed == 0 else 1


def cmd_mutate_test(path: str, junit_xml: str, mutation_json: str) -> int:
    """Run tests expecting at least one to fail (mutation-check mode)."""
    xml_path = junit_xml
    program, _err = _load_program(path, xml_path)
    if program is None:
        # Lex/parse failure of a mutated program still counts as "killed".
        return 0

    interpreter = Interpreter(program)
    results = interpreter.run_tests()
    failed = sum(1 for r in results if not r.passed)

    if xml_path:
        _write_junit(xml_path, os.path.basename(path), results)

    if failed == 0:
        if mutation_json:
            print(_mutation_summary(mutation_json, path), file=sys.stderr)
        else:
            print("mutation survived: expected at least one failure but all tests passed",
                  file=sys.stderr)
        return 1
    return 0


def cmd_mutate_list(path: str, out_dir: str) -> int:
    source, err = _read_source(path)
    if source is None:
        return err

    try:
        mutations = list_mutations(source)
    except LexError as e:
        print(f"lex error: {e}", file=sys.stderr)
        return 2

    payload = [m.to_dict() for m in mutations]
    try:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "mutations.json"), "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        for m in payload:
            d = os.path.join(out_dir, m["id"])
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "mutation.json"), "w", encoding="utf-8") as f:
                json.dump(m, f, indent=2)
    except OSError as e:
        print(f"error: cannot write to {out_dir}: {e}", file=sys.stderr)
        return 2
    print(f"wrote {len(mutations)} mutation(s) to {out_dir}", file=sys.stderr)
    return 0


def cmd_mutate_patch(mutation_path: str, source_path: str, dest_path: str) -> int:
    try:
        with open(mutation_path, "r", encoding="utf-8") as f:
            mutation = json.load(f)
    except OSError as e:
        print(f"error: cannot read {mutation_path}: {e}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as e:
        print(f"error: invalid JSON in {mutation_path}: {e}", file=sys.stderr)
        return 2

    source, err = _read_source(source_path)
    if source is None:
        return err

    try:
        mutated = apply_mutation(source, mutation)
    except (KeyError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    try:
        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(mutated)
    except OSError as e:
        print(f"error: cannot write {dest_path}: {e}", file=sys.stderr)
        return 2
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="minilang", description="minilang CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    test_p = sub.add_parser("test", help="run tests defined in a minilang program")
    test_p.add_argument("file", help="path to a .mini source file")
    test_p.add_argument("--shard-count", type=int, default=1,
                        help="total number of shards to split tests across (default: 1)")
    test_p.add_argument("--shard-index", type=int, default=0,
                        help="0-based index of the shard to run (default: 0)")
    test_p.add_argument("--junit-xml", default="",
                        help="write a JUnit-compatible XML report to this path")

    mutate_p = sub.add_parser("mutate", help="mutation testing helpers")
    mutate_sub = mutate_p.add_subparsers(dest="mutate_command", required=True)

    list_p = mutate_sub.add_parser("list", help="list all possible mutations of a program")
    list_p.add_argument("file", help="path to a .mini source file")
    list_p.add_argument("-o", "--out-dir", required=True,
                        help="output directory (will contain mutations.json plus one subdirectory per mutation)")

    patch_p = mutate_sub.add_parser("patch", help="patch a source file with a single mutation")
    patch_p.add_argument("--mutation", required=True,
                         help="path to a JSON file describing a single mutation")
    patch_p.add_argument("--source", required=True,
                         help="path to the original .mini source file")
    patch_p.add_argument("--output", required=True,
                         help="path to write the mutated source")

    mtest_p = mutate_sub.add_parser("test",
                                    help="run tests on a mutated program; succeeds iff at least one test fails (i.e. the mutation is killed)")
    mtest_p.add_argument("file", help="path to a mutated .mini source file")
    mtest_p.add_argument("--junit-xml", default="",
                         help="write a JUnit-compatible XML report to this path")
    mtest_p.add_argument("--mutation-json", default="",
                         help="on survival, print a compact one-line summary built from this mutation JSON")

    args = parser.parse_args(argv)

    if args.command == "test":
        return cmd_test(args.file, args.shard_index, args.shard_count, args.junit_xml)
    if args.command == "mutate":
        if args.mutate_command == "list":
            return cmd_mutate_list(args.file, args.out_dir)
        if args.mutate_command == "patch":
            return cmd_mutate_patch(args.mutation, args.source, args.output)
        if args.mutate_command == "test":
            return cmd_mutate_test(args.file, args.junit_xml, args.mutation_json)
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
