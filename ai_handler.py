import os
import json
import requests
import re
import time
import random
from scriptorium import build_scriptorium_prompt
from scriptorium.genre_detector import detect_genre
from scriptorium.dual_scalpel import get_scalpel_context
from scriptorium.trivia_engine import build_scriptorium_trivia_prompt

# ── API Keys ─────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GROQ_API_KEY   = os.environ.get("GROQ_API_KEY", "")

# ── Endpoints ─────────────────────────────────────────────────────────────────
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"

# ── Models ────────────────────────────────────────────────────────────────────
GEMINI_FLASH        = "gemini-3.5-flash-lite"
GEMINI_PRO          = "gemini-3.5-flash-lite"
GROQ_FALLBACK_CHAT  = "openai/gpt-oss-20b"
GROQ_FALLBACK_HEAVY = "openai/gpt-oss-120b"

SCRIPTORIUM_DEFAULT_MODEL = GEMINI_PRO

# ── Shared POST helper ────────────────────────────────────────────────────────
def _post(url, key, payload, timeout=40):
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()

# ── JSON parser (strips markdown fences) ─────────────────────────────────────
def _parse_json_array(content):
    content = re.sub(r'^```(?:json)?\s*', '', content.strip(), flags=re.MULTILINE)
    content = re.sub(r'\s*```$', '', content.strip(), flags=re.MULTILINE)
    parsed = json.loads(content)
    if not isinstance(parsed, list):
        for v in parsed.values():
            if isinstance(v, list):
                return v
    return parsed

# ─────────────────────────────────────────────────────────────────────────────
#  DIFFICULTY-PROGRESSIVE TRIVIA PROMPT BUILDER
# ─────────────────────────────────────────────────────────────────────────────
_QUESTION_ANGLES = [
    "Explore lesser-known minor characters and obscure scriptural details.",
    "Focus on numbers, quantities, ages, durations, and biblical measurements.",
    "Focus on the exact sequence of events and cause-and-effect chains.",
    "Focus on direct quotes: who said what, to whom, and in what context.",
    "Focus on geography: mountains, rivers, seas, cities, and named nations.",
    "Focus on genealogy, tribal lineages, and ancestral family relationships.",
    "Focus on miracles, divine judgments, and supernatural interventions.",
    "Focus on symbolic objects, visions, garments, and sacred instruments.",
    "Focus on covenants: their terms, signatories, conditions, and consequences.",
    "Focus on contrasts and parallels between Old and New Testament figures.",
]

_QUESTION_TYPES = [
    "Who (person / author / speaker / prophet)",
    "What (event / object / miracle / commandment / offering)",
    "Where (place / geography / direction / region)",
    "How many (number / count / duration / age / quantity)",
    "Why (motivation / theological reason / divine purpose)",
    "What happened next (sequence / immediate consequence)",
    "Which (distinction between similar biblical figures or places)",
    "How (method / process / divine instruction / manner)",
]

_DIFFICULTY_GUIDE = {
    "easy": (
        "EASY — Direct factual recall. Single-hop answers found explicitly in one verse.\n"
        "• Questions about well-known names, famous events, and clear facts.\n"
        "• The correct answer is stated plainly in the text with no inference needed.\n"
        "• Wrong options are clearly different — no tricky near-misses.\n"
        "• Example: 'Who built the ark?' Answer: Noah (Genesis 6:14).\n"
        "• Suitable for children and new Bible readers."
    ),
    "medium": (
        "MEDIUM — Contextual understanding. Requires knowing the surrounding narrative.\n"
        "• Questions about character relationships, motivations, and sequence.\n"
        "• The correct answer requires context — not just one verse.\n"
        "• Wrong options are plausible but distinguishable by a careful reader.\n"
        "• Example: 'What material was used to make the Ark of the Covenant?' (Acacia wood, Exodus 25:10)\n"
        "• Suitable for regular churchgoers and Sunday school teachers."
    ),
    "hard": (
        "HARD — Cross-referential, theological, and symbolic depth.\n"
        "• Involves prophecy fulfillment, typology, cross-book connections, or Greek/Hebrew nuance.\n"
        "• Draws from less-known passages — the casual reader would likely get this wrong.\n"
        "• Wrong options are highly plausible — only a serious student would get it right.\n"
        "• Example: 'What Greek word in 1 Corinthians 13 describes the love that never fails?' (agape)\n"
        "• Suitable for Bible scholars, seminary students, and serious students of the Word."
    ),
}


