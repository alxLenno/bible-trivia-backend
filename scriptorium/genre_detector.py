"""
Genre Detector for the Scriptorium Framework.
Provides deterministic mapping of biblical books to their primary literary genre.
"""

# Categorization based on standard biblical scholarship
GENRE_MAP = {
    # Pentateuch / Law & Narrative
    "Genesis": "narrative",
    "Exodus": "narrative", # Mixed law/narrative, but narrative is primary frame
    "Leviticus": "law",
    "Numbers": "narrative",
    "Deuteronomy": "law",
    
    # Historical Books / Narrative
    "Joshua": "narrative",
    "Judges": "narrative",
    "Ruth": "narrative",
    "1 Samuel": "narrative",
    "2 Samuel": "narrative",
    "1 Kings": "narrative",
    "2 Kings": "narrative",
    "1 Chronicles": "narrative",
    "2 Chronicles": "narrative",
    "Ezra": "narrative",
    "Nehemiah": "narrative",
    "Esther": "narrative",
    
    # Poetry & Wisdom
    "Job": "wisdom",
    "Psalms": "poetry",
    "Proverbs": "wisdom",
    "Ecclesiastes": "wisdom",
    "Song of Solomon": "poetry",
    
    # Major Prophets
    "Isaiah": "prophecy",
    "Jeremiah": "prophecy",
    "Lamentations": "poetry", # Often grouped with prophets, but genre is poetic lament
    "Ezekiel": "prophecy",
    "Daniel": "apocalyptic", # Mixed narrative/apocalyptic, but apocalyptic is defining feature
    
    # Minor Prophets
    "Hosea": "prophecy",
    "Joel": "prophecy",
    "Amos": "prophecy",
    "Obadiah": "prophecy",
    "Jonah": "narrative", # Prophet book, but genre is narrative
    "Micah": "prophecy",
    "Nahum": "prophecy",
    "Habakkuk": "prophecy",
    "Zephaniah": "prophecy",
    "Haggai": "prophecy",
    "Zechariah": "apocalyptic",
    "Malachi": "prophecy",
    
    # Gospels & Acts / Theological Narrative
    "Matthew": "narrative",
    "Mark": "narrative",
    "Luke": "narrative",
    "John": "narrative",
    "Acts": "narrative",
    
    # Pauline Epistles
    "Romans": "epistle",
    "1 Corinthians": "epistle",
    "2 Corinthians": "epistle",
    "Galatians": "epistle",
    "Ephesians": "epistle",
    "Philippians": "epistle",
    "Colossians": "epistle",
    "1 Thessalonians": "epistle",
    "2 Thessalonians": "epistle",
    "1 Timothy": "epistle",
    "2 Timothy": "epistle",
    "Titus": "epistle",
    "Philemon": "epistle",
    
    # General Epistles
    "Hebrews": "epistle", # Often considered a sermon, but functions as an epistle
    "James": "epistle", # Wisdom literature within epistle frame
    "1 Peter": "epistle",
    "2 Peter": "epistle",
    "1 John": "epistle",
    "2 John": "epistle",
    "3 John": "epistle",
    "Jude": "epistle",
    
    # Apocalyptic
    "Revelation": "apocalyptic"
}

def detect_genre(book: str, chapter: int = None) -> str:
    """
    Returns the primary literary genre of a biblical book.
    Defaults to 'narrative' if the book is unknown.
    """
    if not book:
        return "narrative"
        
    # Handle slight variations in book names (e.g., "Song of Songs" vs "Song of Solomon")
    normalized_book = book.strip()
    if normalized_book == "Song of Songs":
        normalized_book = "Song of Solomon"
        
    genre = GENRE_MAP.get(normalized_book, "narrative")
    
    # Advanced logic: Some books have split genres by chapter
    if chapter is not None:
        if normalized_book == "Daniel":
            if 1 <= chapter <= 6:
                return "narrative"
            else:
                return "apocalyptic"
        elif normalized_book == "Exodus":
            if 20 <= chapter <= 23 or 25 <= chapter <= 31:
                return "law"
                
    return genre
