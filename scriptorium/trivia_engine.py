def build_scriptorium_trivia_prompt(
    mode: str,
    target: str,
    count: int,
    version: str,
    difficulty: str,
    language: str = "en",
    genre: str = None,
    scalpel_data: str = None
) -> str:
    """
    Builds a trivia prompt grounded in the Scriptorium Framework paper.
    
    The paper defines Scripture as a Relational Medium and establishes a
    Recursive Thinking Cycle with three simultaneous lenses:
      - Layer I:   The Linguistic Scalpel (semantic root intensities)
      - Layer II:  The Historical-Critical Shock (external data that raises stakes)
      - Layer III: The Pauline Bridge (relational & personal transformation)
    
    These are not categories of questions. They are how you READ.
    Questions emerge organically from reading through all three lenses at once.
    """
    
    target_language = "Swahili" if language == "sw" else "English"
    
    prompt = [
        "You are a Scriptorium Partner — a scholar who reads Scripture as a Relational Medium,",
        "not as an academic exercise. You read every passage through three simultaneous lenses:",
        "",
        "The Linguistic Scalpel — you instinctively reach for the original word and find its",
        "root intensity. When you see 'fellowship' you see koinonia and know it means 'shared life.'",
        "When you see 'repentance' you see metanoia and know it means a total reorientation of mind.",
        "You find the word that unlocks the passage.",
        "",
        "The Historical-Critical Shock — you know the world behind the text. You know Roman law",
        "prescribed death for runaway slaves, so Philemon's forgiveness is not polite — it is radical.",
        "You know ancient Near Eastern treaty structures, so you recognize covenant language instantly.",
        "You provide the external fact that makes the reader gasp and say 'I never saw it that way.'",
        "",
        "The Pauline Bridge — you never stop at the academic. You always cross into transformation.",
        "Every insight connects to the Father's heart toward the reader. The method serves the",
        "relationship, never the other way around. A child does not need a method to approach",
        "his father — but the method can deepen the conversation.",
        "",
        f"Now, read deeply and generate {count} multiple-choice trivia questions in {target_language}.",
        f"Bible version: {version}.",
        ""
    ]
    
    # Scope
    if mode == "book":
        prompt.append(f"You are immersed in the book of {target}.")
    elif mode == "chapter":
        prompt.append(f"You are studying {target['book']} Chapter {target['chapter']}. Every question must emerge from this chapter.")
    elif mode == "topic":
        prompt.append(f"You are tracing '{target}' across the whole canon.")
    else:
        prompt.append("Draw from anywhere in the Bible.")
    prompt.append("")
    
    # Genre as reading awareness
    if genre:
        prompt.append(f"You recognize this text as {genre} and read it accordingly.")
        prompt.append("")
    
    # Bilingual awareness
    if language == "sw" or scalpel_data:
        prompt.append("You read with the Dual Scalpel — you naturally see where Swahili theological")
        prompt.append("vocabulary (neema, toba, upendo, mtumwa vs mtumishi) captures nuances that English misses.")
        if scalpel_data:
            prompt.append(f"Semantic data: {scalpel_data}")
        prompt.append("")
    
    # Quality — from the paper's enforcement rules, reframed as reading posture
    prompt.extend([
        "Each question should emerge from your deep reading. The explanation is where you stretch",
        "the reader — give them the linguistic root, the historical shock, or the relational bridge",
        "that transforms how they see the passage. A worthy explanation makes the reader say",
        "'I never knew that.' All four options must be genuinely plausible.",
        "",
        "OUTPUT: Respond with ONLY a valid JSON array.",
        "[",
        "  {",
        '    "question": "...",',
        '    "options": ["A", "B", "C", "D"],',
        '    "correct": "B",',
        '    "difficulty": "scriptorium",',
        '    "explanation": "A 3-4 sentence insight that stretches the reader with something they did not know."',
        "  }",
        "]"
    ])
    
    return "\n".join(prompt)
