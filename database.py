# database.py
import sqlite3
import os

DATABASE_FILE = 'database.db'

def init_db():
    """
    Initializes the database by creating necessary tables and triggers
    if they don't exist. Correctly defines 'updated_at' with a default
    for new table creation.
    """
    print(f"Initializing database schema at: {os.path.abspath(DATABASE_FILE)}")
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()

    # --- Users Table ---
    # Includes fields from setup_profile form
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,               -- Store HASHED password
            profile_picture TEXT,
            bio TEXT,
            age INTEGER,
            dob TEXT,
            profession TEXT,
            profile_setup INTEGER DEFAULT 0,    -- 0 = Not setup, 1 = Setup complete
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
    # Defines updated_at column with default for initial creation
    c.execute('''
        CREATE TABLE IF NOT EXISTS snippets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            code TEXT NOT NULL,
            language TEXT NOT NULL,
            description TEXT,
            is_private INTEGER DEFAULT 0,      -- 0 = public, 1 = private
            views INTEGER DEFAULT 0,
            rating_total INTEGER DEFAULT 0,   -- Sum of all ratings
            rating_count INTEGER DEFAULT 0,   -- Number of ratings received
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Column with default
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    ''')
    print("- Snippets table schema ensured.")

    # --- Trigger to update 'updated_at' on snippet update ---
    # Ensures the trigger is created correctly
    c.execute('''
        CREATE TRIGGER IF NOT EXISTS update_snippet_updated_at
        AFTER UPDATE ON snippets
        FOR EACH ROW
        -- Only run if updated_at wasn't explicitly set in the UPDATE statement
        WHEN OLD.updated_at = NEW.updated_at OR OLD.updated_at IS NULL
        BEGIN
            -- Set updated_at to the current time for the updated row
            UPDATE snippets
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = OLD.id;
        END;
    ''')
    print("- Trigger 'update_snippet_updated_at' ensured.")

    # --- Votes Table ---
    c.execute('''
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            snippet_id INTEGER NOT NULL,
            vote_type TEXT NOT NULL CHECK(vote_type IN ('up', 'down')),
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
            parent_id INTEGER,                 -- For nested replies
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (snippet_id) REFERENCES snippets(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (parent_id) REFERENCES comments(id) ON DELETE CASCADE
        );
    ''')
    print("- Comments table schema ensured.")

    # --- Ratings Table (Optional - Commented out) ---
    # c.execute(''' CREATE TABLE IF NOT EXISTS ratings ( ... ); ''')
    # print("- Ratings table ensured.")


    conn.commit()
    conn.close()
    print("Database initialization check complete.")

def migrate_db():
    """
    Applies schema migrations, specifically handling the addition of
    'updated_at' column to avoid issues with non-constant defaults in
    older SQLite versions.
    """
    print("Checking for necessary database migrations...")
    conn = None
    schema_changed = False # Flag to track if changes were made
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        c = conn.cursor()

        # --- Migration for 'updated_at' column in 'snippets' table ---
        c.execute("PRAGMA table_info(snippets);")
        columns = [info[1] for info in c.fetchall()] # Get existing column names

        if 'updated_at' not in columns:
            print("  - Attempting to add 'updated_at' column to snippets...")
            try:
                # Step 1: Add the column WITHOUT the non-constant default
                c.execute("ALTER TABLE snippets ADD COLUMN updated_at TIMESTAMP;")
                print("    -> Added 'updated_at' column definition.")

                # Step 2: Update existing rows to have a sensible default value
                # Using created_at is a common approach for initial backfill.
                c.execute("""
                    UPDATE snippets
                    SET updated_at = created_at
                    WHERE updated_at IS NULL;
                """)
                print("    -> Populated existing NULL 'updated_at' values using 'created_at'.")

                conn.commit() # Commit these changes
                schema_changed = True
                print("  - Successfully added and populated 'updated_at' column.")

            except sqlite3.OperationalError as e:
                # If adding column fails for other reasons
                print(f"    -> ERROR adding/populating 'updated_at' column: {e}")
                conn.rollback()
        else:
             # No need to print this every time if the column exists
             # print("  - 'updated_at' column already exists in snippets table.")
             pass

        # --- Add other migration checks here if needed ---
        # Example: Check for 'full_name' column in users
        # c.execute("PRAGMA table_info(users);")
        # user_columns = [info[1] for info in c.fetchall()]
        # if 'full_name' not in user_columns:
        #     try:
        #         c.execute("ALTER TABLE users ADD COLUMN full_name TEXT;")
        #         print("  - Added 'full_name' column to users table.")
        #         conn.commit()
        #         schema_changed = True
        #     except sqlite3.OperationalError as e:
        #         print(f"    -> ERROR adding 'full_name' column: {e}")
        #         conn.rollback()
        # ... repeat for other new user columns if necessary ...


    except sqlite3.Error as e:
        # Catch potential connection or PRAGMA errors
        print(f"Migration check failed with database error: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

    if schema_changed:
        print("Database schema migrations applied successfully.")
    else:
         print("No schema migrations were needed.")
    # print("Database migration check complete.") # Can omit this less informative line

# --- Direct Execution Block ---
# This allows running `python database.py` to set up/check the database
if __name__ == '__main__':
    print("-" * 40)
    print("Running database script directly...")
    print("-" * 40)
    # init_db ensures tables and triggers are created IF THEY DON'T EXIST
    init_db()
    # migrate_db ensures columns are added IF THEY DON'T EXIST
    migrate_db()
    print("-" * 40)
    print(f"Script finished. Database '{DATABASE_FILE}' schema checked/updated.")
    print("-" * 40)