import sqlite3
import os
from faker import Faker
from werkzeug.security import generate_password_hash
from datetime import datetime
import random

# --- Configuration ---
DATABASE_FILE = 'database.db'
NUM_FAKE_USERS = 10  # Create exactly 10 users
SNIPPETS_PER_USER = 5 # How many snippets for each user?
DEFAULT_PASSWORD = "12121212" # Use the specified password

# --- Initialization ---
fake = Faker()

# --- Data Definitions ---
# (Keep LANGUAGES, CODE_EXAMPLES, POSSIBLE_SKILLS as they were)
LANGUAGES = ['Python', 'JavaScript', 'HTML', 'CSS', 'SQL', 'Java', 'Bash', 'Markdown', 'JSON', 'Go', 'Ruby', 'PHP', 'C++']
CODE_EXAMPLES = {
    'Python': 'def greet(name):\n    print(f"Hello, {name}!")\ngreet("Pythonista")',
    'JavaScript': 'function add(a, b) {\n  return a + b;\n}\nconsole.log(add(5, 3));',
    'HTML': '<!DOCTYPE html>\n<html><body>\n<h1>My First Heading</h1>\n<p>My first paragraph.</p>\n</body></html>',
    'CSS': 'body {\n  background-color: lightblue;\n}\nh1 {\n  color: white;\n  text-align: center;\n}',
    'SQL': 'SELECT column1, column2 FROM my_table WHERE condition;',
    'Markdown': '# Heading\n\nThis is **bold** and this is *italic*. \n\n```python\nprint("code block")\n```',
    'Java': "public class HelloWorld { public static void main(String[] args) { System.out.println(\"Hello, Java!\"); } }",
    'Bash': "echo \"Processing file $1...\"\ndate",
    'JSON': '{ "id": 1, "name": "A Thing", "enabled": true, "tags": ["tag1", "tag2"] }',
    'Go': "package main\nimport \"fmt\"\nfunc main() { fmt.Println(\"Hello, Go!\") }",
    'Ruby': "class Greeter\n  def initialize(name)\n    @name = name\n  end\n  def say_hello\n    puts \"Hello, #{@name}!\"\n  end\nend\ng = Greeter.new(\"Ruby User\")\ng.say_hello",
    'PHP': "<?php\n$txt = \"PHP\";\necho \"I love $txt!\";\n?>",
    'C++': "#include <iostream>\n\nint main() {\n  std::cout << \"Hello World!\";\n  return 0;\n}"
}
POSSIBLE_SKILLS = ['Python', 'JavaScript', 'HTML', 'CSS', 'Flask', 'React', 'SQL', 'Docker', 'Git', 'Java', 'C++', 'Go', 'API Design', 'Testing', 'DevOps', 'Cloud', 'Node.js', 'Security', 'Project Management', 'UI/UX']


# --- Function to Create ONE Fake User (Now takes user_number) ---
def create_fake_user_data(user_number):
    """Generates a dictionary containing fake data for a specific user number."""
    print(f"   Generating data for user{user_number}...")

    # *** CHANGED: Generate sequential username ***
    username = f"user{user_number}"
    # *** Use standard email, as username isn't from faker anymore ***
    email = f"{username}@{fake.domain_name()}" # Or use fake.unique.email() if you prefer fully random
    # *** Use the NEW DEFAULT_PASSWORD ***
    hashed_password = generate_password_hash(DEFAULT_PASSWORD)

    # --- Keep generating other details with Faker for realism ---
    bio = fake.paragraph(nb_sentences=random.randint(2, 4))
    profession = fake.job()
    country = fake.country()
    website = fake.url()
    num_skills = random.randint(3, 7)
    skills = ','.join(random.sample(POSSIBLE_SKILLS, k=num_skills))
    dob_object = fake.date_of_birth(minimum_age=18, maximum_age=70)
    dob_string = dob_object.strftime('%Y-%m-%d')
    age = (datetime.now().date() - dob_object).days // 365
    experience = round(random.uniform(0.5, 20.0), 1)
    education = random.choice([ f"{fake.bs().split(' ')[0].capitalize()} University", f"Online Certification in {random.choice(POSSIBLE_SKILLS)}", "Self-taught Developer", f"{fake.company()} Tech Institute" ])
    status = random.choice([ "Open to collaboration", "Actively seeking new opportunities", "Learning new things", "Building cool projects", "Available for freelance", "" ])
    full_name = fake.name() # Still give them a fake "real" name
    join_date = fake.date_time_between(start_date="-2y", end_date="now")

    return {
        "username": username, "email": email, "password": hashed_password,
        "profile_picture": None, "bio": bio, "age": age, "dob": dob_string,
        "profession": profession, "profile_setup": 1, # Mark as setup
        "join_date": join_date, "full_name": full_name, "status": status,
        "experience": experience, "education": education, "skills": skills,
        "country": country, "website": website,
    }