def _build_trivia_prompt(mode, target, count, version, difficulty, language="en"):
    seed  = int(time.time() * 1000) + random.randint(0, 9999)
    angle = random.choice(_QUESTION_ANGLES)
    types_pool = random.sample(_QUESTION_TYPES, min(count, len(_QUESTION_TYPES)))
    types_str  = "\n".join(f"  {i+1}. {t}" for i, t in enumerate(types_pool))

    lang_map = {"en": "English", "sw": "Swahili", "nl": "Dutch"}
    target_language = lang_map.get(language, "English")
    diff_block = _DIFFICULTY_GUIDE.get(difficulty, _DIFFICULTY_GUIDE["medium"])

    if mode == "book":
        scope = (
            f"Focus EXCLUSIVELY on the Book of {target} ({version}).\n"
            f"Every question must be directly answerable from {target} alone."
        )
    elif mode == "chapter" and isinstance(target, dict):
        scope = (
            f"Focus EXCLUSIVELY on {target['book']} Chapter {target['chapter']} ({version}).\n"
            "Every question must be answerable from that single chapter."
        )
    elif mode == "topic":
        scope = (
            f"Focus on the biblical theme: \"{target}\".\n"
            "Draw from both Old and New Testaments, showing how this theme develops across the canon."
        )
    else:
        scope = (
            f"Draw from the ENTIRE Bible — Old and New Testament ({version}).\n"
            "Cover diverse books: Creation, Patriarchs, Exodus, Kings, Prophets, Gospels, Epistles, Revelation."
        )

    return f"""You are an expert Bible trivia question writer with deep knowledge of Scripture.
Generate exactly {count} unique, high-quality multiple-choice trivia questions.

LANGUAGE: All output MUST be written in {target_language}.

SCOPE:
{scope}

DIFFICULTY: {difficulty.upper()}
{diff_block}

SPECIAL FOCUS FOR THIS BATCH (make most questions lean toward this angle):
{angle}

QUESTION TYPE ROTATION — use these types in order, never repeat the same type consecutively:
{types_str}

UNIQUENESS SEED (guarantees fresh, non-repetitive questions): {seed}

════════════════════════════════════════════════════════════
RULES — VIOLATING ANY OF THESE MAKES A QUESTION INVALID
════════════════════════════════════════════════════════════

1. FACTUAL ACCURACY (ABSOLUTE):
   • Every question and answer MUST be verifiable from the actual biblical text.
   • NEVER fabricate, invent, or assume details not explicitly in Scripture.
   • If uncertain about a fact, skip it and write a different question instead.
   • Every explanation MUST end with a real scripture reference in parentheses, e.g. (Genesis 3:15).

2. NO ANSWER LEAKS (CRITICAL):
   • The correct answer must NEVER appear as a word inside the question text.
   • BAD: "Who was the ancestor of the tribe of Judah?" → answer: "Judah"  ← INVALID
   • GOOD: "Which of Jacob's sons became the ancestor of Israel's royal tribe?" → answer: "Judah"
   • Rephrase any question where the answer word naturally appears in it.

3. PLAUSIBLE DISTRACTORS:
   • All 4 options must be real biblical figures, places, numbers, or concepts.
   • Wrong options should be close enough to trick someone who hasn't studied carefully.
   • NEVER use "None of the above", "All of the above", or obviously fake options.

4. QUESTION VARIETY:
   • Each question must be a different type (Who / What / Where / How many / Why / etc.).
   • NEVER ask "complete this verse" or "which verse says..."
   • Each question must stand alone — no references to previous questions.

5. EXPLANATION QUALITY:
   • 2–3 sentences explaining WHY the correct answer is right.
   • Briefly explain why the most plausible wrong option is incorrect.
   • End with the scripture reference in parentheses.

════════════════════════════════════════════════════════════
OUTPUT FORMAT — RESPOND WITH ONLY A VALID JSON ARRAY. NO MARKDOWN. NO PREAMBLE.
════════════════════════════════════════════════════════════
[
  {{
    "question": "Standalone trivia question text (answer must NOT appear here)",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correct": "The exact correct option string (must match one of the four options exactly)",
    "difficulty": "{difficulty}",
    "explanation": "2-3 sentences explaining the correct answer and why key wrong options are wrong. (Scripture reference e.g. Exodus 17:6)"
  }}
]"""


