import json
import os
from fastapi import FastAPI, Request, HTTPException
import redis
import time

from urllib.parse import urlparse

# No load_dotenv here like in rclient because we expect this script
# run by Heroku (or Docker) with exported vars

SEC_KEY=os.getenv("SEC_KEY", 'DEFAULT_KEY')
REDIS_URL=os.getenv("REDIS_URL", '')

def current_milli_time():
    return round(time.time() * 1000)
print("Starting web server")
app = FastAPI()

url = urlparse(REDIS_URL)
#r = redis.Redis(host=url.hostname, port=url.port, password=url.password, ssl=False, ssl_cert_reqs=None)
r = redis.Redis(
    host=url.hostname, 
    port=url.port, 
    password=url.password, 
    ssl=True, 
    ssl_cert_reqs=None,  # For self-signed certs
    ssl_ca_certs='./ssl/ca.crt',  # Path to CA certificate
    decode_responses=True
)


@app.get("/")
async def root():
    return {"message": "TradingView-Webhook-Bridge"}

@app.post("/webhook")
async def webhook(request: Request):
    body = await request.body()
    headers = request.headers
    qparams = request.query_params
    pparams = request.path_params

    if 'text/plain' in headers['content-type']:
        raise HTTPException(status_code=400, detail='Alert Message must be of type application/json')
    elif 'application/json' in headers['content-type']:
        data = await request.json()
        if 'key' not in data:
            raise HTTPException(status_code=401, detail='Missing auth key')
        key = data['key']
        if key == SEC_KEY:
            if 'data' not in data:
                raise HTTPException(status_code=400, detail='Wrong Alert message format, "data" field not found!')
            data = data['data']
            data['ttl'] = current_milli_time() + 120 * 1000
            print(f'Publishing TradingView Alert {data}')
            r.lpush('signals', json.dumps(data))
            return {"success": True}
        else:
            raise HTTPException(status_code=401, detail='Wrong auth key')

@app.post("/pop-event")
async def pop_event(request: Request):
    data = await request.json()
    if 'key' not in data:
        raise HTTPException(status_code=401, detail='Missing auth key')
    key = data['key']
    if key == SEC_KEY:
        event = r.rpop('signals')
        if event is not None:
            return json.loads(event)
        else:
            return {"empty": True}
    else:
        raise HTTPException(status_code=401, detail='Wrong auth key')
