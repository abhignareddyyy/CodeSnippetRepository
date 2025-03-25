import sqlite3
import os

def init_db():
    """Initialize the database with required tables."""
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # Create users table with profile_picture column
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        profile_picture TEXT DEFAULT NULL  -- Added profile picture column
    )
    ''')

    # Create snippets table
    c.execute('''
    CREATE TABLE IF NOT EXISTS snippets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        code TEXT NOT NULL,
        language TEXT NOT NULL,
        description TEXT,
        is_private BOOLEAN DEFAULT 0,
        rating_total INTEGER DEFAULT 0,
        rating_count INTEGER DEFAULT 0,
        views INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')

    # Create ratings table
    c.execute('''
    CREATE TABLE IF NOT EXISTS ratings (
        snippet_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (snippet_id, user_id),
        FOREIGN KEY (snippet_id) REFERENCES snippets (id),
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')

    # Create votes table
    c.execute('''
    CREATE TABLE IF NOT EXISTS votes (
        user_id INTEGER,
        snippet_id INTEGER,
        vote_type TEXT CHECK(vote_type IN ('up', 'down')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, snippet_id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (snippet_id) REFERENCES snippets(id)
    )
    ''')

    # Create followers table
    c.execute('''
    CREATE TABLE IF NOT EXISTS followers (
        follower_id INTEGER,
        followed_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (follower_id, followed_id),
        FOREIGN KEY (follower_id) REFERENCES users(id),
        FOREIGN KEY (followed_id) REFERENCES users(id)
    )
    ''')

    # Create comments table
    c.execute('''
    CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snippet_id INTEGER,
        user_id INTEGER,
        parent_id INTEGER NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (snippet_id) REFERENCES snippets(id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (parent_id) REFERENCES comments(id)
    )
    ''')

    conn.commit()
    conn.close()
    print("Database initialized successfully.")

def reset_db():
    """Reset the database by deleting it and recreating tables."""
    if os.path.exists('database.db'):
        os.remove('database.db')
        print("Existing database removed.")
    
    init_db()
    print("Database reset complete.")

def migrate_db():
    """Add missing columns to existing tables if they don't exist."""
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Add views column to snippets if missing
    c.execute("PRAGMA table_info(snippets)")
    columns = [col[1] for col in c.fetchall()]
    if 'views' not in columns:
        c.execute('ALTER TABLE snippets ADD COLUMN views INTEGER DEFAULT 0')
        print("Added 'views' column to snippets table.")
    
    # Add profile_picture column to users if missing
    c.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in c.fetchall()]
    if 'profile_picture' not in columns:
        c.execute('ALTER TABLE users ADD COLUMN profile_picture TEXT DEFAULT NULL')
        print("Added 'profile_picture' column to users table.")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    migrate_db()