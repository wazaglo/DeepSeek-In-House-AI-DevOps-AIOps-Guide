# DeepSeek In-House AI — DevOps & AIOps Guide

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Ollama](https://img.shields.io/badge/Ollama-000?logo=ollama&logoColor=white)](https://ollama.ai/)
[![DeepSeek](https://img.shields.io/badge/DeepSeek-4A6CF7?logo=deepseek&logoColor=white)](https://deepseek.com/)

A private, self-hosted DeepSeek AI environment: local LLM inference via
[Ollama](https://ollama.com), three chat interfaces, an auditing LLM gateway,
a Prometheus/Grafana/Loki observability stack, and an AIOps bridge that turns
system metrics into an AI-assessed risk score.

- **Free & private** — no API costs; your code never leaves the server.
- **Audited gateway** — every prompt/response, user, model and latency logged
  through one controlled endpoint (:11435) and searchable in Grafana.
- **AIOps** — an AI-generated `ai_server_risk_level` metric in Grafana.
- **Multi-interface** — lightweight chat (3000), ChatGPT-style sessions
  (3001), and a professional workspace (3002).

## Architecture

```
┌───────────────────────────────────────────────┐
│                Ollama Server                  │
│           deepseek-coder:1.3b / 6.7b          │
└───────────────────────▲───────────────────────┘
                        │  upstream (127.0.0.1:11434)
┌───────────────────────┴───────────────────────┐
│        AI Gateway  :11435  (gateway/)         │
│  API-key auth · audit JSONL · /metrics        │
└───┬───────────┬───────────┬───────────────────┘
    │           │           │
    ▼           ▼           ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│ Chatbot  │ │ NextChat │ │ Big-AGI  │   + any API client
│  :3000   │ │  :3001   │ │  :3002   │   (Bearer / X-API-Key)
└──────────┘ └──────────┘ └──────────┘

   ┌──────────────────────────────────────────┐
   │           AI Monitor (aiops/)            │
   │   Prometheus → Ollama → risk gauge       │
   └────────────────────┬─────────────────────┘
                        ▼
   ┌──────────────────────────────────────────┐
   │            Monitoring Stack              │
   │  Prometheus  :9090   Grafana     :4000   │
   │  Loki        :3100   Alloy (logs)        │
   │  node-exporter :9100 (+ textfile)        │
   │  cAdvisor    :8082                       │
   │                                          │
   │  audit JSONL → Alloy → Loki → Grafana    │
   │  gateway /metrics → Prometheus → Grafana │
   └──────────────────────────────────────────┘
```

## Prerequisites

| Requirement | Used for |
| :--- | :--- |
| [Ollama](https://ollama.com) (installed as a systemd service) | LLM inference on port 11434 |
| Docker + Docker Compose | Monitoring stack and web UIs |
| Python 3.10+ | AIOps bridge (`aiops/ai_monitor.py`) |
| Node.js 18+ (optional) | Local CLI tools |

4 GB+ RAM minimum; 8 GB recommended if you also run `deepseek-coder:6.7b`.

## Quickstart

### 1. Ollama service

The server runs Ollama as a systemd service (full setup steps:
[docs/CHANGES-2026-09-08.md](docs/CHANGES-2026-09-08.md), Part 3). Verify:

```bash
systemctl status ollama        # should be active
curl http://localhost:11434/   # should print "Ollama is running"
ollama list                    # models: deepseek-coder:1.3b (+ 6.7b optional)
```

Key service settings (set in the unit file):
`OLLAMA_HOST=0.0.0.0:11434`, `OLLAMA_ORIGINS=*`.

### 2. AI gateway (audit layer)

The gateway (`gateway/app.py`, stdlib-only) sits in front of Ollama on
`:11435`. Every request must carry an API key from `gateway/users.json`;
each call is audited (user, team, model, prompt, response, duration, status,
token usage) to `monitoring/logs/gateway_audit.jsonl` and exposed as
Prometheus metrics at `/metrics`.

```bash
# 1. Create the users file (gitignored — real keys must never be committed)
cp gateway/users.json.example gateway/users.json
# then edit users.json and give every user/UI a random key:
openssl rand -hex 16

# 2. Install the systemd service
sudo cp gateway/ollama-gateway.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ollama-gateway

# 3. Verify
curl -s localhost:11435/health                                  # {"status": "ok"}
curl -s -o /dev/null -w '%{http_code}\n' localhost:11435/api/tags  # 401 without a key
curl -s -X POST localhost:11435/api/generate \
  -H "Authorization: Bearer $(python3 -c "import json;print(json.load(open('gateway/users.json'))[0]['key'])")" \
  -d '{"model":"deepseek-coder:1.3b","prompt":"hi","stream":false}'
```

Clients authenticate with `Authorization: Bearer <key>`, `X-API-Key: <key>`,
HTTP Basic auth, or `?key=<key>` (for UIs that cannot send headers).

### 3. Chat UIs

```bash
docker compose -f uis/docker-compose.yml up -d
```

The UIs in `uis/docker-compose.yml` already point at the gateway
(`http://host.docker.internal:11435?key=...`), so chat traffic is audited
with a per-UI identity.

| Port | UI | Notes |
| :--- | :--- | :--- |
| 3000 | Chatbot Ollama | Fast, no-login interface |
| 3001 | NextChat | ChatGPT-style UI, private sessions |
| 3002 | Big-AGI | "DevOps grade" workspace with folder management |

### 4. Monitoring stack

```bash
docker compose -f monitoring/docker-compose.yml up -d
```

| Port | Service |
| :--- | :--- |
| 4000 | Grafana dashboards (incl. **AI Activity** audit dashboard) |
| 9090 | Prometheus (scrapes the gateway's `/metrics`) |
| 3100 | Loki (searchable audit-log store, 30-day retention) |
| 9100 | node-exporter (host metrics + textfile collector) |
| 8082 | cAdvisor (container metrics) |

Grafana ships with Prometheus + Loki datasources and the **AI Activity —
Ollama Gateway Audit** dashboard (requests by user/model, error rate, p50/p95
latency, token usage, raw audit search), provisioned from
`monitoring/grafana/provisioning/`. Alloy tails the gateway's audit JSONL and
ships each line to Loki with `user`/`model`/`path`/`status` labels.

### 5. AIOps bridge

```bash
pip install -r aiops/requirements.txt
python3 aiops/ai_monitor.py
```

Every 60 s the bridge reads CPU/memory from Prometheus, asks the local model
for a 0–100 risk score, and writes `monitoring/metrics/ai_prediction.prom`,
which node-exporter picks up and Prometheus scrapes. Watch it in Grafana via
the `ai_server_risk_level` metric.

## Repository layout

```
aiops/       ai_monitor.py, requirements.txt      AIOps bridge
gateway/     app.py, users.json(.example),        Auditing LLM gateway (:11435)
             ollama-gateway.service
monitoring/  docker-compose.yml, prometheus.yml,
             alloy/ loki/ grafana/                Observability stack
             metrics/ logs/                       (logs/ = audit trail, gitignored)
uis/         docker-compose.yml                   Chat UIs (3000/3001/3002)
docs/        CHANGES-2026-09-08.md                Change log & server setup
```

## Configuration

Environment variables for the AIOps bridge (all optional):

| Variable | Default |
| :--- | :--- |
| `PROM_URL` | `http://localhost:9090` |
| `OLLAMA_URL` | `http://localhost:11434/api/generate` |
| `DEEPSEEK_MODEL` | `deepseek-coder:1.3b` |
| `METRIC_FILE` | `<repo>/monitoring/metrics/ai_prediction.prom` |

Environment variables for the gateway (all optional):

| Variable | Default |
| :--- | :--- |
| `OLLAMA_UPSTREAM` | `http://127.0.0.1:11434` |
| `GATEWAY_HOST` / `GATEWAY_PORT` | `0.0.0.0` / `11435` |
| `GATEWAY_USERS_FILE` | `<repo>/gateway/users.json` |
| `GATEWAY_AUDIT_LOG` | `<repo>/monitoring/logs/gateway_audit.jsonl` |

> The AIOps bridge talks to Ollama directly on `:11434`. Keep it that way: if
> its own calls went through the gateway, every audit entry would trigger
> another scoring run.

For local CLI tools, route through the gateway so your usage is audited:

```bash
export DEEPSEEK_MODEL="deepseek-coder:1.3b"
curl -X POST http://localhost:11435/api/generate \
  -H "Authorization: Bearer <your-key>" \
  -d '{"model":"deepseek-coder:1.3b","prompt":"hello","stream":false}'
```

(`ollama` CLI itself still speaks to `:11434`; the gateway serves the HTTP
API.)

### Local models

| Model | Size | Best for |
| :--- | :--- | :--- |
| `deepseek-coder:1.3b` | 776 MB | CLI tasks, AIOps bridge — fast |
| `deepseek-coder:6.7b` | 3.8 GB | Complex refactoring — slow on CPU |

## Daily DevOps tasks

- **Log analysis:** `cat sys.log | ollama run deepseek-coder:1.3b "Explain these errors"`
- **Project scaffolding:** "Create a FastAPI project with Docker and PostgreSQL"
- **Refactoring & tests:** "Refactor this module for time complexity" / "Generate pytest cases"
- **Predictive stability:** watch the `ai_server_risk_level` spike in Grafana
  when the model flags load trends.

## Troubleshooting

**Connection refused on port 11434** — Ollama is down or not installed:

```bash
systemctl status ollama && journalctl -u ollama -e
ss -tulpn | grep 11434
```

**A UI shows no models** — the UIs now talk to the gateway. Check the gateway
is up (`systemctl status ollama-gateway`), that its key exists in
`gateway/users.json`, and that the UI container has
`OLLAMA_BASE_URL=http://host.docker.internal:11435?key=<key>` (already set in
`uis/docker-compose.yml`). The gateway passes Ollama's `OLLAMA_ORIGINS=*`
traffic straight through.

**Audit logs not appearing in Grafana** — walk the chain: the JSONL grows
(`wc -l monitoring/logs/gateway_audit.jsonl`) → Alloy tails it
(`docker logs monitoring-alloy-1`) → Loki has it
(`curl -G localhost:3100/loki/api/v1/label/job/values` should include
`ai-gateway-audit`).

**`ai_server_risk_level` not updating** — check the bridge and the chain:

```bash
tail -f ai_monitor.log                                  # bridge output
curl -s localhost:9090/api/v1/query?query=ai_server_risk_level
```

The metric file must land in `monitoring/metrics/` (mounted read-only into
node-exporter as `/textfile`).

## Security note

This setup binds Ollama and the gateway to all interfaces with
`OLLAMA_ORIGINS=*` and exposes Grafana, Prometheus, Loki, and cAdvisor
directly. That is acceptable on a trusted home LAN only. On any shared
network, firewall the ports and restrict `OLLAMA_ORIGINS` to your UI origins.

Two gateway-specific caveats: API keys travel in plaintext HTTP on the LAN,
and the audit trail contains **raw prompts and responses** (kept 30 days in
Loki and in `monitoring/logs/`, both gitignored). Anyone with a UI key can
consume models and appear in the audit as that identity — treat
`gateway/users.json` like a password file. Ollama itself is still reachable
directly on `:11434`; firewall it to localhost if the gateway must become the
only entry point.

## License

[MIT](LICENSE)
