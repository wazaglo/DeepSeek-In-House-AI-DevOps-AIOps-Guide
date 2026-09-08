import re
import os
import time

import requests
from prometheus_api_client import PrometheusConnect

# Configuration
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROM_URL = os.environ.get('PROM_URL', 'http://localhost:9090')
OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://localhost:11434/api/generate')
MODEL = os.environ.get('DEEPSEEK_MODEL', 'deepseek-coder:1.3b')
METRIC_FILE = os.environ.get(
    'METRIC_FILE', os.path.join(REPO_ROOT, 'monitoring', 'metrics', 'ai_prediction.prom'))

pc = PrometheusConnect(url=PROM_URL, disable_ssl=True)

def get_metrics():
    cpu_query = '100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)'
    mem_query = 'node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes * 100'
    cpu_data = pc.custom_query(query=cpu_query)
    mem_data = pc.custom_query(query=mem_query)
    return {
        'cpu': round(float(cpu_data[0]['value'][1]), 2) if cpu_data else 0,
        'mem': round(float(mem_data[0]['value'][1]), 2) if mem_data else 0
    }

def ask_ai(metrics):
    prompt = f"""
    Analyze these server metrics: CPU {metrics['cpu']}%, Memory Available {metrics['mem']}%
    1. Give a Risk Score (0-100) where 100 is a total crash.
    2. Give a 1-sentence prediction for the next hour.
    Format your output exactly like this:
    SCORE: [number]
    TEXT: [sentence]
    """
    payload = {"model": MODEL, "prompt": prompt, "stream": False}
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=55)
        response.raise_for_status()
        text = response.json().get('response', '')
    except requests.RequestException as e:
        print(f"AI request failed: {e}")
        return None, None

    score = None
    insight = 'No prediction'
    score_match = re.search(r'SCORE:\s*(-?\d+)', text)
    if score_match:
        score = max(0, min(100, int(score_match.group(1))))
    text_match = re.search(r'TEXT:\s*(.+)', text)
    if text_match:
        insight = text_match.group(1).strip()
    return score, insight

def write_metric(score):
    # Prometheus textfile format: atomic write, bare gauge (no labels, to
    # avoid unbounded time-series churn from changing values).
    os.makedirs(os.path.dirname(METRIC_FILE) or '.', exist_ok=True)
    content = (
        '# HELP ai_server_risk_level AI predicted risk level 0-100\n'
        '# TYPE ai_server_risk_level gauge\n'
        f'ai_server_risk_level {score}\n'
    )
    tmp = METRIC_FILE + '.tmp'
    with open(tmp, 'w') as f:
        f.write(content)
    os.rename(tmp, METRIC_FILE)

if __name__ == "__main__":
    print("AI Monitor version 3 started...")
    while True:
        try:
            m = get_metrics()
            score, insight = ask_ai(m)
            if score is None:
                # Leave the previous metric in place rather than plotting a
                # failure as "healthy".
                print("Skipping metric update (AI unavailable)")
            else:
                write_metric(score)
                print(f"Updated AI Metric: Score {score} — {insight}")
        except Exception as e:
            print(f"Loop error: {e}")
        time.sleep(60)
