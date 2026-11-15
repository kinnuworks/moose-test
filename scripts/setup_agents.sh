#!/usr/bin/env bash
# Installs each agent under test in its own virtualenv, exactly as published, pinned.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .agents
mk() { [ -x ".agents/$1/bin/python" ] || python3 -m venv ".agents/$1"; ".agents/$1/bin/pip" install -q --upgrade pip; ".agents/$1/bin/pip" install -q "${@:2}"; }
mk base "openai==3.51.0" "tavily-python==0.8.5"
mk gptr "gpt-researcher==0.17.0"
# open_deep_research 0.0.16: the exact commit every committed run used
mk odr "git+https://github.com/langchain-ai/open_deep_research.git@${ODR_REF:-1b7d2e80db9faa586165c60e09096dbbfd483a64}"
echo "agents installed in .agents/"
