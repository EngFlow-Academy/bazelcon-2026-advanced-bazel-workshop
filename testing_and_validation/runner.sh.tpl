#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${RUNFILES_DIR:-}" && -z "${RUNFILES_MANIFEST_FILE:-}" ]]; then
  if [[ -d "$0.runfiles" ]]; then
    RUNFILES_DIR="$0.runfiles"
  fi
fi

if [[ -n "${RUNFILES_DIR:-}" ]]; then
  CLI="${RUNFILES_DIR}/%workspace%/%cli_short_path%"
  SRC="${RUNFILES_DIR}/%workspace%/%src_short_path%"
else
  CLI="%cli_short_path%"
  SRC="%src_short_path%"
fi

ARGS=()
if [[ -n "${XML_OUTPUT_FILE:-}" ]]; then
  ARGS+=(--junit-xml "${XML_OUTPUT_FILE}")
fi

exec "${CLI}" test "${SRC}" ${ARGS[@]+"${ARGS[@]}"}
