#!/usr/bin/env python3
"""Build the 'Advanced Bazel: Testing & Validation' workshop deck.

Content mirrors slides/WORKSHOP.md.
"""

import argparse

from pptx import Presentation
from pptx.util import Emu, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from lxml import etree

_parser = argparse.ArgumentParser(description=__doc__)
_parser.add_argument("--template", required=True, help="Input .pptx template")
_parser.add_argument("--workshop-md", required=True,
                     help="Path to WORKSHOP.md (bundled as input for provenance)")
_parser.add_argument("--output", required=True, help="Output .pptx path")
_args = _parser.parse_args()

TEMPLATE = _args.template
OUTPUT = _args.output

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"

WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BRIGHT_GREEN = RGBColor(0x7E, 0xC4, 0x74)
CODE_BG = RGBColor(0x0B, 0x2E, 0x14)
CODE_TEXT = RGBColor(0xF5, 0xF5, 0xF5)


def clear_deck(prs):
    sldIdLst = prs.slides._sldIdLst
    rId_to_drop = []
    for sldId in list(sldIdLst):
        rId_to_drop.append(sldId.get(
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"))
        sldIdLst.remove(sldId)
    part = prs.part
    for rId in rId_to_drop:
        try:
            part.drop_rel(rId)
        except Exception:
            pass


def clear_tf(tf):
    txBody = tf._txBody
    for p in txBody.findall(f"{{{A_NS}}}p"):
        txBody.remove(p)
    etree.SubElement(txBody, f"{{{A_NS}}}p")


def set_run(run, size=None, bold=None, color=None, font="Arial", italic=None):
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if italic is not None:
        run.font.italic = italic
    if color is not None:
        run.font.color.rgb = color
    if font is not None:
        run.font.name = font


LEVEL_INDENT_EMU = {
    0: (457200, -342900),
    1: (914400, -342900),
    2: (1371600, -342900),
}


def add_paragraph(tf, text, *, size=18, bold=False, color=WHITE,
                  level=0, bullet=True, bullet_color=None,
                  align=None, italic=False, first=False,
                  font="Arial"):
    if first and len(tf.paragraphs) == 1 and not tf.paragraphs[0].runs:
        p = tf.paragraphs[0]
    else:
        p = tf.add_paragraph()

    p.level = level
    if align is not None:
        p.alignment = align

    pPr = p._p.get_or_add_pPr()
    for tag in ("buClr", "buChar", "buAutoNum", "buNone", "buFont",
                "buSzPts", "buSzPct"):
        for el in pPr.findall(f"{{{A_NS}}}{tag}"):
            pPr.remove(el)

    marL, indent = LEVEL_INDENT_EMU.get(level, LEVEL_INDENT_EMU[0])
    pPr.set("marL", str(marL))
    pPr.set("indent", str(indent))

    if bullet:
        bc = bullet_color if bullet_color is not None else color
        buClr = etree.SubElement(pPr, f"{{{A_NS}}}buClr")
        srgb = etree.SubElement(buClr, f"{{{A_NS}}}srgbClr")
        srgb.set("val", "{:02X}{:02X}{:02X}".format(bc[0], bc[1], bc[2]))
        buFont = etree.SubElement(pPr, f"{{{A_NS}}}buFont")
        buFont.set("typeface", "Arial")
        buChar = etree.SubElement(pPr, f"{{{A_NS}}}buChar")
        buChar.set("char", "●" if level == 0 else ("○" if level == 1 else "■"))
    else:
        pPr.set("marL", "0")
        pPr.set("indent", "0")
        etree.SubElement(pPr, f"{{{A_NS}}}buNone")

    run = p.add_run()
    run.text = text
    set_run(run, size=size, bold=bold, color=color, italic=italic, font=font)
    return p


def add_title(slide, title_text, *, size=28, color=WHITE, bold=True):
    for ph in slide.placeholders:
        if ph.placeholder_format.idx == 0:
            tf = ph.text_frame
            clear_tf(tf)
            add_paragraph(tf, title_text, size=size, bold=bold, color=color,
                          bullet=False, first=True)
            return ph
    return None


def add_body_bullets(slide, items, *, ph_idx=1, base_size=18, color=WHITE,
                     bullet_color=None):
    ph = None
    for p in slide.placeholders:
        if p.placeholder_format.idx == ph_idx:
            ph = p
            break
    if ph is None:
        return
    tf = ph.text_frame
    tf.word_wrap = True
    clear_tf(tf)
    first = True
    for it in items:
        text, level = (it if isinstance(it, tuple) else (it, 0))
        size = base_size if level == 0 else max(12, base_size - 3)
        add_paragraph(tf, text, size=size, level=level, bullet=True,
                      color=color, bullet_color=bullet_color or color,
                      first=first)
        first = False


def add_textbox(slide, left, top, width, height, lines, *,
                fill=None, font_size=12, color=CODE_TEXT, mono=True, bold=False,
                align=None):
    tb = slide.shapes.add_textbox(Emu(left), Emu(top), Emu(width), Emu(height))
    if fill is not None:
        tb.fill.solid()
        tb.fill.fore_color.rgb = fill
    else:
        tb.fill.background()
    tb.line.fill.background()
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = Emu(91425)
    tf.margin_right = Emu(91425)
    tf.margin_top = Emu(45700)
    tf.margin_bottom = Emu(45700)
    clear_tf(tf)
    first = True
    for line in lines:
        add_paragraph(tf, line, size=font_size, color=color, bullet=False,
                      bold=bold, align=align, first=first,
                      font=("Courier New" if mono else "Arial"))
        first = False
    return tb


def strip_handle(slide):
    for sh in list(slide.shapes):
        if sh.has_text_frame and "@handle" in sh.text_frame.text:
            sh._element.getparent().remove(sh._element)


# ------------------------------- Build deck -------------------------------

prs = Presentation(TEMPLATE)
clear_deck(prs)

L_TITLE = prs.slide_layouts[0]
L_SECTION = prs.slide_layouts[1]
L_BODY = prs.slide_layouts[2]
L_TITLE_ONLY = prs.slide_layouts[4]


# ---------- Slide 1: Title ----------
s = prs.slides.add_slide(L_TITLE)
strip_handle(s)
for ph in s.placeholders:
    if ph.placeholder_format.idx == 0:
        tf = ph.text_frame
        clear_tf(tf)
        add_paragraph(tf, "Advanced Bazel", size=44, bold=True,
                      color=WHITE, bullet=False, first=True)
        add_paragraph(tf, "Rules Authoring, Performance Tuning and Remote Execution",
                      size=24, color=WHITE, bullet=False)
    elif ph.placeholder_format.idx == 1:
        tf = ph.text_frame
        clear_tf(tf)
        add_paragraph(tf, "Antonio Di Stefano  ·  Yannic Bonenberger",
                      size=18, bold=True, color=WHITE, bullet=False, first=True)


# ---------- Slide 2: Placeholder for the earlier part of the workshop ----------
# WORKSHOP.md only covers Testing & Validation; the rest of the material lives
# elsewhere. Left intentionally blank so it can be filled in later.
s = prs.slides.add_slide(L_SECTION)
for ph in s.placeholders:
    if ph.placeholder_format.idx == 0:
        tf = ph.text_frame
        clear_tf(tf)
        add_paragraph(tf, "", size=44, color=WHITE, bullet=False, first=True)


# ---------- Slide 3: Section - Testing & Validation ----------
s = prs.slides.add_slide(L_SECTION)
for ph in s.placeholders:
    if ph.placeholder_format.idx == 0:
        tf = ph.text_frame
        clear_tf(tf)
        add_paragraph(tf, "Testing & Validation", size=54, bold=True,
                      color=WHITE, bullet=False,
                      align=PP_ALIGN.CENTER, first=True)


# ---------- Slide 4: What we're building ----------
s = prs.slides.add_slide(L_BODY)
add_title(s, "Four Bazel building blocks")
add_body_bullets(s, [
    "Test sharding — splitting a test target across parallel workers",
    "Validation actions — implicit checks via the _validation output group",
    "Tree artifacts — directory outputs whose contents are only known at execution time",
    "ctx.actions.map_directory — fanning out N actions over a tree artifact",
], base_size=20)


# ---------- Slide 5: What you start with ----------
s = prs.slides.add_slide(L_BODY)
add_title(s, "What you start with")
add_body_bullets(s, [
    "A working minilang CLI at //cli:cli",
    "An example minilang program at //:example.mini",
    "A minimal mini_test rule that invokes 'minilang test <src>' and honors the exit code",
    ("bazel test //:example_test already passes", 1),
    "Sharding wiring and the mutation-testing aspect are the four stages you'll implement",
], base_size=18)


# ---------- Slide 6: The CLI - treat it as a black box ----------
s = prs.slides.add_slide(L_BODY)
add_title(s, "The CLI — treat it as a black box")
add_body_bullets(s, [
    "You'll invoke it from your rules. Don't look inside the Python",
    "Each stage introduces just the subcommand it needs — don't try to memorize the whole surface",
    "For now: only 'minilang test <file.mini>'",
], base_size=20)


# ---------- Slide 7: minilang test flags ----------
s = prs.slides.add_slide(L_TITLE_ONLY)
add_title(s, "minilang test — flags")
add_textbox(s, left=311700, top=1000000, width=8520600, height=1500000,
            lines=[
                "$ minilang test example.mini",
                "$ minilang test example.mini --shard-count 3 --shard-index 0",
                "$ minilang test example.mini --junit-xml out.xml",
            ],
            fill=CODE_BG, font_size=14, color=CODE_TEXT, mono=True)
add_body_bullets_lines = [
    "--shard-count N   — total shard count (round robin)",
    "--shard-index i   — 0-based shard index; runs tests where i % N == index",
    "--junit-xml PATH  — writes a JUnit-compatible XML report to PATH",
]
add_textbox(s, left=311700, top=2800000, width=8520600, height=1600000,
            lines=add_body_bullets_lines, fill=None, font_size=16,
            color=WHITE, mono=True)


# ---------- Slide 8: Stage 1 — Test sharding ----------
s = prs.slides.add_slide(L_SECTION)
for ph in s.placeholders:
    if ph.placeholder_format.idx == 0:
        tf = ph.text_frame
        clear_tf(tf)
        add_paragraph(tf, "Stage 1 — Test sharding", size=48, bold=True,
                      color=WHITE, bullet=False,
                      align=PP_ALIGN.CENTER, first=True)


# ---------- Slide 9: Stage 1 goal ----------
s = prs.slides.add_slide(L_TITLE_ONLY)
add_title(s, "Goal")
add_textbox(s, left=311700, top=1000000, width=8520600, height=900000,
            lines=[
                'mini_test(',
                '    name = "example_test_sharded",',
                '    src = "example.mini",',
                '    shard_count = 3,',
                ')',
            ],
            fill=CODE_BG, font_size=15, color=CODE_TEXT, mono=True)
add_textbox(s, left=311700, top=2200000, width=8520600, height=1000000,
            lines=[
                "bazel test //:example_test_sharded",
                "  → three parallel test actions,",
                "     each running one of the three test cases.",
            ],
            fill=None, font_size=18, color=WHITE, mono=False, align=PP_ALIGN.LEFT)


# ---------- Slide 10: Stage 1 building blocks - env vars ----------
s = prs.slides.add_slide(L_BODY)
add_title(s, "Bazel's contract with sharded tests")
add_body_bullets(s, [
    "TEST_TOTAL_SHARDS — number of shards (`shard_count` on the target). 1 means unsharded",
    "TEST_SHARD_INDEX — 0-based index of this shard",
    "TEST_SHARD_STATUS_FILE — the runner MUST create or update the mtime of this file",
    ("Otherwise Bazel fails the test", 1),
    "shard_count is a built-in test attribute — you don't declare it on your rule",
    ("Your job: plumb env vars → CLI's --shard-count / --shard-index", 1),
], base_size=17)


# ---------- Slide 11: Stage 1 verify ----------
s = prs.slides.add_slide(L_TITLE_ONLY)
add_title(s, "Verify")
add_textbox(s, left=311700, top=1000000, width=8520600, height=700000,
            lines=[
                "bazel test //:example_test_sharded --test_output=all",
            ],
            fill=CODE_BG, font_size=15, color=CODE_TEXT, mono=True)
add_textbox(s, left=311700, top=1900000, width=8520600, height=1200000,
            lines=[
                'Three "shard N of 3" logs, each with a single test.',
                "",
                "Reference: bazel.build/reference/test-encyclopedia",
            ],
            fill=None, font_size=17, color=WHITE, mono=False)


# ---------- Slide 12: CLI — mutation subcommands ----------
s = prs.slides.add_slide(L_BODY)
add_title(s, "The CLI — mutation subcommands")
add_body_bullets(s, [
    "minilang mutate list <src> -o <dir>",
    ("Produces a tree: mutations.json + one mNNNN/mutation.json per candidate", 1),
    "minilang mutate patch --mutation <json> --source <src> --output <dest>",
    ("Patches <src> with one mutation, writes to <dest>", 1),
    "minilang mutate test <file.mini>",
    ("Inverts the exit code — success iff at least one test failed", 1),
    ("--junit-xml, --mutation-json (compact 'survived: …' line on survival)", 1),
], base_size=17)


# ---------- Slide 13: Interlude — mutation testing, and why naïve is wrong ----------
s = prs.slides.add_slide(L_SECTION)
for ph in s.placeholders:
    if ph.placeholder_format.idx == 0:
        tf = ph.text_frame
        clear_tf(tf)
        add_paragraph(tf, "Interlude", size=54, bold=True,
                      color=WHITE, bullet=False,
                      align=PP_ALIGN.CENTER, first=True)
        add_paragraph(tf,
                      "mutation testing, and why the naïve approach is wrong",
                      size=22, color=WHITE, bullet=False,
                      align=PP_ALIGN.CENTER)


# ---------- Slide 14: What is mutation testing ----------
s = prs.slides.add_slide(L_BODY)
add_title(s, "Mutation testing in one paragraph")
add_body_bullets(s, [
    "Grade a test suite by perturbing the program under test",
    ("Flip < to <=, swap + for -, replace true with false, …", 1),
    "Re-run the tests",
    ("A test fails → mutation is killed (good — your tests caught it)", 1),
    ("Every test still passes → mutation survived (bad — tests are blind to it)", 1),
    "The CLI does the heavy lifting: mutate list / patch / test",
], base_size=18)


# ---------- Slide 15: The tempting-but-wrong design ----------
s = prs.slides.add_slide(L_BODY)
add_title(s, "The tempting-but-wrong design")
add_body_bullets(s, [
    "Add a 'mutation_test' mode to mini_test that loops over every mutation at test time",
    "Don't do this. Concretely:",
    ("One action = one worker — no parallelism, 24 mutations run sequentially", 1),
    ("All-or-nothing caching — one line changes, everything reruns", 1),
    ("All-or-nothing failure — one survivor = red test; other 23 outcomes invisible", 1),
    ("All-or-nothing logs — everything smashed into one test.log / test.xml", 1),
], base_size=17)


# ---------- Slide 16: The right shape — three phases ----------
s = prs.slides.add_slide(L_BODY)
add_title(s, "The right shape: three phases")
add_body_bullets(s, [
    "Enumeration — what mutations exist? One action, produces a manifest",
    "Mutation — apply mutation m0007 to the source. One action per mutation",
    "Verification — does m0007 survive? One action per mutation runs the test suite",
    "Bazel schedules, caches, and reports each mutation's outcome independently",
], base_size=19)


# ---------- Slide 17: Stage 2 — Validation actions ----------
s = prs.slides.add_slide(L_SECTION)
for ph in s.placeholders:
    if ph.placeholder_format.idx == 0:
        tf = ph.text_frame
        clear_tf(tf)
        add_paragraph(tf, "Stage 2 — Validation actions", size=48, bold=True,
                      color=WHITE, bullet=False,
                      align=PP_ALIGN.CENTER, first=True)


# ---------- Slide 18: Stage 2 goal ----------
s = prs.slides.add_slide(L_BODY)
add_title(s, "Goal")
add_body_bullets(s, [
    "Create mini_mutation_testing_aspect",
    "Runs extra work automatically when a mini_test target is built",
    ("No --output_groups flag needed", 1),
    "For this stage: keep the work trivial (a placeholder file)",
    ("The point is the wiring, not what the aspect does yet", 1),
], base_size=19)


# ---------- Slide 19: Stage 2 building blocks ----------
s = prs.slides.add_slide(L_BODY)
add_title(s, "Building blocks")
add_body_bullets(s, [
    "aspect() — attach private tool attrs like a rule does",
    "Gate on ctx.rule.kind == 'mini_test' — return [] otherwise",
    "OutputGroupInfo(_validation = depset([...]))",
    ("_validation is magic — Bazel runs those actions on every build", 1),
    ("Failures fail the build but don't affect artifact production", 1),
    ("--run_validations=false disables it; --keep_going shows every failure", 1),
], base_size=17)


# ---------- Slide 20: Stage 2 verify ----------
s = prs.slides.add_slide(L_TITLE_ONLY)
add_title(s, "Verify")
add_textbox(s, left=311700, top=1000000, width=8520600, height=1200000,
            lines=[
                "bazel build \\",
                "  --aspects=//:defs.bzl%mini_mutation_testing_aspect \\",
                "  //:example_test",
                "",
                "bazel build --aspects=... \\",
                "  --run_validations=false //:example_test   # skips it",
            ],
            fill=CODE_BG, font_size=13, color=CODE_TEXT, mono=True)


# ---------- Slide 21: Stage 3 — Tree artifacts ----------
s = prs.slides.add_slide(L_SECTION)
for ph in s.placeholders:
    if ph.placeholder_format.idx == 0:
        tf = ph.text_frame
        clear_tf(tf)
        add_paragraph(tf, "Stage 3 — Tree artifacts", size=48, bold=True,
                      color=WHITE, bullet=False,
                      align=PP_ALIGN.CENTER, first=True)


# ---------- Slide 22: Stage 3 goal ----------
s = prs.slides.add_slide(L_BODY)
add_title(s, "Goal")
add_body_bullets(s, [
    "Replace the stage-2 placeholder",
    "Have the aspect run 'minilang mutate list <src> -o <dir>'",
    "Expose <dir> as a directory output — a tree artifact",
], base_size=20)


# ---------- Slide 23: Stage 3 building blocks ----------
s = prs.slides.add_slide(L_BODY)
add_title(s, "Building blocks")
add_body_bullets(s, [
    "Tree artifact: directory output known only at execution time",
    ("Single artifact in the action graph; downstream actions can still enumerate entries", 1),
    "ctx.actions.declare_directory(name)",
    ("Returns a File; file.path is the directory the action must populate", 1),
    "ctx.actions.run(executable, inputs, outputs, arguments, …)",
    ("Producing action lists the tree artifact in outputs", 1),
    "ctx.actions.args() — assemble the command line without string concatenation",
], base_size=16)


# ---------- Slide 24: Stage 3 verify ----------
s = prs.slides.add_slide(L_TITLE_ONLY)
add_title(s, "Verify")
add_textbox(s, left=311700, top=1000000, width=8520600, height=800000,
            lines=[
                "bazel build --aspects=... //:example_test",
                "ls bazel-bin/example_test.mutations/",
            ],
            fill=CODE_BG, font_size=15, color=CODE_TEXT, mono=True)
add_textbox(s, left=311700, top=2000000, width=8520600, height=1500000,
            lines=[
                "mutations.json + one mNNNN/ subdirectory per candidate mutation.",
                "",
                "The count depends on the source — Bazel didn't know it",
                "at analysis time. That's the whole point.",
            ],
            fill=None, font_size=17, color=WHITE, mono=False)


# ---------- Slide 25: Stage 4 — ctx.actions.map_directory ----------
s = prs.slides.add_slide(L_SECTION)
for ph in s.placeholders:
    if ph.placeholder_format.idx == 0:
        tf = ph.text_frame
        clear_tf(tf)
        add_paragraph(tf, "Stage 4 — ctx.actions.map_directory",
                      size=42, bold=True,
                      color=WHITE, bullet=False,
                      align=PP_ALIGN.CENTER, first=True)


# ---------- Slide 26: Stage 4 goal ----------
s = prs.slides.add_slide(L_BODY)
add_title(s, "Goal — two actions per mutation")
add_body_bullets(s, [
    "For each mutation subdirectory produced in stage 3:",
    ("mutate patch → mutated source in the results tree", 1),
    ("mutate test  → runs the test suite (inverted exit code)", 1),
    "A mutation survives iff its test action exits non-zero",
    ("Bazel surfaces the one-liner: 'survived: <id> <op> at <file>:<line>:<col>'", 1),
], base_size=18)


# ---------- Slide 27: map_directory - signature ----------
s = prs.slides.add_slide(L_TITLE_ONLY)
add_title(s, "ctx.actions.map_directory")
add_textbox(s, left=311700, top=900000, width=8520600, height=2600000,
            lines=[
                "ctx.actions.map_directory(",
                "    *,",
                "    input_directories,      # {str: tree_artifact_File}",
                "    output_directories,     # {str: tree_artifact_File}",
                "    tools,                  # {str: FilesToRunProvider}",
                "    additional_inputs = {}, # {str: File | depset}",
                "    additional_params = {}, # {str: str|int|bool}",
                "    implementation,         # top-level function",
                "    mnemonic = None,",
                "    ...",
                ")",
            ],
            fill=CODE_BG, font_size=13, color=CODE_TEXT, mono=True)
add_textbox(s, left=311700, top=3700000, width=8520600, height=900000,
            lines=[
                "Declared once at analysis time.",
                "Callback creates N distinct actions from execution-time data.",
                "Each action independently cacheable and failable.",
            ],
            fill=None, font_size=15, color=WHITE, mono=False)


# ---------- Slide 28: map_directory - callback ----------
s = prs.slides.add_slide(L_TITLE_ONLY)
add_title(s, "The implementation callback")
add_textbox(s, left=311700, top=900000, width=8520600, height=1000000,
            lines=[
                "def impl(template_ctx, *, input_directories,",
                "         output_directories, additional_inputs,",
                "         tools, additional_params):",
                "    ...",
            ],
            fill=CODE_BG, font_size=13, color=CODE_TEXT, mono=True)
add_body_bullets_lines = [
    "input_directories[key] → ExpandedDirectory",
    "    .directory, .children (each has .tree_relative_path, .basename, .path)",
    "output_directories[key] → tree artifact File declared outside",
    "tools[key] → FilesToRunProvider (use .executable)",
    "Callback must be a top-level function (no lambdas, no nested defs)",
]
add_textbox(s, left=311700, top=2100000, width=8520600, height=2000000,
            lines=add_body_bullets_lines, fill=None, font_size=14,
            color=WHITE, mono=False)


# ---------- Slide 29: template_ctx surface ----------
s = prs.slides.add_slide(L_BODY)
add_title(s, "template_ctx — restricted surface")
add_body_bullets(s, [
    "template_ctx.args() — same as ctx.actions.args()",
    "template_ctx.declare_file(filename, *, directory)",
    ("Declares a file inside the given output tree artifact", 1),
    "template_ctx.declare_subdirectory(name, *, directory)",
    "template_ctx.run(*, outputs, executable, inputs, tools, arguments, progress_message)",
    ("No mnemonic. No run_shell. Outputs must be declared via declare_file", 1),
    "Every read → in inputs=[…]. Every write → declared + in outputs=[…]",
], base_size=16)


# ---------- Slide 30: Stage 4 verify ----------
s = prs.slides.add_slide(L_TITLE_ONLY)
add_title(s, "Verify")
add_textbox(s, left=311700, top=900000, width=8520600, height=700000,
            lines=[
                "bazel build --aspects=... --keep_going //:example_test",
            ],
            fill=CODE_BG, font_size=14, color=CODE_TEXT, mono=True)
add_textbox(s, left=311700, top=1800000, width=8520600, height=2300000,
            lines=[
                "≈ 2 × N actions (patch + test per mutation).",
                "Surviving mutations report as failed actions:",
                "",
                "    survived: m0006 *->/ at mutated.mini:15:19",
                "",
                "Fix a survivor (stronger assertion in example.mini), rerun —",
                "only that mutation's actions rerun. Everything else is cached.",
            ],
            fill=None, font_size=15, color=WHITE, mono=False)


# ---------- Slide 31: Takeaways ----------
s = prs.slides.add_slide(L_BODY)
add_title(s, "Takeaways")
add_body_bullets(s, [
    "Test sharding is a rule-author's job: read env vars, forward them, touch the status file",
    "_validation turns extra checks into implicit build-time work",
    "Tree artifacts let you produce work whose shape is decided at execution time",
    "map_directory bridges analysis and execution — N distinct actions from execution-time data",
    "Pattern generalizes: produce a manifest → fan out per-entry → surface failures as validations",
    ("Code gen, per-package linting, per-file coverage, ABI diffs, …", 1),
], base_size=16)


# ---------- Slide 32: Q&A ----------
s = prs.slides.add_slide(L_SECTION)
for ph in s.placeholders:
    if ph.placeholder_format.idx == 0:
        tf = ph.text_frame
        clear_tf(tf)
        add_paragraph(tf, "Q&A", size=88, bold=True, color=WHITE,
                      bullet=False, align=PP_ALIGN.CENTER, first=True)


prs.save(OUTPUT)
print(f"Wrote {OUTPUT}")
print(f"Slide count: {len(prs.slides)}")
