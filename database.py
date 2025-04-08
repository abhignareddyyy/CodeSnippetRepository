# database.py
import sqlite3
import os

DATABASE_FILE = 'database.db'

def init_db():
    """
    Initializes the database by creating necessary tables and triggers
    if they don't exist. Includes 'favorites' (for own snippets)
    and 'bookmarks' (for any public snippet) tables.
    """
    print(f"Initializing database schema at: {os.path.abspath(DATABASE_FILE)}")
    conn = None # Initialize conn
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        c = conn.cursor()

        # --- Users Table ---
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                profile_picture TEXT,
                bio TEXT,
                age INTEGER,
                dob TEXT,
                profession TEXT,
                profile_setup INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                full_name TEXT,
                status TEXT,
                experience REAL,
                education TEXT,
                skills TEXT,
                country TEXT,
                website TEXT
            );
        ''')
        print("- Users table schema ensured.")

        # --- Snippets Table ---
        c.execute('''
            CREATE TABLE IF NOT EXISTS snippets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                code TEXT NOT NULL,
                language TEXT NOT NULL,
                description TEXT,
                is_private INTEGER DEFAULT 0,
                views INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        ''')
        print("- Snippets table schema ensured.")

        # --- Trigger: Update snippet 'updated_at' ---
        c.execute('''
            CREATE TRIGGER IF NOT EXISTS update_snippet_updated_at
            AFTER UPDATE ON snippets
            FOR EACH ROW
            WHEN OLD.updated_at = NEW.updated_at OR NEW.updated_at IS NULL -- Check NEW too
            BEGIN
                UPDATE snippets SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
            END;
        ''')
        print("- Trigger 'update_snippet_updated_at' ensured.")

        # --- Votes Table ---
        c.execute('''
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                snippet_id INTEGER NOT NULL,
                vote_type INTEGER NOT NULL CHECK(vote_type IN (1, -1)), -- 1=up, -1=down
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (snippet_id) REFERENCES snippets(id) ON DELETE CASCADE,
                UNIQUE(user_id, snippet_id)
            );
        ''')
        print("- Votes table schema ensured.")

        # --- Followers Table ---
        c.execute('''
            CREATE TABLE IF NOT EXISTS followers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                follower_id INTEGER NOT NULL,
                followed_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (follower_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (followed_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(follower_id, followed_id)
            );
        ''')
        print("- Followers table schema ensured.")

        # --- Comments Table ---
        c.execute('''
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snippet_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                parent_id INTEGER,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (snippet_id) REFERENCES snippets(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (parent_id) REFERENCES comments(id) ON DELETE CASCADE
            );
        ''')
        print("- Comments table schema ensured.")

        # --- Favorites Table (For User's Own Snippets) ---
        c.execute('''
            CREATE TABLE IF NOT EXISTS favorites (
                user_id INTEGER NOT NULL,
                snippet_id INTEGER NOT NULL,
                favorited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (snippet_id) REFERENCES snippets(id) ON DELETE CASCADE,
                PRIMARY KEY (user_id, snippet_id)
            );
        ''')
        print("- Favorites table schema ensured.")

        # --- *** Bookmarks Table (For Any Public Snippet) *** ---
        c.execute('''
            CREATE TABLE IF NOT EXISTS bookmarks (
                user_id INTEGER NOT NULL,
                snippet_id INTEGER NOT NULL,
                bookmarked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (snippet_id) REFERENCES snippets(id) ON DELETE CASCADE,
                PRIMARY KEY (user_id, snippet_id)
            );
        ''')
        print("- Bookmarks table schema ensured.")
        # --- *** END NEW TABLE *** ---

        conn.commit()

    except sqlite3.Error as e:
         print(f"ERROR during DB initialization: {e}")
         # Depending on severity, maybe raise the error
         # raise
    finally:
        if conn:
            conn.close()
            print("Database connection closed after init.")

    print("Database initialization check complete.")


def migrate_db():
    """
    Applies schema migrations if needed, adding missing columns like
    'updated_at' to snippets and 'join_date' to users.
    """
    print("Checking for necessary database migrations...")
    conn = None
    schema_changed = False # Flag to track if changes were made
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        c = conn.cursor()

        # === Migration for 'updated_at' in 'snippets' ===
        c.execute("PRAGMA table_info(snippets);")
        snippets_columns = [info[1] for info in c.fetchall()]
        if 'updated_at' not in snippets_columns:
            print("  - Migrating: Adding 'updated_at' to snippets...")
            try:
                c.execute("ALTER TABLE snippets ADD COLUMN updated_at TIMESTAMP;")
                c.execute("UPDATE snippets SET updated_at = created_at WHERE updated_at IS NULL;")
                conn.commit() # Commit this specific migration
                schema_changed = True
                print("  - Migration complete: 'updated_at' added.")
            except sqlite3.OperationalError as e:
                print(f"    -> ERROR migrating 'updated_at': {e}")
                conn.rollback() # Rollback this specific migration attempt


        # === Migration for 'join_date' in 'users' ===
        c.execute("PRAGMA table_info(users);")
        user_columns = [info[1] for info in c.fetchall()]
        if 'join_date' not in user_columns:
            print("  - Migrating: Adding 'join_date' to users...")
            try:
                c.execute("ALTER TABLE users ADD COLUMN join_date TIMESTAMP;")
                c.execute("UPDATE users SET join_date = created_at WHERE join_date IS NULL;")
                conn.commit() # Commit this specific migration
                schema_changed = True
                print("  - Migration complete: 'join_date' added.")
            except sqlite3.OperationalError as e:
                print(f"    -> ERROR migrating 'join_date': {e}")
                conn.rollback() # Rollback this specific migration attempt

        # --- Add other future migration checks here ---
        # Example: Adding a hypothetical 'tags' column to snippets
        # c.execute("PRAGMA table_info(snippets);")
        # snippets_columns = [info[1] for info in c.fetchall()] # Re-fetch if needed
        # if 'tags' not in snippets_columns:
        #     print("  - Migrating: Adding 'tags' to snippets...")
        #     try:
        #          c.execute("ALTER TABLE snippets ADD COLUMN tags TEXT;")
        #          # No default update needed unless required
        #          conn.commit()
        #          schema_changed = True
        #          print("  - Migration complete: 'tags' added.")
        #     except sqlite3.OperationalError as e:
        #          print(f"    -> ERROR migrating 'tags': {e}")
        #          conn.rollback()

    except sqlite3.Error as e:
        print(f"Migration check failed with database error: {e}")
        # Rollback might not be needed here if commits are per-migration
        # if conn: conn.rollback()
    finally:
        if conn:
             conn.close()
             print("Database connection closed after migration check.")


    if schema_changed:
        print("One or more database schema migrations were applied.")
    else:
         print("No necessary schema migrations were detected.")


# --- Direct Execution Block ---
if __name__ == '__main__':
    print("-" * 40)
    print(f"Running database script for: {DATABASE_FILE}")
    print("-" * 40)
    # Ensure tables exist (idempotent)
    init_db()
    # Apply pending migrations (idempotent)
    migrate_db()
    print("-" * 40)
    print("Database schema checks complete.")
    print("-" * 40)