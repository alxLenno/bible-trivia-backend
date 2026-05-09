"""
Dual Scalpel Data for the Scriptorium Framework.
Provides semantic mapping between Greek, English, and Swahili for key theological terms.
"""
import re

# The core dictionary of semantic mappings
DUAL_SCALPEL_DATA = {
    "doulos": {
        "strongs": "G1401",
        "en": "servant / slave",
        "sw": "mtumwa (slave) vs mtumishi (servant)",
        "insight": "English often flattens this to 'servant', but Swahili forces a choice. Paul calls himself a 'mtumwa' (slave) of Christ, emphasizing total ownership, not just a 'mtumishi' (employee/servant)."
    },
    "agape": {
        "strongs": "G26",
        "en": "love",
        "sw": "upendo",
        "insight": "English 'love' covers everything from pizza to God. Swahili 'upendo' excludes romantic/transactional love natively, aligning closer to the unconditional nature of Greek agape."
    },
    "charis": {
        "strongs": "G5485",
        "en": "grace",
        "sw": "neema",
        "insight": "While 'grace' in English can mean elegance, 'neema' in Swahili carries a stronger inherent sense of provision from a superior to an inferior—capturing the 'undeserved' nature of charis."
    },
    "eirene": {
        "strongs": "G1515",
        "en": "peace",
        "sw": "amani vs salama",
        "insight": "English 'peace' often just means 'absence of conflict'. Swahili 'amani' (tranquility) and 'salama' (safety/wholeness) better capture the dual dimensions of the Hebrew 'shalom' that eirene translates."
    },
    "metanoia": {
        "strongs": "G3341",
        "en": "repentance",
        "sw": "toba",
        "insight": "English 'repentance' can sound purely emotional (feeling sorry). Swahili 'toba' carries a stronger cultural connotation of an active, physical 'turning back' or changing of direction, matching the Greek metanoia."
    },
    "koinonia": {
        "strongs": "G2842",
        "en": "fellowship",
        "sw": "ushirika",
        "insight": "English 'fellowship' often implies just socializing. Swahili 'ushirika' implies active partnership, shared assets, and deep communal bonds (jamii), reflecting the deep sharing of koinonia."
    },
    "parakletos": {
        "strongs": "G3875",
        "en": "Comforter / Advocate",
        "sw": "Msaidizi",
        "insight": "Swahili 'Msaidizi' (Helper) highlights the practical, active assistance of the Holy Spirit, whereas English 'Comforter' can sometimes feel passive."
    },
    "ekklesia": {
        "strongs": "G1577",
        "en": "church",
        "sw": "kanisa / kusanyiko",
        "insight": "English 'church' often refers to a building. The Greek 'ekklesia' means a 'called-out assembly', which is beautifully captured by the Swahili concept of a 'kusanyiko' (gathering of the people)."
    }
}

# A simple mapping of English keywords to the Greek roots to trigger the scalpel
KEYWORD_TRIGGERS = {
    "servant": "doulos",
    "slave": "doulos",
    "love": "agape",
    "grace": "charis",
    "peace": "eirene",
    "repent": "metanoia",
    "repentance": "metanoia",
    "fellowship": "koinonia",
    "comforter": "parakletos",
    "advocate": "parakletos",
    "helper": "parakletos",
    "church": "ekklesia"
}

def get_scalpel_context(text: str) -> str:
    """
    Scans the provided text (passage or user message) for English keywords.
    If a keyword matches a theological concept in our Dual Scalpel database,
    it returns a formatted string containing the Greek-English-Swahili insights
    for the prompt engine to use.
    """
    if not text:
        return ""
        
    found_roots = set()
    words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
    
    for word in words:
        if word in KEYWORD_TRIGGERS:
            found_roots.add(KEYWORD_TRIGGERS[word])
            
    if not found_roots:
        return ""
        
    context_lines = []
    for root in found_roots:
        data = DUAL_SCALPEL_DATA[root]
        context_lines.append(f"Term: {root} ({data['strongs']})")
        context_lines.append(f"  English: {data['en']}")
        context_lines.append(f"  Swahili: {data['sw']}")
        context_lines.append(f"  Hermeneutical Insight: {data['insight']}")
        context_lines.append("")
        
    return "\n".join(context_lines)
