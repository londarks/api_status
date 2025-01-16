import time
import threading
import requests
import redis
import json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# -------------------------------------------------------------------------------
# CONFIGURAÇÕES
# -------------------------------------------------------------------------------

CHECK_INTERVAL = 30 # 30 segundos acada checagem
MAX_RECORDS = 720 * 4  # 4 horas (30s cada checagem)
APIS_TO_MONITOR = [
    {"name": "API - 1", "url": "https://host.com/api/v1/heartbeat/"},
    {"name": "API - 2", "url": "https://host.com/api/v1/heartbeat/"},
    {"name": "API - 3", "url": "https://host.com/api/v1/heartbeat/"},
    # Adicione mais endpoints conforme necessário
]

import os
redis_host = os.getenv("REDIS_HOST", "localhost")
r = redis.Redis(host=redis_host, port=6379, db=0)

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")

def monitor_apis():
    """
    Roda em loop, faz checagem das APIs e armazena no Redis em formato JSON.
    """
    while True:
        for api_info in APIS_TO_MONITOR:
            name = api_info["name"]
            url = api_info["url"]

            start_time = time.time()
            status_code = 0
            error = ""

            try:
                response = requests.get(url, timeout=5)
                status_code = response.status_code
            except requests.exceptions.RequestException as e:
                error = str(e)

            end_time = time.time()
            response_time = round((end_time - start_time) * 1000, 2)

            # Registro
            log_entry = {
                "timestamp": time.time(),
                "status_code": status_code,
                "error": error,
                "response_time_ms": response_time
            }

            key = f"api_status:{name}"
            # Salva em JSON
            r.lpush(key, json.dumps(log_entry))
            # Limita a lista
            r.ltrim(key, 0, MAX_RECORDS - 1)

        time.sleep(CHECK_INTERVAL)

def start_monitor_thread():
    t = threading.Thread(target=monitor_apis, daemon=True)
    t.start()

start_monitor_thread()

# ------------------------------------------------------------------------------
# ROTAS
# ------------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/status")
def get_status():
    """
    Retorna o status MAIS RECENTE de cada API.
    """
    import json
    api_status_list = []

    for api_info in APIS_TO_MONITOR:
        name = api_info["name"]
        key = f"api_status:{name}"

        latest_data = r.lindex(key, 0)
        if latest_data:
            # Decodifica bytes -> str, carrega JSON
            latest_data = json.loads(latest_data.decode("utf-8"))

            api_status_list.append({
                "name": name,
                "status_code": latest_data["status_code"],
                "error": latest_data["error"],
                "response_time_ms": latest_data["response_time_ms"],
                "timestamp": latest_data["timestamp"],
            })
        else:
            api_status_list.append({
                "name": name,
                "status_code": None,
                "error": "Sem dados ainda",
                "response_time_ms": None,
                "timestamp": None
            })

    return {"data": api_status_list}


@app.get("/api/history")
def get_history(count: int = 20):
    """
    Retorna as últimas `count` requisições (por default 20) de cada API.
    Cada item no formato JSON.
    """
    import json
    history_data = {}

    for api_info in APIS_TO_MONITOR:
        name = api_info["name"]
        key = f"api_status:{name}"

        # Pega as últimas `count` do Redis
        raw_list = r.lrange(key, 0, count - 1)
        parsed_list = []

        for item in raw_list:
            # item é bytes
            decoded = item.decode("utf-8")
            parsed = json.loads(decoded)
            parsed_list.append(parsed)

        history_data[name] = parsed_list

    return {"data": history_data}
