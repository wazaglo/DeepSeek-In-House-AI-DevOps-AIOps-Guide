import requests
import json
import time
import os
from prometheus_api_client import PrometheusConnect

# Configuration
PROM_URL = 'http://localhost:9090'
OLLAMA_URL = 'http://localhost:11434/api/generate'
MODEL = 'deepseek-coder:1.3b'
METRIC_FILE = 'monitoring/metrics/ai_prediction.prom'

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
        response = requests.post(OLLAMA_URL, json=payload).json().get('response', '')
        # Parse simple lines
        score = 50
        text = "No prediction"
        for line in response.split('\n'):
            if 'SCORE:' in line:
                try: score = int(''.join(filter(str.isdigit, line)))
                except: pass
            if 'TEXT:' in line:
                text = line.replace('TEXT:', '').strip()
        return score, text
    except:
        return 0, "Error connecting to AI"

if __name__ == "__main__":
    print("AI Monitor version 2 started...")
    while True:
        try:
            m = get_metrics()
            score, text = ask_ai(m)
            # Write Prometheus Format
            # ai_server_risk{insight="..."} 45
            content = f'# HELP ai_server_risk_level AI predicted risk level 0-100\n'
            content += f'# TYPE ai_server_risk_level gauge\n'
            content += f'ai_server_risk_level{{insight="{text}"}} {score}\n'
            
            with open(METRIC_FILE + '.tmp', 'w') as f:
                f.write(content)
            os.rename(METRIC_FILE + '.tmp', METRIC_FILE)
            print(f"Updated AI Metric: Score {score}")
        except Exception as e:
            print(f"Loop error: {e}")
        time.sleep(60) # Faster updates for testing
