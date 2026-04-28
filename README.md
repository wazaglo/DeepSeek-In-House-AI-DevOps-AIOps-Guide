# DeepSeek In-House AI - DevOps & AIOps Guide

This guide documents your private, self-hosted DeepSeek AI environment, featuring real-time AIOps monitoring and multiple DevOps-focused interfaces.

🎯 **Benefits of Our In-House Setup**
- **Free & Private:** No API costs; code never leaves your private server.
- **AIOps Integration:** AI-driven system health predictions visible in Grafana.
- **Multi-Interface:** Optimized UIs for different tasks (Chat, DevOps, Lite).
- **Scalable:** Easy to add new models and monitoring collectors.

🚀 **Quickstart**

### 🏠 Local Setup (LAN Access)
Prerequisites:
- **Node.js 18+** for local CLI tools.
- **Ollama Client** for local terminal integration.

1. **Connect to the Server CLI:**
   ```bash
   export OLLAMA_HOST="http://localhost:11434"
   ollama run deepseek-coder:1.3b
   ```

2. **Access the Web UIs:**
   - **Chatbot Ollama (3000):** Fast, no-login required interface.
   - **NextChat (3001):** ChatGPT-style UI for private sessions.
   - **Big-AGI (3002):** Professional "DevOps Grade" interface with folder management.

3. **Monitor with AIOps (4000):**
   - Access **Grafana** at `http://localhost:4000`.
   - View the `ai_server_risk_level` metric for AI-driven stability forecasts.

---

📖 **Popular DevOps Tasks**

### 📊 AIOps & Monitoring
- **Predictive Stability:** The AI analyzes CPU/RAM trends every 60s.
- **Threshold Alerts:** See the "Risk Score" spike in Grafana when the AI detects high load.
- **Log Analysis:** Use the CLI to pipe logs: `cat sys.log | ollama run deepseek-coder:1.3b "Explain these errors"`

### 🛠️ Development & Scripting
- **Project Setup:** `deepseek > Create a FastAPI project with Docker and PostgreSQL`
- **Code Optimization:** `deepseek > Refactor this Python module for better time complexity`
- **Unit Testing:** `deepseek > Generate pytest cases for this repository`

---

🔧 **Configuration**

### Environment Variables (.env)
Create this in your project root for local CLI tools to point to your AI server:
```bash
# Server Connection
OLLAMA_HOST=http://localhost:11434
DEEPSEEK_MODEL=deepseek-coder:1.3b

# Monitoring Stats
PROM_URL=http://localhost:9090
GRAFANA_URL=http://localhost:4000
```

### Local Models Available
| Model | Size | Best For | Speed |
| :--- | :--- | :--- | :--- |
| **deepseek-coder:1.3b** | 776MB | Quick CLI tasks, AIOps bridge | **Fast** |
| **deepseek-coder:6.7b** | 3.8GB | Complex refactoring, logic | **Slow (CPU bound)** |

---

🛠️ **Troubleshooting**

### 1. Connection Refused
Ensure the Ollama service is listening on all interfaces:
```bash
# Check service status
systemctl status ollama
# Verify port listening
ss -tulpn | grep 11434
```

### 2. Web UI Model Not Found
If Big-AGI or NextChat doesn't show models:
- Check `OLLAMA_ORIGINS="*"` in the service override.
- Manually enter the host `http://localhost:11434` in the UI settings.

### 3. AIOps Bridge Not Updating
Check the status of the Python monitor:
```bash
ps aux | grep ai_monitor.py
tail -f ai_monitor.log
```

---

🔄 **Infrastructure as Code**
The `configs/` directory contains Docker Compose files for:
- `prometheus.yml`: Monitoring configuration.
- `ui-big-agi.yml`: Professional UI deployment.
- `ui-nextchat.yml`: ChatGPT-style UI deployment.
- `ui-chatbot-ollama.yml`: Lightweight UI deployment.

🎉 **You're Ready!**
Your DeepSeek AI is now a core part of your DevOps infrastructure. Private, free, and monitored.
