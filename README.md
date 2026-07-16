# DeepSeek In-House AI — DevOps & AIOps Guide

[![CI](https://github.com/wazaglo/DeepSeek-In-House-AI-DevOps-AIOps-Guide/actions/workflows/ci.yml/badge.svg)](https://github.com/wazaglo/DeepSeek-In-House-AI-DevOps-AIOps-Guide/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Ollama](https://img.shields.io/badge/Ollama-000?logo=ollama&logoColor=white)](https://ollama.ai/)
[![DeepSeek](https://img.shields.io/badge/DeepSeek-4A6CF7?logo=deepseek&logoColor=white)](https://deepseek.com/)

A private, self-hosted DeepSeek AI environment with real-time AIOps monitoring, multiple web interfaces, and DevOps-focused tooling. No API costs, no data leaving your server.

---

## Features

- **Private & Free** — Self-hosted on your infrastructure. Zero API costs.
- **AIOps Integration** — AI-driven system health predictions in Grafana
- **Multi-Interface** — Choose the right UI for the task: chat, dev, or lightweight
- **Monitoring Stack** — Prometheus + Grafana + Node Exporter + cAdvisor
- **Extensible** — Easily add new models and monitoring collectors

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Ollama Server                      │
│              deepseek-coder:1.3b / 6.7b              │
└────────┬────────────┬────────────┬───────────────────┘
         │            │            │
         ▼            ▼            ▼
   ┌──────────┐ ┌──────────┐ ┌──────────┐
   │ Chatbot  │ │ NextChat │ │ Big-AGI  │
   │ :3000    │ │ :3001    │ │ :3002    │
   └──────────┘ └──────────┘ └──────────┘
         │
         ▼
   ┌──────────────────────────────────────┐
   │         AI Monitor (Python)           │
   │    Reads Prometheus → Ollama → Risk   │
   └──────────┬───────────────────────────┘
              │
              ▼
   ┌──────────────────────────────────────┐
   │         Monitoring Stack              │
   │  Prometheus :9090                     │
   │  Grafana    :4000                     │
   │  Node Exp.  :9100                     │
   │  cAdvisor   :8082                     │
   └──────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Server with Docker and Docker Compose installed
- 4GB+ RAM (8GB recommended for 6.7b model)
- Node.js 18+ for local CLI tools (optional)

### 1. Start the Monitoring Stack

```bash
docker compose up -d
```

### 2. Install Ollama with DeepSeek

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull DeepSeek models
ollama pull deepseek-coder:1.3b
ollama pull deepseek-coder:6.7b
```

### 3. Start the AI Monitor

```bash
pip install requests prometheus-api-client
python scripts/ai_monitor.py
```

### 4. Access the Web UIs

| Interface | URL | Purpose |
|-----------|-----|---------|
| Chatbot Ollama | http://localhost:3000 | Fast, no-login chat |
| NextChat | http://localhost:3001 | ChatGPT-style UI |
| Big-AGI | http://localhost:3002 | Professional DevOps interface |
| Grafana | http://localhost:4000 | AIOps dashboards |

Each UI is deployable independently via config files in `configs/`:

```bash
docker compose -f configs/ui-big-agi.yml up -d
docker compose -f configs/ui-nextchat.yml up -d
docker compose -f configs/ui-chatbot-ollama.yml up -d
```

---

## AIOps Monitoring

The AI monitor (`scripts/ai_monitor.py`) runs a continuous loop:

1. Queries Prometheus for CPU and memory metrics
2. Sends metrics to DeepSeek for analysis
3. Generates a **risk score (0–100)** and prediction text
4. Writes the result as a Prometheus metric file for Grafana

### Viewing AI Predictions in Grafana

1. Open Grafana at http://localhost:4000 (default login: admin/admin)
2. Add Prometheus as a data source (http://prometheus:9090)
3. Import a dashboard or query the `ai_server_risk_level` metric

---

## DevOps Use Cases

### Code Generation & Refactoring

```bash
# Generate boilerplate
ollama run deepseek-coder:1.3b "Create a FastAPI project with Docker and PostgreSQL"

# Code review
ollama run deepseek-coder:1.3b "Review this Python module for security issues"

# Unit tests
ollama run deepseek-coder:1.3b "Generate pytest cases for this auth module"
```

### Log Analysis

```bash
tail -100 /var/log/syslog | ollama run deepseek-coder:1.3b "Explain these errors"
```

### Infrastructure Troubleshooting

```bash
ollama run deepseek-coder:1.3b "Debug this Terraform plan: $(cat plan.log)"
```

---

## Project Structure

```
├── .github/workflows/ci.yml    # CI pipeline (linting, validation)
├── scripts/
│   └── ai_monitor.py           # AIOps monitoring daemon
├── configs/
│   ├── docker-compose.yml      # Monitoring stack (Prometheus, Grafana)
│   ├── ui-big-agi.yml          # Big-AGI deployment
│   ├── ui-nextchat.yml         # NextChat deployment
│   └── ui-chatbot-ollama.yml   # Chatbot Ollama deployment
├── docker-compose.yml          # Root monitoring stack
├── .yamllint                   # YAML linting rules
├── .gitignore
├── LICENSE
└── README.md
```

## Configuration

### Environment Variables

```bash
# Server Connection
OLLAMA_HOST=http://localhost:11434
DEEPSEEK_MODEL=deepseek-coder:1.3b

# Monitoring
PROM_URL=http://localhost:9090
GRAFANA_URL=http://localhost:4000
```

### Available Models

| Model | Size | Best For | Speed |
|-------|------|----------|-------|
| deepseek-coder:1.3b | 776MB | Quick CLI tasks, AIOps | Fast |
| deepseek-coder:6.7b | 3.8GB | Complex refactoring | Slow (CPU) |

---

## Troubleshooting

### Connection Refused

```bash
systemctl status ollama
ss -tulpn | grep 11434
```

### AI Monitor Not Updating

```bash
ps aux | grep ai_monitor.py
tail -f ai_monitor.log
```

### Web UI Not Showing Models

Ensure `OLLAMA_ORIGINS="*"` is set in the Ollama service override, or manually enter `http://localhost:11434` in the UI settings.

---

## License

[MIT](LICENSE) © 2026 Wisdom Azaglo
