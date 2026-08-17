import os
import requests

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

payload = {
    "model": "openai/gpt-oss-20b",
    "messages": [{"role": "user", "content": "Hello"}]
}
resp = requests.post(GROQ_URL, headers={"Authorization": f"Bearer {GROQ_API_KEY}"}, json=payload)
print("Groq Llama 8b:", resp.status_code, resp.text)

payload["model"] = "openai/gpt-oss-120b"
resp = requests.post(GROQ_URL, headers={"Authorization": f"Bearer {GROQ_API_KEY}"}, json=payload)
print("Groq GPT OSS:", resp.status_code, resp.text)
