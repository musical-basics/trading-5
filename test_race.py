import urllib.request
import json
import threading
import sys

def run_post(data):
    try:
        req = urllib.request.Request(
            'http://127.0.0.1:8000/api/alpha-lab/generate-swarm-save', 
            data=data.encode('utf-8'), 
            headers={'Content-Type': 'application/json', 'Origin': 'http://localhost:3001'}
        )
        with urllib.request.urlopen(req) as response:
            print('POST Status:', response.status)
            print('POST Headers:', response.headers)
            print('POST Body:', response.read().decode('utf-8'))
    except Exception as e:
        print('POST Failed:', getattr(e, 'code', e), getattr(e, 'headers', ''))

url = "http://127.0.0.1:8000/api/alpha-lab/generate-swarm-stream?agent_tiers=%7B%7D&agent_notes=%7B%7D"
req = urllib.request.Request(url, headers={'Origin': 'http://localhost:3001'})

try:
    with urllib.request.urlopen(req) as response:
        for line in response:
            line = line.decode('utf-8').strip()
            if line.startswith("data: "):
                payload = json.loads(line[6:])
                if payload.get("type") == "result":
                    print("Got result from stream. Firing POST!")
                    data = json.dumps({
                        "name": payload.get("name", "test"),
                        "hypothesis": "test",
                        "rationale": payload.get("rationale", ""),
                        "code": payload.get("code", ""),
                        "model_tier": payload.get("model_tier", "test"),
                        "input_tokens": payload.get("input_tokens", 0),
                        "output_tokens": payload.get("output_tokens", 0),
                        "cost_usd": payload.get("cost_usd", 0)
                    })
                    t = threading.Thread(target=run_post, args=(data,))
                    t.start()
                    t.join()  # wait for post to finish before exiting stream loop
        print("Stream ended happily")
except Exception as e:
    print("Stream Failed:", getattr(e, 'code', e), getattr(e, 'headers', ''))
