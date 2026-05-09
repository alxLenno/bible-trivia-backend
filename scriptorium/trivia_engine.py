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
    Builds an enhanced trivia prompt that APPLIES Scriptorium principles
    as thinking methods, not as question templates.
    
    The AI should internalize these rules and produce diverse, dynamic questions
    that naturally emerge from the text — not repeat the same patterns.
    """
    
    target_language = "Swahili" if language == "sw" else "English"
    
    prompt = [
        f"You are a master Biblical Scholar generating {count} advanced trivia questions.",
        f"LANGUAGE: Generate the entire JSON response strictly in {target_language}.",
        f"BIBLE VERSION: Align with {version} translation terminology.",
        ""
    ]
    
    # Context instruction based on mode
    if mode == "book":
        prompt.append(f"SCOPE: Focus EXCLUSIVELY on the book of {target}.")
    elif mode == "chapter":
        prompt.append(f"SCOPE: Focus EXCLUSIVELY on {target['book']} Chapter {target['chapter']}. Every question must be answerable from this chapter.")
    elif mode == "topic":
        prompt.append(f"SCOPE: Focus on the biblical topic of '{target}'. Cross-reference how it appears across different books.")
    else:
        prompt.append("SCOPE: Draw from across the entire Bible (Old and New Testament).")
    prompt.append("")
    
    # THE SCRIPTORIUM METHOD — Internalized principles, not a checklist
    prompt.extend([
        "HOW TO THINK (Internalize these — do NOT treat them as a list of question types):",
        "",
        "1. THE STRETCHING PRINCIPLE:",
        "   Every question's EXPLANATION must teach the player something they almost certainly did NOT know.",
        "   Do not merely confirm the correct answer. Instead, the explanation should be a mini-revelation:",
        "   a hidden linguistic root, an archaeological discovery, a surprising intertextual echo,",
        "   a sociopolitical detail from the ancient world, or a narrative technique the author deployed.",
        "   The player should finish reading the explanation and think: 'I never knew that.'",
        "",
        "2. THE SOCRATIC PRINCIPLE:",
        "   Questions must force SYNTHESIS, not RECALL. Never ask 'Who did X?' or 'Where did Y happen?'",
        "   Instead, ask questions that require the player to connect two ideas, evaluate a claim,",
        "   or identify a deeper pattern. The question should feel like a puzzle, not a memory test.",
        "   Example of BAD: 'Who built the ark?' (pure recall)",
        "   Example of GOOD: 'Which narrative detail in the flood account most closely parallels the",
        "   creation sequence in Genesis 1, suggesting the author intended a theological re-creation motif?'",
        "",
        "3. THE FATHER'S HEART PRINCIPLE:",
        "   At least ONE question out of every 5 should touch the relational dimension of God.",
        "   Not just theology about God, but questions that reveal God's character as Father (Baba),",
        "   Redeemer, Covenant-Keeper, or Comforter. The explanation for this question should connect",
        "   the academic insight to a pastoral truth about God's nature.",
        "",
        "4. THE NON-MIRRORING PRINCIPLE:",
        "   All 4 answer options must be genuinely plausible to someone with moderate Bible knowledge.",
        "   Do NOT include obviously wrong distractors. Each wrong answer should represent a real",
        "   interpretive tradition, a common misconception, or a theologically adjacent concept.",
        "   The player should genuinely struggle to choose.",
        ""
    ])
    
    # Genre-specific LENS (not question type — a way of reading)
    if genre:
        prompt.append(f"GENRE LENS: The target text is primarily {genre.upper()}.")
        prompt.append("Let this genre naturally shape HOW you read the text when crafting questions:")
        if genre == "epistle":
            prompt.append("Notice argument flow, rhetorical pivots (e.g., 'therefore'), indicative-to-imperative shifts, and the pastoral situation the author addresses.")
        elif genre in ["poetry", "wisdom"]:
            prompt.append("Notice parallelism structures, metaphorical layers, emotional register, and how imagery encodes theology.")
        elif genre == "narrative":
            prompt.append("Notice plot structure, character foils, the narrator's editorial voice, irony, and whether events are descriptive (reporting) vs prescriptive (modeling).")
        elif genre in ["prophecy", "apocalyptic"]:
            prompt.append("Notice symbolic imagery systems, the tension between forthtelling and foretelling, covenant-lawsuit patterns, and fulfillment trajectories.")
        elif genre == "law":
            prompt.append("Notice the covenantal framework, case-law vs. apodictic law, the theological rationale behind specific commands, and how NT authors reinterpret these laws.")
        prompt.append("")
    
    # Swahili Dual Scalpel
    if language == "sw" or version == "SWAB":
        prompt.append("SWAHILI BILINGUAL LENS (DUAL SCALPEL):")
        prompt.append("Since the target language is Swahili, naturally weave in questions that explore how Swahili theological vocabulary captures (or misses) nuances of the original Greek/Hebrew.")
        prompt.append("For example, how 'upendo' maps to 'agape', or the distinction between 'mtumwa' and 'mtumishi' for Greek 'doulos'.")
        if scalpel_data:
            prompt.append("Use this semantic data as inspiration:")
            prompt.append(scalpel_data)
        prompt.append("")
    
    # DIVERSITY MANDATE
    prompt.extend([
        "CRITICAL — DIVERSITY MANDATE:",
        f"You are generating {count} questions. They must NOT all follow the same pattern.",
        "Vary your approach across the questions:",
        "- Some should probe linguistic/translation nuances",
        "- Some should test structural or literary awareness",
        "- Some should explore historical-cultural background",
        "- Some should reveal intertextual or typological connections", 
        "- At least one should touch the relational/pastoral dimension (Father's Heart)",
        "Do NOT let any single approach dominate. Each question should feel fresh and surprising.",
        ""
    ])
    
    # Output format
    prompt.extend([
        "RULES FOR OPTIONS AND EXPLANATIONS:",
        "- Provide exactly 4 plausible options for each question.",
        "- The explanation MUST be 3-4 sentences that teach something NEW (Stretching Principle).",
        "- Include the scripture reference in the explanation.",
        "- The explanation should make the player feel like they just attended a mini-lecture.",
        "",
        "OUTPUT FORMAT (CRITICAL):",
        "Respond with ONLY a valid JSON array. No markdown, no commentary.",
        '[',
        '  {',
        '    "question": "...",',
        '    "options": ["A", "B", "C", "D"],',
        '    "correct": "B",',
        '    "difficulty": "scriptorium",',
        '    "explanation": "3-4 sentence mini-lesson with scripture reference..."',
        '  }',
        ']'
    ])
    
    return "\n".join(prompt)
