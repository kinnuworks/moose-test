#!/usr/bin/env bash
# Installs each agent under test in its own virtualenv, exactly as published, pinned.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .agents
mk() { [ -x ".agents/$1/bin/python" ] || python3 -m venv ".agents/$1"; ".agents/$1/bin/pip" install -q --upgrade pip; ".agents/$1/bin/pip" install -q "${@:2}"; }
mk base "openai" "tavily-python"
mk gptr "gpt-researcher==0.17.0"
mk odr "git+https://github.com/langchain-ai/open_deep_research.git@${ODR_REF:-main}"
echo "agents installed in .agents/"
