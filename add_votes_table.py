import sqlite3

conn = sqlite3.connect('database.db')
c = conn.cursor()

# Create votes table
c.execute('''
    CREATE TABLE IF NOT EXISTS votes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        snippet_id INTEGER NOT NULL,
        vote_type TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (snippet_id) REFERENCES snippets (id),
        UNIQUE(user_id, snippet_id)
    )
''')

conn.commit()
conn.close() 