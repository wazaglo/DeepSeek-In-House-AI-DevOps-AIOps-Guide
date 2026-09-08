# DeepSeek In-House AI — DevOps & AIOps Guide

A private, self-hosted DeepSeek AI environment: local LLM inference via
[Ollama](https://ollama.com), three chat interfaces, a Prometheus/Grafana
observability stack, and an AIOps bridge that turns system metrics into an
AI-assessed risk score.

- **Free & private** — no API costs; your code never leaves the server.
- **AIOps** — an AI-generated `ai_server_risk_level` metric in Grafana.
- **Multi-interface** — lightweight chat (3000), ChatGPT-style sessions
  (3001), and a professional workspace (3002).

## Prerequisites

| Requirement | Used for |
| :--- | :--- |
| [Ollama](https://ollama.com) (installed as a systemd service) | LLM inference on port 11434 |
| Docker + Docker Compose | Monitoring stack and web UIs |
| Python 3.10+ | AIOps bridge (`aiops/ai_monitor.py`) |
| Node.js 18+ (optional) | Local CLI tools |

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

### 2. Chat UIs

```bash
docker compose -f uis/docker-compose.yml up -d
```

| Port | UI | Notes |
| :--- | :--- | :--- |
| 3000 | Chatbot Ollama | Fast, no-login interface |
| 3001 | NextChat | ChatGPT-style UI, private sessions |
| 3002 | Big-AGI | "DevOps grade" workspace with folder management |

### 3. Monitoring stack

```bash
docker compose -f monitoring/docker-compose.yml up -d
```

| Port | Service |
| :--- | :--- |
| 4000 | Grafana dashboards |
| 9090 | Prometheus |
| 9100 | node-exporter (host metrics + textfile collector) |
| 8082 | cAdvisor (container metrics) |

### 4. AIOps bridge

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
monitoring/  docker-compose.yml, prometheus.yml,
             metrics/                             Observability stack
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

For local CLI tools, point clients at the server:

```bash
export OLLAMA_HOST="http://localhost:11434"
export DEEPSEEK_MODEL="deepseek-coder:1.3b"
```

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

**A UI shows no models** — check the UI's Ollama host setting. Containers
must use `http://host.docker.internal:11434` (already set in
`uis/docker-compose.yml`), and the service needs `OLLAMA_ORIGINS=*`.

**`ai_server_risk_level` not updating** — check the bridge and the chain:

```bash
tail -f ai_monitor.log                                  # bridge output
curl -s localhost:9090/api/v1/query?query=ai_server_risk_level
```

The metric file must land in `monitoring/metrics/` (mounted read-only into
node-exporter as `/textfile`).

## Security note

This setup binds Ollama to all interfaces with `OLLAMA_ORIGINS=*` and exposes
Grafana, Prometheus, and cAdvisor directly. That is acceptable on a trusted
home LAN only. On any shared network, firewall the ports and restrict
`OLLAMA_ORIGINS` to your UI origins.
