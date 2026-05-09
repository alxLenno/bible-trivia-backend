"""
Scriptorium Framework — AI-Powered Hermeneutical Partner
========================================================

A modular plugin package that transforms a generic AI chatbot into a
Socratic "Scriptorium Partner" for biblical study.

Architecture:
    prompt_engine   — System prompt builder (Enforcement Rules)
    genre_detector  — Biblical genre classification
    dual_scalpel    — Greek-English-Swahili semantic mapping
    trivia_engine   — Scriptorium-enhanced trivia generation
    canonical_lens  — Typological connections (future)

Usage:
    from scriptorium import build_scriptorium_prompt
    from scriptorium.genre_detector import detect_genre
    from scriptorium.dual_scalpel import get_scalpel_context
"""

from .prompt_engine import build_scriptorium_prompt

__version__ = "0.1.0"
__all__ = ["build_scriptorium_prompt"]