# --- Function to Create ONE Fake Snippet (Unchanged) ---
def create_fake_snippet_data(user_id):
    """Generates a dictionary of fake snippet data linked to a user ID."""
    print(f"      Generating snippet data for user {user_id}...")
    language = random.choice(LANGUAGES)
    title = fake.sentence(nb_words=random.randint(3, 7))[:-1]
    code = CODE_EXAMPLES.get(language, f"-- Code example for {language}\nPRINT 'Hello World'")
    description = fake.paragraph(nb_sentences=random.randint(1, 3))
    is_private = 1 if random.random() < 0.2 else 0
    views = random.randint(0, 5000)
    created_at = fake.date_time_between(start_date="-1y", end_date="now")

    return {
        "user_id": user_id, "title": title, "code": code, "language": language,
        "description": description, "is_private": is_private, "views": views,
        "created_at": created_at
    }

# --- Main Function: Does the Actual Work ---
def main():
    """Connects to DB and inserts fake users and their snippets."""
    if not os.path.exists(DATABASE_FILE):
        print(f"Error: Database file '{DATABASE_FILE}' not found.")
        return

    conn = None
    total_users_inserted = 0
    total_snippets_inserted = 0
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        print(f"Connected to database: {DATABASE_FILE}")
        # *** Updated message for clarity ***
        print(f"Attempting to insert {NUM_FAKE_USERS} users (user1-user{NUM_FAKE_USERS}), each with {SNIPPETS_PER_USER} snippets...")

        # --- USER CREATION LOOP (Iterate 1 to NUM_FAKE_USERS) ---
        for i in range(1, NUM_FAKE_USERS + 1): # Start from 1, go up to 10
            user_number = i
            user_data = create_fake_user_data(user_number) # Pass user number
            user_id = None

            # Prepare user SQL statement (columns must match your users table schema)
            user_sql = '''
                INSERT INTO users (
                    username, email, password, profile_picture, bio, age, dob,
                    profession, profile_setup, join_date, full_name, status,
                    experience, education, skills, country, website
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            '''
            # Prepare user data tuple (ensure order matches user_sql)
            user_data_tuple = (
                user_data["username"], user_data["email"], user_data["password"],
                user_data["profile_picture"], user_data["bio"], user_data["age"],
                user_data["dob"], user_data["profession"], user_data["profile_setup"],
                user_data["join_date"], user_data["full_name"], user_data["status"],
                user_data["experience"], user_data["education"], user_data["skills"],
                user_data["country"], user_data["website"]
            )

            try:
                cursor.execute(user_sql, user_data_tuple)
                user_id = cursor.lastrowid # Get the ID of the inserted user
                total_users_inserted += 1
                print(f"\n({i}/{NUM_FAKE_USERS}) Inserted user: {user_data['username']} (ID: {user_id})")

                # --- SNIPPET CREATION LOOP (Only if user was inserted) ---
                if user_id:
                    user_snippets_inserted = 0
                    for j in range(SNIPPETS_PER_USER):
                        snippet_data = create_fake_snippet_data(user_id)
                        # (Snippet SQL and tuple preparation remains the same)
                        snippet_sql = '''
                            INSERT INTO snippets (
                                user_id, title, code, language, description,
                                is_private, views, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        '''
                        snippet_data_tuple = (
                            snippet_data["user_id"], snippet_data["title"],
                            snippet_data["code"], snippet_data["language"],
                            snippet_data["description"], snippet_data["is_private"],
                            snippet_data["views"], snippet_data["created_at"]
                        )
                        try:
                            cursor.execute(snippet_sql, snippet_data_tuple)
                            user_snippets_inserted += 1
                        except sqlite3.Error as snippet_e:
                            print(f"    - Failed to insert snippet {j+1} for user {user_data['username']}. Error: {snippet_e}")

                    print(f"    - Inserted {user_snippets_inserted}/{SNIPPETS_PER_USER} snippets for user {user_data['username']}.")
                    total_snippets_inserted += user_snippets_inserted
                # --- END SNIPPET LOOP ---

            except sqlite3.IntegrityError as user_e:
                # This might happen if you run the script twice without deleting db
                print(f"\n({i}/{NUM_FAKE_USERS}) Skipping user {user_data['username']}. Integrity Error (Likely already exists): {user_e}")
            except sqlite3.Error as user_e:
                print(f"\n({i}/{NUM_FAKE_USERS}) Failed to insert user {user_data['username']}. Error: {user_e}")

        # Commit all changes at the end
        conn.commit()
        print("-" * 40)
        print(f"Script finished.")
        print(f"Total users inserted: {total_users_inserted}")
        print(f"Total snippets inserted: {total_snippets_inserted}")
        print("-" * 40)

    except sqlite3.Error as e:
        print(f"\nDatabase error during operation: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

# --- Run the main function ---
if __name__ == "__main__":
    main()