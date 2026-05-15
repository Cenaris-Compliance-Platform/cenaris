import requests
try:
    r = requests.get('http://localhost:8080/api/v1/walkthroughs/eligible', timeout=5)
    print('status', r.status_code)
    try:
        print('body:', r.json())
    except Exception:
        print('body(not json):', r.text[:200])
except Exception as e:
    print('error', e)
