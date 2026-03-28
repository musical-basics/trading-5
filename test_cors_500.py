import urllib.request
import json
data = json.dumps({
    'name': 'test',
    'hypothesis': 'test',
    'rationale': 'test',
    'code': 'this will crash if we pass null to something or raise Exception',
    'model_tier': 'test',
    'input_tokens': 100,
    'output_tokens': 100,
    'cost_usd': 0.1
}).encode('utf-8')
req = urllib.request.Request('http://127.0.0.1:8000/api/alpha-lab/generate-swarm-save', data=data, headers={'Content-Type': 'application/json', 'Origin': 'http://localhost:3001'})
try:
    with urllib.request.urlopen(req) as response:
        print('Status:', response.status, response.headers)
except Exception as e:
    print('Failed:', getattr(e, 'code', e), getattr(e, 'headers', ''))