# ─────────────────────────────────────────────────────────────────────────────
#  TRIVIA GENERATION  (Gemini primary → Groq fallback)
# ─────────────────────────────────────────────────────────────────────────────
def handle_generate_trivia(prompt):
    if not prompt:
        return {"success": False, "error": "No prompt provided"}

    trivia_system = (
        "You are a Bible trivia generator. "
        "Output ONLY a valid JSON array of trivia question objects. "
        "No markdown, no explanation outside the JSON."
    )

    # 1. Gemini Flash (primary)
    if GEMINI_API_KEY:
        try:
            print(f"[*] Gemini Trivia ({GEMINI_FLASH})...")
            payload = {
                "model": GEMINI_FLASH,
                "messages": [
                    {"role": "system", "content": trivia_system},
                    {"role": "user",   "content": prompt}
                ],
                "temperature": 0.85,
                "max_tokens": 4096,
                "response_format": {"type": "json_object"}
            }
            result = _post(GEMINI_URL, GEMINI_API_KEY, payload, timeout=50)
            parsed = _parse_json_array(result["choices"][0]["message"]["content"])
            print(f"[+] Gemini generated {len(parsed)} trivia questions.")
            return {"success": True, "response": parsed, "source": "gemini"}
        except Exception as e:
            print(f"[!] Gemini Trivia failed: {e}")

    # 2. Groq fallback
    if GROQ_API_KEY:
        try:
            print(f"[*] Groq Trivia fallback ({GROQ_FALLBACK_HEAVY})...")
            payload = {
                "model": GROQ_FALLBACK_HEAVY,
                "messages": [
                    {"role": "system", "content": trivia_system},
                    {"role": "user",   "content": prompt}
                ],
                "temperature": 0.8,
                "max_tokens": 4096,
                "response_format": {"type": "json_object"}
            }
            result = _post(GROQ_URL, GROQ_API_KEY, payload, timeout=40)
            parsed = _parse_json_array(result["choices"][0]["message"]["content"])
            return {"success": True, "response": parsed, "source": "groq"}
        except Exception as e:
            print(f"[!] Groq Trivia fallback failed: {e}")

    return {"success": False, "error": "All trivia backends failed"}


# ─────────────────────────────────────────────────────────────────────────────
#  STANDARD CHAT  (Gemini primary → Groq fallback)
# ─────────────────────────────────────────────────────────────────────────────
_CHAT_SYSTEM = (
    "You are the AI Scribe — a knowledgeable biblical scholar within the Scriptorium. "
    "Help users understand sacred texts, explain biblical history, answer theological questions, "
    "and illuminate passages with accuracy, depth, and reverence. "
    "Cite specific scripture references when relevant."
)

def handle_chat(message, history=None, model_id="llama-3-8b", temperature=0.7):
    if not isinstance(history, list):
        history = []

    messages = [{"role": "system", "content": _CHAT_SYSTEM}, *history, {"role": "user", "content": message}]

    # 1. Gemini Flash (primary)
    if GEMINI_API_KEY:
        for attempt in (1, 2):
            try:
                print(f"[*] Gemini Chat ({GEMINI_FLASH}) attempt {attempt}...")
                payload = {"model": GEMINI_FLASH, "messages": messages, "temperature": temperature, "max_tokens": 2048}
                result = _post(GEMINI_URL, GEMINI_API_KEY, payload, timeout=35)
                return {"success": True, "response": result["choices"][0]["message"]["content"], "source": "gemini"}
            except Exception as e:
                print(f"[!] Gemini Chat attempt {attempt} failed: {e}")
                if attempt == 1:
                    time.sleep(1)

    # 2. Groq fallback
    if GROQ_API_KEY:
        for attempt in (1, 2):
            try:
                print(f"[*] Groq Chat fallback ({GROQ_FALLBACK_CHAT}) attempt {attempt}...")
                payload = {"model": GROQ_FALLBACK_CHAT, "messages": messages, "temperature": temperature, "max_tokens": 2048}
                result = _post(GROQ_URL, GROQ_API_KEY, payload, timeout=35)
                return {"success": True, "response": result["choices"][0]["message"]["content"], "source": "groq"}
            except Exception as e:
                print(f"[!] Groq Chat attempt {attempt} failed: {e}")
                if attempt == 1:
                    time.sleep(1)

    return {"success": False, "error": "All chat backends failed"}


