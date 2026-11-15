#!/usr/bin/env bash
# Starts the Moose Test stack locally: Bifrost (gateway), the Tavily proxy, and Ollama (embeddings).
set -euo pipefail
cd "$(dirname "$0")/.."
touch .env && chmod 600 .env
grep -q '^BIFROST_ADMIN_USERNAME=' .env || echo "BIFROST_ADMIN_USERNAME=admin" >> .env
grep -q '^BIFROST_ADMIN_PASSWORD=' .env || echo "BIFROST_ADMIN_PASSWORD=$(python3 -c 'import secrets;print(secrets.token_urlsafe(18))')" >> .env
set -a; . ./.env; set +a
mkdir -p .bifrost logs
cp bifrost/config.json .bifrost/config.json
if ! curl -sf -o /dev/null http://localhost:11434/api/tags; then (ollama serve > logs/ollama.log 2>&1 &); sleep 2; fi
ollama list | grep -q nomic-embed-text || ollama pull nomic-embed-text
if ! curl -sf -o /dev/null http://localhost:8080/health; then
  (npx -y @maximhq/bifrost@1.6.3 --transport-version v${BIFROST_VERSION:-2.5.1} -app-dir ./.bifrost -host 127.0.0.1 -port 8080 -log-style json > logs/bifrost.log 2>&1 &)
  for i in $(seq 1 60); do curl -sf -o /dev/null http://localhost:8080/health && break; sleep 1; done
fi
curl -sf -o /dev/null http://localhost:8080/health || { echo "Bifrost did not start; see logs/bifrost.log"; exit 1; }
if ! lsof -iTCP:8899 -sTCP:LISTEN >/dev/null 2>&1; then
  (MOOSETEST_RELAY_MAP="$PWD/.moosetest-relaymap.json" ./.venv/bin/mitmdump -q --listen-host 127.0.0.1 -p 8899 -s moosetest/tavily_proxy.py > logs/proxy.log 2>&1 &)
  sleep 3
fi
[ -f "$HOME/.mitmproxy/mitmproxy-ca-cert.pem" ] || { echo "proxy CA missing"; exit 1; }
echo "stack up: Bifrost :8080, Tavily proxy :8899, Ollama :11434"
