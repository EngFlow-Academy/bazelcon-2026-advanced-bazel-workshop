import socket
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Iterable

from evaluator import TestResult


def build_junit_xml(suite_name: str, results: Iterable[TestResult]) -> bytes:
    results = list(results)
    tests = len(results)
    failures = sum(1 for r in results if not r.passed and r.failure_type == "failure")
    errors = sum(1 for r in results if not r.passed and r.failure_type == "error")
    total_time = sum(r.duration_s for r in results)

    suites = ET.Element("testsuites")
    suite = ET.SubElement(suites, "testsuite", {
        "name": suite_name,
        "tests": str(tests),
        "failures": str(failures),
        "errors": str(errors),
        "time": f"{total_time:.6f}",
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", ""),
        "hostname": socket.gethostname(),
    })

    for r in results:
        case = ET.SubElement(suite, "testcase", {
            "name": r.name,
            "classname": suite_name,
            "time": f"{r.duration_s:.6f}",
        })
        if not r.passed:
            tag = "failure" if r.failure_type == "failure" else "error"
            fail = ET.SubElement(case, tag, {
                "message": r.message,
                "type": r.failure_type or "error",
            })
            fail.text = r.message
        if r.stdout:
            out = ET.SubElement(case, "system-out")
            out.text = r.stdout

    ET.indent(suites, space="  ")
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(suites, encoding="utf-8")
