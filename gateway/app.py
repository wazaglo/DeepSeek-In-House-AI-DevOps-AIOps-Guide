#!/usr/bin/env python3
"""Ollama audit gateway.

A single controlled endpoint in front of Ollama. Every request is:
  1. Authenticated against gateway/users.json (API key -> user identity).
  2. Proxied to the upstream Ollama server.
  3. Audited: user, model, prompt, response, timings, token counts and
     errors are appended to an append-only JSONL audit log.
  4. Counted in Prometheus metrics exposed on /metrics.

Stdlib-only: no pip dependencies. The audit log is designed to be tailed
by Grafana Alloy and shipped to Loki (see monitoring/alloy/config.alloy).

Endpoints (mirroring the Ollama API):
  POST /api/generate   POST /api/chat   GET /api/tags
  GET  /api/version    GET  /metrics    GET  /health
"""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = os.environ.get('OLLAMA_UPSTREAM', 'http://127.0.0.1:11434')
LISTEN_HOST = os.environ.get('GATEWAY_HOST', '0.0.0.0')
LISTEN_PORT = int(os.environ.get('GATEWAY_PORT', '11435'))
USERS_FILE = os.environ.get(
    'GATEWAY_USERS_FILE',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'users.json'))
AUDIT_LOG = os.environ.get(
    'GATEWAY_AUDIT_LOG',
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 'monitoring', 'logs', 'gateway_audit.jsonl'))

MAX_BODY = 10 * 1024 * 1024        # 10 MB request cap
PROMPT_FIELD_MAX = 4000            # truncate prompts/responses in audit log

_llm_paths = ('/api/generate', '/api/chat')
_llm_re = re.compile(r'^/api/(generate|chat|tags|version)$')

_users_lock = threading.Lock()
_users_cache = {'mtime': 0.0, 'users': {}}

audit_lock = threading.Lock()

_metrics_lock = threading.Lock()
_counters = {}   # (user, model, path, status) -> count
_latency = {}    # path -> list of durations (capped)


def load_users():
    """Load users.json (mtime-cached). Format:
    [{"key": "...", "user": "alice", "team": "devops"}, ...]"""
    try:
        mtime = os.path.getmtime(USERS_FILE)
    except OSError:
        mtime = 0.0
    with _users_lock:
        if mtime != _users_cache['mtime']:
            users = {}
            if mtime:
                with open(USERS_FILE) as f:
                    for entry in json.load(f):
                        users[entry['key']] = {
                            'user': entry.get('user', 'unknown'),
                            'team': entry.get('team', ''),
                        }
            _users_cache['mtime'] = mtime
            _users_cache['users'] = users
        return dict(_users_cache['users'])


def audit(record):
    record['ts'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
    line = json.dumps(record, ensure_ascii=False, default=str)
    with audit_lock:
        os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)
        with open(AUDIT_LOG, 'a') as f:
            f.write(line + '\n')


def record_metric(user, model, path, status, duration):
    key = (user, model, path, status)
    with _metrics_lock:
        _counters[key] = _counters.get(key, 0) + 1
        lat = _latency.setdefault(path, [])
        lat.append(duration)
        if len(lat) > 2000:
            del lat[:len(lat) - 2000]


def render_metrics():
    with _metrics_lock:
        lines = [
            '# HELP ai_gateway_requests_total Audited proxy requests.',
            '# TYPE ai_gateway_requests_total counter',
        ]
        for (user, model, path, status), n in sorted(_counters.items()):
            lines.append(
                f'ai_gateway_requests_total{{user="{user}",model="{model}",'
                f'path="{path}",status="{status}"}} {n}')
        lines += [
            '# HELP ai_gateway_request_duration_seconds Proxy latency.',
            '# TYPE ai_gateway_request_duration_seconds summary',
        ]
        for path, samples in sorted(_latency.items()):
            s = sorted(samples)
            lines.append(f'ai_gateway_request_duration_seconds{{path="{path}",quantile="0.5"}} {s[len(s)//2]:.4f}')
            lines.append(f'ai_gateway_request_duration_seconds{{path="{path}",quantile="0.95"}} {s[min(len(s)-1, int(len(s)*0.95))]:.4f}')
            lines.append(f'ai_gateway_request_duration_seconds_sum{{path="{path}"}} {sum(s):.4f}')
            lines.append(f'ai_gateway_request_duration_seconds_count{{path="{path}"}} {len(s)}')
    return ('\n'.join(lines) + '\n').encode()