# ─────────────────────────────────────────────────────────────────────────────
#  SCRIPTORIUM CHAT  (Gemini Pro → Flash → Groq)
# ─────────────────────────────────────────────────────────────────────────────
def handle_scriptorium_chat(message, history=None, context=None):
    if history is None:
        history = []

    language    = context.get("language", "en") if context else "en"
    book        = context.get("book", "") if context else ""
    chapter     = context.get("chapter", None) if context else None
    turn_count  = context.get("turn_count", len(history) // 2) if context else len(history) // 2
    passage     = context.get("passage_text", "") if context else ""

    genre        = detect_genre(book, chapter)
    scalpel_data = get_scalpel_context(message + " " + passage) if language == "sw" else None

    system_prompt = build_scriptorium_prompt(
        user_message=message, passage_context=passage, language=language,
        genre=genre, turn_count=turn_count, scalpel_data=scalpel_data
    )
    messages = [{"role": "system", "content": system_prompt}, *history, {"role": "user", "content": message}]

    for model in [GEMINI_PRO, GEMINI_FLASH]:
        if GEMINI_API_KEY:
            try:
                print(f"[*] Scriptorium Chat ({model})...")
                payload = {"model": model, "messages": messages, "temperature": 0.6, "max_tokens": 1500}
                result = _post(GEMINI_URL, GEMINI_API_KEY, payload, timeout=30)
                return {"success": True, "response": result["choices"][0]["message"]["content"],
                        "source": "gemini", "scriptorium_active": True, "genre_detected": genre}
            except Exception as e:
                print(f"[!] Scriptorium {model} failed: {e}")

    if GROQ_API_KEY:
        try:
            print(f"[*] Scriptorium Groq fallback...")
            payload = {"model": GROQ_FALLBACK_HEAVY, "messages": messages, "temperature": 0.6, "max_tokens": 1500}
            result = _post(GROQ_URL, GROQ_API_KEY, payload, timeout=25)
            return {"success": True, "response": result["choices"][0]["message"]["content"],
                    "source": "groq", "scriptorium_active": True, "genre_detected": genre}
        except Exception as e:
            print(f"[!] Scriptorium Groq fallback failed: {e}")

    return {"success": False, "error": "Scriptorium backend failed"}


# ─────────────────────────────────────────────────────────────────────────────
#  SCRIPTORIUM TRIVIA  (Gemini Pro → Groq)
# ─────────────────────────────────────────────────────────────────────────────
def handle_scriptorium_trivia(mode, target, count, version, difficulty, language, book_name=None, excluded_questions=None):
    genre        = detect_genre(book_name) if book_name else detect_genre(target if mode == "book" else None)
    scalpel_data = get_scalpel_context(target) if language == "sw" else None

    prompt = build_scriptorium_trivia_prompt(
        mode=mode, target=target, count=count, version=version,
        difficulty=difficulty, language=language, genre=genre, scalpel_data=scalpel_data
    )

    if excluded_questions:
        prompt += "\nDo not repeat or paraphrase these previous questions. Use different facts and interpretive points:\n" + json.dumps(excluded_questions[-100:], ensure_ascii=False)

    if GEMINI_API_KEY:
        try:
            print(f"[*] Scriptorium Trivia ({GEMINI_PRO})...")
            payload = {
                "model": GEMINI_PRO,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.8, "max_tokens": 4096,
                "response_format": {"type": "json_object"}
            }
            result = _post(GEMINI_URL, GEMINI_API_KEY, payload, timeout=55)
            parsed = _parse_json_array(result["choices"][0]["message"]["content"])
            print(f"[+] Scriptorium Trivia: {len(parsed)} questions.")
            return {"success": True, "response": parsed, "source": "gemini", "scriptorium_active": True}
        except Exception as e:
            print(f"[!] Scriptorium Gemini Trivia failed: {e}")

    if GROQ_API_KEY:
        try:
            print(f"[*] Scriptorium Trivia Groq fallback...")
            payload = {
                "model": GROQ_FALLBACK_HEAVY,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.8, "max_tokens": 4096,
                "response_format": {"type": "json_object"}
            }
            result = _post(GROQ_URL, GROQ_API_KEY, payload, timeout=45)
            parsed = _parse_json_array(result["choices"][0]["message"]["content"])
            return {"success": True, "response": parsed, "source": "groq", "scriptorium_active": True}
        except Exception as e:
            print(f"[!] Scriptorium Trivia Groq fallback failed: {e}")

    return {"success": False, "error": "Scriptorium trivia generation failed"}
