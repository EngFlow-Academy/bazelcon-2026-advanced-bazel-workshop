# Advanced Bazel Workshop — Deck

Slide deck for the "Testing & Validation" segment of the BazelCon 2026
Advanced Bazel workshop.

## Build

```sh
bazel build //slides:deck
```

Output: `bazel-bin/slides/AdvancedBazel_TestingAndValidation.pptx`.

## Layout

- `build_deck.py` — deck generator (python-pptx).
- `template/EngFlow_Dark_Template.pptx` — EngFlow slide template.
- `BUILD.bazel` — one `py_binary` for the builder plus the `:deck` genrule.