class Gateway(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):  # keep stdout quiet
        pass

    def _send(self, status, body, ctype='application/json'):
        self.send_response(status)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _identity(self):
        auth = self.headers.get('Authorization', '')
        key = auth.removeprefix('Bearer ').strip() if auth else ''
        if not key:  # UIs commonly use X-API-Key
            key = self.headers.get('X-API-Key', '').strip()
        if not key:  # some clients only allow basic auth
            import base64
            if auth.startswith('Basic '):
                try:
                    key = base64.b64decode(auth[6:]).decode().split(':')[0]
                except Exception:
                    key = ''
        if not key and '?' in self.path:  # UIs that cannot set headers
            import urllib.parse
            key = urllib.parse.parse_qs(self.path.split('?', 1)[1]).get('key', [''])[0]
        user = load_users().get(key)
        return (user['user'], user['team']) if user else (None, None)

    def _proxy(self, body=None, method='POST'):
        path = self.path.split('?')[0]
        started = time.time()
        user, team = self._identity()
        if user is None:
            record_metric('anonymous', '', path, 401, time.time() - started)
            audit({'event': 'request', 'user': None, 'path': path,
                   'status': 401, 'error': 'missing or invalid API key'})
            return self._send(401, json.dumps(
                {'error': 'missing or invalid API key'}).encode())

        req = urllib.request.Request(UPSTREAM + self.path, data=body, method=method)
        req.add_header('Content-Type', self.headers.get('Content-Type', 'application/json'))
        model, prompt = '', ''
        if body:
            try:
                parsed = json.loads(body)
                model = parsed.get('model', '')
                prompt = parsed.get('prompt') or parsed.get('messages', '')
            except (ValueError, AttributeError):
                pass
        prompt = str(prompt)[:PROMPT_FIELD_MAX]

        try:
            with urllib.request.urlopen(req, timeout=600) as up:
                raw = up.read()
                status = up.status
        except urllib.error.HTTPError as e:
            raw, status = e.read(), e.code
        except Exception as e:
            status, raw = 502, json.dumps({'error': f'upstream unreachable: {e}'}).encode()
            audit({'event': 'request', 'user': user, 'team': team, 'path': path,
                   'model': model, 'prompt': prompt, 'status': status,
                   'error': str(e), 'duration_s': round(time.time() - started, 3)})
            record_metric(user, model, path, status, time.time() - started)
            return self._send(502, raw)

        response_text, usage = '', {}
        try:
            data = json.loads(raw)
            response_text = str(data.get('response') or data.get('message', {}).get('content', '') or '')[:PROMPT_FIELD_MAX]
            usage = {k: data[k] for k in ('eval_count', 'prompt_eval_count', 'total_duration') if k in data}
        except ValueError:
            pass  # /api/tags, /api/version, streaming — store nothing bulky

        record_metric(user, model or '-', path, status, time.time() - started)
        if path in _llm_paths or path == '/api/tags':
            audit({'event': 'request', 'user': user, 'team': team, 'path': path,
                   'model': model, 'prompt': prompt, 'response': response_text,
                   'status': status, 'usage': usage,
                   'duration_s': round(time.time() - started, 3)})
        self._send(status, raw)

    def do_POST(self):
        if not _llm_re.match(self.path.split('?')[0]):
            return self._send(404, json.dumps({'error': 'not found'}).encode())
        length = int(self.headers.get('Content-Length', 0) or 0)
        if length > MAX_BODY:
            return self._send(413, json.dumps({'error': 'request too large'}).encode())
        self._proxy(self.rfile.read(length) if length else b'')

    def do_GET(self):
        if self.path.split('?')[0] == '/metrics':
            return self._send(200, render_metrics(), 'text/plain; version=0.0.4')
        if self.path == '/health':
            return self._send(200, json.dumps({'status': 'ok'}).encode())
        self._proxy(method='GET')


if __name__ == '__main__':
    srv = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), Gateway)
    print(f'Ollama audit gateway on :{LISTEN_PORT} -> {UPSTREAM}', flush=True)
    srv.serve_forever()
