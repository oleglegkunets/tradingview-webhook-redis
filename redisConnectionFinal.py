import requests
import json
import time
import redis
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()

# Create session with connection pooling and retry logic
session = requests.Session()
retry_strategy = Retry(
    total=3,  # retry up to 3 times
    backoff_factor=1,  # wait 1, 2, 4 seconds between retries
    status_forcelist=[500, 502, 503, 504]  # retry on server errors
)
adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
session.mount("http://", adapter)
session.mount("https://", adapter)

urlT = "http://213.58.150.82:8080/webhook"

SEC_KEY=os.getenv("SEC_KEY", 'DEFAULT_KEY')
REDIS_URL=os.getenv("REDIS_URL", '')

payload = json.dumps({
  "key": SEC_KEY,
  "data": {
    "strategy-order-action": "buy",
    "strategy-order-price": 1.1234,
    "ticker": "EUR/USD"
  }
})
headers = {
  'Content-Type': 'application/json'
}
total_elapsed = 0
average_elapsed = 0
i = 1

url = urlparse(REDIS_URL)

r = redis.Redis(host=url.hostname, port=url.port, password=url.password, ssl=True, ssl_ca_certs='./ca.crt', ssl_cert_reqs=None)

while i > 0:
  start_time = time.perf_counter()
  try:
    # Increased timeout to 60 seconds for better reliability
    response = session.post(urlT, headers=headers, data=payload, timeout=60)
    if response.status_code != 200:
      print(f"Http error while sending message: {response.status_code} : {response.content}")
      break
  except requests.exceptions.ReadTimeout:
    print(f"Request {i}: Read timeout after 60 seconds, continuing...")
    time.sleep(5)  # Wait 5 seconds before retrying
    continue
  except requests.exceptions.RequestException as e:
    print(f"Request {i}: Request failed: {e}, continuing...")
    time.sleep(5)  # Wait 5 seconds before retrying
    continue

  e = r.brpop('signals', 0)
  if e is None:
    print("Message not received!")
    break
  # j = json.dumps(e[1].decode())
  elapsed_ms = (time.perf_counter() - start_time) * 1000.0
  msg = e[1].decode()
  print(f'Event: {msg}')

  total_elapsed += elapsed_ms
  average_elapsed = total_elapsed / i

  print(f"HTTP {response.status_code} in {elapsed_ms:.2f} ms")
  print(response.text)
  print(f"Average HTTP success in : {average_elapsed:.2f}")
  i = i + 1
  time.sleep(1)