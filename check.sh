#!/usr/bin/env bash
# Moose Test checks. All run against real things: the unit tests cover the grader, the fault
# server and the provisioning payloads; the browser test walks the viewer's demo path and
# records a video; the live smoke test runs real agents through a real local Bifrost with the
# real model provider and real Tavily. Nothing here is skipped or mocked.
set -euo pipefail
cd "$(dirname "$0")"
PY=./.venv/bin/python

echo "== unit tests"
$PY -m pytest -q tests

echo "== viewer demo path in a real browser (records results/rough-cut/*.webm)"
$PY -m pytest -q tests_e2e

echo "== live smoke: Bifrost + model provider + Tavily"
curl -sf -o /dev/null http://localhost:8080/health || { echo "Bifrost is not running on :8080 (scripts/up.sh)"; exit 1; }
$PY -m pytest -q tests_live

echo "check.sh: all checks passed"
