import urllib.request
import json

def api(method, path, body=None):
    req = urllib.request.Request(f'http://localhost:8765{path}', method=method)
    req.add_header('Content-Type', 'application/json')
    if body:
        req.data = json.dumps(body).encode('utf-8')
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode('utf-8'))
    except Exception as e:
        return {'error': str(e)}

print(api('GET', '/api/v1/settings/deployment'))
print(api('GET', '/api/v2/messenger-accounts'))
