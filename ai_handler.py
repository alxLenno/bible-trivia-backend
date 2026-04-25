import os
import json
import requests
import re

# AI Configuration
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
HF_TOKEN = os.environ.get("HF_TOKEN", "")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
HF_CHAT_URL = "https://lennoxkk-trivia-model.hf.space/chat"
HF_TRIVIA_URL = "https://lennoxkk-trivia-model.hf.space/api/generate_trivia"

MODEL_MAP = {
    "llama-3-8b": "llama-3.1-8b-instant",
    "llama-3-70b": "llama-3.1-70b-versatile",
    "mixtral": "mixtral-8x7b-32768",
    "gemma": "gemma2-9b-it"
}

def handle_chat(message, history=None, model_id="llama-3-8b"):
    """Handles AI chat with Groq and Hugging Face fallback."""
    # Ensure history is a valid list
    if history is None or not isinstance(history, list):
        history = []
        
    # 1. Try Groq (Fast Choice)
    groq_model = MODEL_MAP.get(model_id, MODEL_MAP["llama-3-8b"])
    try:
        print(f"[*] Attempting Groq Chat with model {groq_model}...")
        groq_payload = {
            "model": groq_model,
            "messages": [
                {"role": "system", "content": "You are the AI Scribe, a knowledgeable biblical scholar. Help users understand sacred texts, explain history, and answer questions about the Bible accurately and respectfully."},
                *history,
                {"role": "user", "content": message}
            ],
            "temperature": 0.7,
            "max_tokens": 1024
        }
        resp = requests.post(GROQ_URL, headers={"Authorization": f"Bearer {GROQ_API_KEY}"}, json=groq_payload, timeout=10)
        if resp.ok:
            result = resp.json()
            return {
                "success": True,
                "response": result['choices'][0]['message']['content'],
                "source": "groq"
            }
        print(f"[!] Groq failed: {resp.status_code}")
    except Exception as e:
        print(f"[!] Groq exception: {e}")

    # 2. Fallback to Hugging Face
    try:
        print("[*] Falling back to Hugging Face Chat...")
        hf_payload = {"message": message, "history": history}
        resp = requests.post(HF_CHAT_URL, json=hf_payload, timeout=20)
        if resp.ok:
            result = resp.json()
            return {
                "success": True,
                "response": result.get('response', result.get('text', '')),
                "audio_url": result.get('audio_url'),
                "source": "huggingface"
            }
    except Exception as e:
        print(f"[!] Hugging Face fallback failed: {e}")

    return {"success": False, "error": "All AI backends failed"}

def handle_generate_trivia(prompt):
    """Handles trivia generation with Groq and Hugging Face fallback."""
    if not prompt:
        return {"success": False, "error": "No prompt provided"}
        
    # 1. Try Groq (Fast Choice)
    try:
        print("[*] Attempting Groq Trivia Generation...")
        groq_payload = {
            "model": "llama-3.1-70b-versatile",
            "messages": [
                {"role": "system", "content": "You are a Bible trivia generator. Output ONLY a valid JSON array of questions."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.8,
            "response_format": {"type": "json_object"}
        }
        resp = requests.post(GROQ_URL, headers={"Authorization": f"Bearer {GROQ_API_KEY}"}, json=groq_payload, timeout=20)
        if resp.ok:
            result = resp.json()
            content = result['choices'][0]['message']['content']
            parsed = json.loads(content)
            
            # Extract array if wrapped in object
            if not isinstance(parsed, list):
                for v in parsed.values():
                    if isinstance(v, list):
                        parsed = v
                        break
            
            return {
                "success": True,
                "response": parsed,
                "source": "groq"
            }
        print(f"[!] Groq Trivia failed: {resp.status_code}")
    except Exception as e:
        print(f"[!] Groq Trivia exception: {e}")

    # 2. Fallback to Hugging Face
    try:
        print("[*] Falling back to Hugging Face Trivia...")
        hf_payload = {"prompt": prompt}
        resp = requests.post(HF_TRIVIA_URL, json=hf_payload, timeout=30)
        if resp.ok:
            result = resp.json()
            raw_response = result.get('response', '')
            
            # Parse if it's a string
            if isinstance(raw_response, str):
                try:
                    match = re.search(r'\[\s*\{.*\}\s*\]', raw_response, re.DOTALL)
                    if match:
                        raw_response = json.loads(match.group(0))
                    else:
                        raw_response = json.loads(raw_response)
                except: pass
            
            return {
                "success": True,
                "response": raw_response,
                "source": "huggingface"
            }
    except Exception as e:
        print(f"[!] Hugging Face Trivia fallback failed: {e}")

    return {"success": False, "error": "All AI backends failed"}
