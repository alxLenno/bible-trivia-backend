import os
import json
import requests
import re
from scriptorium import build_scriptorium_prompt
from scriptorium.genre_detector import detect_genre
from scriptorium.dual_scalpel import get_scalpel_context
from scriptorium.trivia_engine import build_scriptorium_trivia_prompt

# AI Configuration
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
HF_TOKEN = os.environ.get("HF_TOKEN", "")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
HF_CHAT_URL = "https://lennoxkk-trivia-model.hf.space/chat"
HF_TRIVIA_URL = "https://lennoxkk-trivia-model.hf.space/api/generate_trivia"

MODEL_MAP = {
    # --- Standard Chat ---
    "llama-3-8b": "llama-3.1-8b-instant",
    "llama-3-70b": "llama-3.3-70b-versatile",
    
    # --- Scriptorium ---
    "gpt-oss-120b": "openai/gpt-oss-120b",
    "qwen3-32b": "qwen/qwen3-32b"
}

SCRIPTORIUM_DEFAULT_MODEL = "gpt-oss-120b"

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

def handle_scriptorium_chat(message, history=None, context=None):
    """Handles chat specifically routed through the Scriptorium framework."""
    if history is None:
        history = []
        
    language = context.get('language', 'en') if context else 'en'
    book = context.get('book', '') if context else ''
    chapter = context.get('chapter', None) if context else None
    turn_count = context.get('turn_count', len(history) // 2) if context else len(history) // 2
    passage = context.get('passage_text', '') if context else ''
    
    # Detect genre
    genre = detect_genre(book, chapter)
    
    # Get Dual Scalpel data for Swahili
    scalpel_data = get_scalpel_context(message + " " + passage) if language == 'sw' else None
    
    # Build the enhanced system prompt
    system_prompt = build_scriptorium_prompt(
        user_message=message,
        passage_context=passage,
        language=language,
        genre=genre,
        turn_count=turn_count,
        scalpel_data=scalpel_data
    )
    
    try:
        print(f"[*] Attempting Scriptorium Chat with model {SCRIPTORIUM_DEFAULT_MODEL}...")
        groq_payload = {
            "model": MODEL_MAP[SCRIPTORIUM_DEFAULT_MODEL],
            "messages": [
                {"role": "system", "content": system_prompt},
                *history,
                {"role": "user", "content": message}
            ],
            "temperature": 0.6, # Slightly lower for deeper theological reasoning
            "max_tokens": 1500
        }
        resp = requests.post(GROQ_URL, headers={"Authorization": f"Bearer {GROQ_API_KEY}"}, json=groq_payload, timeout=25)
        if resp.ok:
            result = resp.json()
            return {
                "success": True,
                "response": result['choices'][0]['message']['content'],
                "source": "groq",
                "scriptorium_active": True,
                "genre_detected": genre
            }
            
        else:
            print(f"[!] Primary Groq failed: {resp.status_code} - {resp.text}")
            
        # Fallback to 70b
        fallback_model = MODEL_MAP["llama-3-70b"]
        print(f"[!] Primary failed. Falling back to Scriptorium Chat with {fallback_model}...")
        groq_payload["model"] = fallback_model
        resp2 = requests.post(GROQ_URL, headers={"Authorization": f"Bearer {GROQ_API_KEY}"}, json=groq_payload, timeout=20)
        if resp2.ok:
            result = resp2.json()
            return {
                "success": True,
                "response": result['choices'][0]['message']['content'],
                "source": "groq",
                "scriptorium_active": True,
                "genre_detected": genre
            }
        else:
            print(f"[!] Fallback Groq failed: {resp2.status_code} - {resp2.text}")
            
    except Exception as e:
        print(f"[!] Scriptorium Chat exception: {e}")
        
    return {"success": False, "error": "Scriptorium backend failed"}

def handle_scriptorium_trivia(mode, target, count, version, difficulty, language, book_name=None):
    """Handles enhanced trivia generation for the Scriptorium framework."""
    
    genre = detect_genre(book_name) if book_name else detect_genre(target if mode == 'book' else None)
    scalpel_data = get_scalpel_context(target) if language == 'sw' else None
    
    prompt = build_scriptorium_trivia_prompt(
        mode=mode,
        target=target,
        count=count,
        version=version,
        difficulty=difficulty,
        language=language,
        genre=genre,
        scalpel_data=scalpel_data
    )
    
    try:
        print(f"[*] Attempting Scriptorium Trivia with model {SCRIPTORIUM_DEFAULT_MODEL}...")
        groq_payload = {
            "model": MODEL_MAP[SCRIPTORIUM_DEFAULT_MODEL],
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.8,
            "max_tokens": 4096,
            "response_format": {"type": "json_object"}
        }
        
        # 120b doesn't strictly support json_object in the same way sometimes, so we ensure the prompt is very strict
        # and fallback to 70b if it fails parsing
        
        resp = requests.post(GROQ_URL, headers={"Authorization": f"Bearer {GROQ_API_KEY}"}, json=groq_payload, timeout=45)
        
        if not resp.ok:
            print(f"[!] Primary failed ({resp.status_code}): {resp.text[:200]}")
            print(f"[!] Falling back to Scriptorium Trivia with {MODEL_MAP['llama-3-70b']}...")
            groq_payload["model"] = MODEL_MAP["llama-3-70b"]
            resp = requests.post(GROQ_URL, headers={"Authorization": f"Bearer {GROQ_API_KEY}"}, json=groq_payload, timeout=45)
            
        if resp.ok:
            result = resp.json()
            content = result['choices'][0]['message']['content']
            finish_reason = result['choices'][0].get('finish_reason', 'unknown')
            print(f"[*] Scriptorium Trivia response received. Finish reason: {finish_reason}, Content length: {len(content)} chars")
            
            parsed = json.loads(content)
            
            # Extract array if wrapped in object
            if not isinstance(parsed, list):
                for v in parsed.values():
                    if isinstance(v, list):
                        parsed = v
                        break
            
            print(f"[*] Scriptorium generated {len(parsed)} questions (requested {count})")
            
            return {
                "success": True,
                "response": parsed,
                "source": "groq",
                "scriptorium_active": True
            }
            
    except Exception as e:
        print(f"[!] Scriptorium Trivia exception: {e}")
        
    return {"success": False, "error": "Scriptorium trivia generation failed"}
