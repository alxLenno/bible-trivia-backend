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
    Builds an enhanced trivia prompt that incorporates Scriptorium principles.
    This replaces the frontend prompt builder when difficulty == 'scriptorium'.
    """
    
    # Base configuration
    target_language = "Swahili" if language == "sw" else "English"
    
    prompt = [
        f"You are a master Biblical Scholar and Trivia Generator for the Scriptorium Framework.",
        f"Generate {count} unique, high-quality multiple-choice trivia questions.",
        f"LANGUAGE INSTRUCTION (CRITICAL): Generate the entire JSON response strictly in {target_language}.",
        f"BIBLE VERSION: Questions should align with {version} translation terminology.",
        ""
    ]
    
    # Context instruction based on mode
    if mode == "book":
        prompt.append(f"CONTEXT: Focus EXCLUSIVELY on the book of {target}.")
    elif mode == "chapter":
        prompt.append(f"CONTEXT: Focus EXCLUSIVELY on {target['book']} Chapter {target['chapter']}. Every question must be answerable from this chapter alone.")
    elif mode == "topic":
        prompt.append(f"CONTEXT: Focus on the biblical topic of '{target}'. Cross-reference how this topic appears in different books.")
    else:
        prompt.append("CONTEXT: Draw from across the entire Bible (Old and New Testament).")
    prompt.append("")
    
    # Scriptorium Difficulty & Genre Awareness
    prompt.extend([
        "DIFFICULTY: SCRIPTORIUM TIER (Extremely High)",
        "These questions are for advanced seminary-level study.",
        "Do NOT ask simple factual recall questions (e.g., 'Who was David's father?').",
        "Instead, your questions MUST test:",
        "1. Typological connections (e.g., OT shadows fulfilled in the NT).",
        "2. Cross-canonical themes and redemptive-historical progression.",
        "3. Semantic domain analysis (Greek/Hebrew word meanings and roots).",
        "4. Historical-cultural context (e.g., ancient Near Eastern treaties, Roman law)."
    ])
    
    if genre:
        prompt.append(f"\nGENRE AWARENESS: The target text is primarily {genre.upper()}.")
        if genre == "epistle":
            prompt.append("Include questions testing the author's logical argument structure, the transition from indicative (theology) to imperative (ethics), and Greek rhetorical devices.")
        elif genre in ["poetry", "wisdom"]:
            prompt.append("Include questions testing Hebrew parallelism (synonymous, antithetical, synthetic), chiasmus, metaphor, and emotional register.")
        elif genre == "narrative":
            prompt.append("Include questions testing plot structure, the narrator's point of view, irony, and whether an event is descriptive (what happened) vs prescriptive (what should happen).")
        elif genre in ["prophecy", "apocalyptic"]:
            prompt.append("Include questions testing symbolic imagery, the distinction between forthtelling (calling to covenant faithfulness) and foretelling (future events), and prophetic fulfillment patterns.")
    
    # Swahili / Dual Scalpel specific logic
    if language == "sw" or version == "SWAB":
        prompt.append("\nSWAHILI BILINGUAL HERMENEUTICS (DUAL SCALPEL):")
        prompt.append("Since the target language is Swahili, you MUST include questions that test semantic precision unique to Swahili.")
        prompt.append("Example: Ask about the theological distinction between 'mtumwa' (slave) and 'mtumishi' (servant) for the Greek word 'doulos', or how 'upendo' captures 'agape' better than the English word 'love'.")
        if scalpel_data:
            prompt.append("Draw inspiration from this Greek-Swahili semantic data:")
            prompt.append(scalpel_data)
            
    # Output formatting and strict rules
    prompt.extend([
        "",
        "RULES FOR OPTIONS AND EXPLANATIONS:",
        "- Provide exactly 4 plausible options.",
        "- The correct answer must NOT be obvious by elimination; distractors must be strong.",
        "- The explanation MUST be a mini-lesson (2-3 sentences) explaining the theology or history behind the answer.",
        "- Include the scripture reference in the explanation.",
        "",
        "OUTPUT FORMAT (CRITICAL):",
        "Respond with ONLY a valid JSON array. Do not include markdown blocks or any other text.",
        "Example structure:",
        "[",
        "  {",
        '    "question": "The Greek term \'metanoia\' (often translated repentance) primarily indicates...",',
        '    "options": ["A feeling of deep sorrow", "A change of mind resulting in a change of direction", "A ritual cleansing", "A public confession"],',
        '    "correct": "A change of mind resulting in a change of direction",',
        '    "difficulty": "scriptorium",',
        '    "explanation": "In Greek, \'meta\' means change and \'noia\' refers to the mind. True repentance is not just emotional sorrow but a fundamental reorientation of one\'s life trajectory. (2 Corinthians 7:10)"',
        "  }",
        "]"
    ])
    
    return "\n".join(prompt)
