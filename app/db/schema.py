SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS usage_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        feature TEXT NOT NULL,
        model TEXT,
        characters INTEGER,
        tokens INTEGER,
        voice_id TEXT,
        cost_estimate REAL,
        status TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS voices (
        voice_id TEXT PRIMARY KEY,
        type TEXT NOT NULL,
        name TEXT,
        note TEXT,
        sample_path TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        source_text TEXT,
        annotated_text TEXT,
        updated_at TEXT NOT NULL
    )
    """,
]
