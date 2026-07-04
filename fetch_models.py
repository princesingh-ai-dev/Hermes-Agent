import requests

url = "https://openrouter.ai/api/v1/models"
response = requests.get(url)
models = response.json().get("data", [])

free_models = [m for m in models if m.get("pricing", {}).get("prompt", "1") == "0" and m.get("pricing", {}).get("completion", "1") == "0"]

print(f"Found {len(free_models)} free models.")
for m in free_models[:15]:
    print(f"- {m['id']} (Context length: {m.get('context_length', 'unknown')})")
