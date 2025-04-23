import sqlite3
import os
import re
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory, g
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, Email

# Assuming database.py contains these functions
from database import init_db, migrate_db

# Database configuration
DATABASE = 'database.db'

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'mykey1234') # Use environment variable or default

# --- Database Helper Functions ---

def parse_db_date(date_str):
    """
    Safely parses a date string typically stored in SQLite (YYYY-MM-DD HH:MM:SS)
    into a Python datetime object. Returns None if parsing fails or input is None/empty.
    """
    if not date_str:
        return None
    try:
        # --- VERY IMPORTANT ---
        # Adjust the format string '%Y-%m-%d %H:%M:%S' if your database
        # stores dates/times in a different format!
        # ----------------------
        return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError) as e:
        try:
            app.logger.warning(f"Could not parse date string '{date_str}': {e}")
        except RuntimeError: # Handle cases outside app context if necessary
            print(f"Warning: Could not parse date string '{date_str}': {e}")
        return None # Return None if parsing fails

def get_db():
    """Opens a new database connection if there is none yet for the current context."""
    db = getattr(g, '_database', None)
    if db is None:
        db_path = os.path.join(app.root_path, DATABASE) # Construct path safely
        try:
             db = g._database = sqlite3.connect(db_path)
             db.row_factory = sqlite3.Row # Use Row factory
             # db.execute("PRAGMA foreign_keys = ON;") # Optional: Enable FK support
        except sqlite3.Error as e:
            app.logger.error(f"Database connection error: {e}") # Use app logger
            raise # Reraise the error
    return db

@app.teardown_appcontext
def close_connection(exception):
    """Closes the database again at the end of the request."""
    db = getattr(g, '_database', None)
    if db is not None:
        try:
            db.close()
        except sqlite3.Error as e:
             app.logger.error(f"Error closing database connection: {e}") # Use app logger

def get_current_user_id():
    """Helper to safely get user ID from session."""
    return session.get('user_id')

# --- File Upload Helper ---
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2MB limit

# Ensure the upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Initialize and migrate database (call these once at startup)
# It's often better to do this via a separate script or CLI command
# but keeping it here based on the original structure.
with app.app_context():
    init_db()
    migrate_db()

# --- Forms ---
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    submit = SubmitField('Sign in')

# --- API Routes ---
@app.route('/api/user/<username>/contributions')
def get_user_contributions(username):
    conn = get_db() # Use helper
    user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()

    if not user:
        return jsonify({"success": False, "error": "User not found"}), 404

    user_id = user['id'] # Access by key

    one_year_ago = datetime.now() - timedelta(days=365)
    one_year_ago_str = one_year_ago.strftime('%Y-%m-%d %H:%M:%S')

    try:
        contributions = conn.execute('''
            SELECT strftime('%Y-%m-%d', created_at) as date, COUNT(id) as count
            FROM snippets
            WHERE user_id = ? AND is_private = 0 AND created_at >= ?
            GROUP BY date
            ORDER BY date ASC
        ''', (user_id, one_year_ago_str)).fetchall()

        contribution_data = {row['date']: row['count'] for row in contributions} # Access by key
        return jsonify({"success": True, "contributions": contribution_data})

    except sqlite3.Error as e:
        app.logger.error(f"DB Error getting contributions for {username}: {e}")
        return jsonify({"success": False, "error": "Database error"}), 500

@app.route('/api/comments', methods=['POST'])
def create_comment():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'Please login to comment'}), 401

    data = request.json
    content = data.get('content')
    snippet_id = data.get('snippet_id')
    parent_id = data.get('parent_id') # Can be None

    if not content or not snippet_id:
        return jsonify({'success': False, 'error': 'Content and snippet ID are required'}), 400

    conn = get_db()
    try:
        # Check snippet exists
        snippet = conn.execute('SELECT id FROM snippets WHERE id = ?', (snippet_id,)).fetchone()
        if not snippet:
            return jsonify({'success': False, 'error': 'Snippet not found'}), 404

        # Check parent comment exists if provided
        if parent_id:
            parent = conn.execute('SELECT id FROM comments WHERE id = ?', (parent_id,)).fetchone()
            if not parent:
                return jsonify({'success': False, 'error': 'Parent comment not found'}), 404

        conn.execute('''
            INSERT INTO comments (snippet_id, user_id, parent_id, content)
            VALUES (?, ?, ?, ?)
        ''', (snippet_id, user_id, parent_id, content))
        conn.commit()
        return jsonify({'success': True, 'message': 'Comment posted successfully'})

    except sqlite3.Error as e:
        conn.rollback()
        app.logger.error(f"Database error creating comment on snippet {snippet_id} by user {user_id}: {e}")
        return jsonify({'success': False, 'error': 'Database error occurred'}), 500

# --- Web Routes ---

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('profile'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        # Basic server-side validation (consider WTForms for robustness)
        if not username or len(username) < 3:
            msg = "Username must be at least 3 characters long"
            if is_ajax: return jsonify({"success": False, "message": msg}), 400
            flash(msg, 'error'); return render_template('register.html')
        if not email or '@' not in email:
            msg = "Please enter a valid email address"
            if is_ajax: return jsonify({"success": False, "message": msg}), 400
            flash(msg, 'error'); return render_template('register.html')
        if not password or len(password) < 8:
            msg = "Password must be at least 8 characters long"
            if is_ajax: return jsonify({"success": False, "message": msg}), 400
            flash(msg, 'error'); return render_template('register.html')

        conn = get_db()
        try:
            existing_user = conn.execute(
                'SELECT id FROM users WHERE username = ? OR email = ?',
                (username, email)
            ).fetchone()

            if existing_user:
                msg = "Username or email already exists!"
                if is_ajax: return jsonify({"success": False, "message": msg}), 409 # Conflict
                flash(msg, 'error'); return render_template('register.html')

            conn.execute(
                'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                (username, email, generate_password_hash(password))
            )
            conn.commit()

            msg = "Registration successful!"
            redirect_url = url_for('login')
            if is_ajax:
                return jsonify({"success": True, "message": msg, "redirect": redirect_url})
            flash(f'{msg} Please login.', 'success')
            return redirect(redirect_url)

        except sqlite3.Error as e:
            conn.rollback()
            app.logger.error(f"Database error during registration for {username}: {e}")
            msg = "Database error occurred. Please try again."
            if is_ajax: return jsonify({"success": False, "message": msg}), 500
            flash(msg, 'error'); return render_template('register.html')
        except Exception as e:
            # Catch other potential errors
            app.logger.error(f"Unexpected error during registration: {e}", exc_info=True)
            msg = "An unexpected error occurred. Please try again."
            if is_ajax: return jsonify({"success": False, "message": msg}), 500
            flash(msg, 'error'); return render_template('register.html')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if form.validate_on_submit(): # Handles POST and validation
        username = form.username.data
        password = form.password.data
        conn = get_db()
        try:
            user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

            if user and check_password_hash(user['password'], password): # Access by key
                session['user_id'] = user['id']
                session['username'] = user['username']
                redirect_url = url_for('profile')
                if is_ajax:
                    return jsonify({'success': True, 'message': 'Logged in successfully!', 'redirect': redirect_url})
                flash('Logged in successfully!', 'success')
                return redirect(redirect_url)
            else:
                msg = 'Invalid username or password!'
                if is_ajax:
                    return jsonify({'success': False, 'message': msg}), 401 # Unauthorized
                flash(msg, 'error')
        except sqlite3.Error as e:
             app.logger.error(f"Database error during login for {username}: {e}")
             msg = 'Database error during login.'
             if is_ajax: return jsonify({'success': False, 'message': msg}), 500
             flash(msg, 'error')

    # Handle AJAX validation errors if form.validate_on_submit() was False on POST
    if is_ajax and request.method == 'POST' and form.errors:
        errors = {field.name: field.errors for field in form if field.errors}
        return jsonify({'success': False, 'message': 'Validation failed', 'errors': errors}), 400

    # Render form for GET or failed POST (non-AJAX)
    return render_template('login.html', form=form)


# --- Consolidated Profile Route ---
# --- Consolidated Profile Route ---
# --- Consolidated Profile Route ---
# --- Consolidated Profile Route (Modified for Debugging Step 2) ---
# --- Consolidated Profile Route (Restored render_template, keeping raise e for debug) ---
@app.route('/profile')          # Route for viewing own profile
@app.route('/user/<username>')  # Route for viewing someone else's profile
def profile(username=None):
    viewer_user_id = get_current_user_id()
    profile_user_id = None
    is_own_profile = False
    user_data_row = None # Use Row object for data access

    # --- Start Debug Print ---
    # print(f"\n===== DEBUG: Entering profile function =====")
    # print(f"DEBUG: Request Path: {request.path}")
    # print(f"DEBUG: Username parameter: {username}")
    # print(f"DEBUG: Viewer User ID from session: {viewer_user_id}")
    # --- End Debug Print ---

    conn = get_db()

    try:
        # --- Start Debug Print ---
        # print("DEBUG: Inside TRY block")
        # --- End Debug Print ---

        # --- 1. Identify profile owner & fetch basic data (using Row factory) ---
        if username:
            # --- Start Debug Print ---
            # print(f"DEBUG: Condition 'if username:' is TRUE (username='{username}')")
            # --- End Debug Print ---
            user_data_row = conn.execute('''
                SELECT id, username, email, join_date, bio, profile_picture, profile_setup,
                       full_name, status, experience, education, skills, country, website, age, dob, profession
                FROM users WHERE username = ?
            ''', (username,)).fetchone()

            if not user_data_row:
                flash(f'User "{username}" not found.', 'error')
                # --- Start Debug Print ---
                # print(f"DEBUG: User '{username}' not found, redirecting to explore.")
                # --- End Debug Print ---
                return redirect(url_for('explore')) # Redirect if user not found

            profile_user_id = user_data_row['id']
            is_own_profile = (viewer_user_id == profile_user_id)
            # --- Start Debug Print ---
            # print(f"DEBUG: Fetched user_data_row for username: '{username}'. ID: {profile_user_id}. Is Own Profile? {is_own_profile}")
            # --- End Debug Print ---

        else: # Viewing own profile (username is None)
            # --- Start Debug Print ---
            # print(f"DEBUG: Condition 'if username:' is FALSE (username is None)")
            # --- End Debug Print ---
            if not viewer_user_id:
                flash('Please login to view your profile.', 'warning')
                 # --- Start Debug Print ---
                # print(f"DEBUG: No viewer_user_id, redirecting to login.")
                 # --- End Debug Print ---
                return redirect(url_for('login')) # Redirect if not logged in

            profile_user_id = viewer_user_id
            is_own_profile = True
            user_data_row = conn.execute('''
                 SELECT id, username, email, join_date, bio, profile_picture, profile_setup,
                        full_name, status, experience, education, skills, country, website, age, dob, profession
                 FROM users WHERE id = ?
             ''', (profile_user_id,)).fetchone()

            if not user_data_row:
                 flash('Error retrieving own profile data. Logged out.', 'error')
                 session.clear()
                 # --- Start Debug Print ---
                 # print(f"DEBUG: Could not retrieve own user data (ID: {profile_user_id}), clearing session and redirecting to login.")
                 # --- End Debug Print ---
                 return redirect(url_for('login')) # Redirect if own data fetch fails
            # --- Start Debug Print ---
            # print(f"DEBUG: Fetched user_data_row for own profile. ID: {profile_user_id}. Is Own Profile? {is_own_profile}")
            # --- End Debug Print ---

        # --- Start Debug Print ---
        # print(f"DEBUG: Proceeding with profile_user_id = {profile_user_id}")
        # --- End Debug Print ---

        # --- Parse Join Date ---
        join_date_obj = parse_db_date(user_data_row['join_date'])
        # --- Start Debug Print ---
        # print(f"DEBUG: Parsed join_date_obj: {join_date_obj}")
        # --- End Debug Print ---

        # --- Fetch Common Data ---
        followers_count = conn.execute('SELECT COUNT(*) FROM followers WHERE followed_id = ?', (profile_user_id,)).fetchone()[0]
        following_count = conn.execute('SELECT COUNT(*) FROM followers WHERE follower_id = ?', (profile_user_id,)).fetchone()[0]
        is_following = False
        if viewer_user_id and not is_own_profile:
            follow_check = conn.execute('SELECT 1 FROM followers WHERE follower_id = ? AND followed_id = ?', (viewer_user_id, profile_user_id)).fetchone()
            is_following = bool(follow_check)
        # --- Start Debug Print ---
        # print(f"DEBUG: Fetched common stats. Followers: {followers_count}, Following: {following_count}, Is Viewer Following?: {is_following}")
        # --- End Debug Print ---

        # --- Fetch Snippets ---
        sql_snippets = 'SELECT id, title, language, created_at, code, is_private, views FROM snippets WHERE user_id = ?'
        params_snippets = [profile_user_id]
        if not is_own_profile:
            sql_snippets += ' AND is_private = 0'
        sql_snippets += ' ORDER BY created_at DESC'
        snippets_rows = conn.execute(sql_snippets, params_snippets).fetchall()
        snippet_count = len(snippets_rows)
        # --- Start Debug Print ---
        # print(f"DEBUG: Fetched {snippet_count} snippets.")
        # --- End Debug Print ---

        # --- Fetch votes/views details ---
        snippet_ids = [row['id'] for row in snippets_rows]
        snippet_details = {}
        if snippet_ids:
            for row in snippets_rows: snippet_details[row['id']] = {'views': row['views'] or 0, 'upvotes': 0, 'downvotes': 0}
            placeholders = ','.join('?' * len(snippet_ids))
            votes_rows = conn.execute(f'''SELECT snippet_id, SUM(CASE vote_type WHEN 1 THEN 1 ELSE 0 END) up, SUM(CASE vote_type WHEN -1 THEN 1 ELSE 0 END) down FROM votes WHERE snippet_id IN ({placeholders}) GROUP BY snippet_id''', snippet_ids).fetchall()
            for vote_row in votes_rows:
                 if vote_row['snippet_id'] in snippet_details:
                     snippet_details[vote_row['snippet_id']]['upvotes'] = vote_row['up']
                     snippet_details[vote_row['snippet_id']]['downvotes'] = vote_row['down']
        # --- Start Debug Print ---
        # print(f"DEBUG: Processed snippet vote/view details.")
        # --- End Debug Print ---

        # --- Process Snippets for Template ---
        snippets_data_for_template = []
        for row in snippets_rows:
            snippet_dict = dict(row)
            details = snippet_details.get(row['id'], {})
            snippet_dict.update(details)
            snippet_dict['created_at'] = parse_db_date(snippet_dict.get('created_at'))
            snippets_data_for_template.append(snippet_dict)
        # --- Start Debug Print ---
        # print(f"DEBUG: Processed snippets into snippets_data_for_template.")
        # --- End Debug Print ---

        # --- Fetch viewer interaction data ---
        user_favorites_ids = set()
        user_bookmarks_ids = set()
        if viewer_user_id:
             try:
                 fav_rows = conn.execute('SELECT snippet_id FROM favorites WHERE user_id = ?', (viewer_user_id,)).fetchall()
                 user_favorites_ids = {row['snippet_id'] for row in fav_rows}
             except sqlite3.Error as e_fav:
                 app.logger.warning(f"DB error fetching favorites for viewer {viewer_user_id} on profile {profile_user_id}: {e_fav}")
             try:
                 bookmark_rows = conn.execute('SELECT snippet_id FROM bookmarks WHERE user_id = ?', (viewer_user_id,)).fetchall()
                 user_bookmarks_ids = {row['snippet_id'] for row in bookmark_rows}
             except sqlite3.Error as e_book:
                 app.logger.warning(f"DB error fetching bookmarks for viewer {viewer_user_id} on profile {profile_user_id}: {e_book}")
        # --- Start Debug Print ---
        # print(f"DEBUG: Fetched viewer interactions. Fav IDs: {len(user_favorites_ids)}, Bookmark IDs: {len(user_bookmarks_ids)}")
        # --- End Debug Print ---

        profile_setup_complete = bool(user_data_row['profile_setup'])
        # --- Start Debug Print ---
        # print(f"DEBUG: Profile setup complete: {profile_setup_complete}")
        # --- End Debug Print ---

        # === CONDITIONAL RENDERING ===
        # --- Start Debug Print ---
        print(f"DEBUG: Checking conditional rendering. is_own_profile: {is_own_profile}") # Keep this print
        # --- End Debug Print ---
        if is_own_profile:
            # --- Start Debug Print ---
            print(f"DEBUG: Branch 'if is_own_profile' entered. Attempting to render profile.html") # Keep this print
            # --- End Debug Print ---

            # !!! RENDER_TEMPLATE CALL IS RESTORED !!!
            return render_template('profile.html',
                                   user=user_data_row,
                                   join_date=join_date_obj,
                                   bio=user_data_row['bio'],
                                   profile_picture=user_data_row['profile_picture'],
                                   snippet_count=snippet_count,
                                   followers_count=followers_count,
                                   following_count=following_count,
                                   snippets=snippets_data_for_template,
                                   snippet_views_map={k: v['views'] for k, v in snippet_details.items()},
                                   user_favorites_ids=user_favorites_ids,
                                   user_bookmarks_ids=user_bookmarks_ids,
                                   profile_setup=profile_setup_complete,
                                   is_own_profile=True,
                                   is_following=False
                                   )
        else: # Render Public Profile
            # --- Start Debug Print ---
            print(f"DEBUG: Branch 'else' (for user_profile.html) entered.") # Keep this print
            # --- End Debug Print ---
            # --- Render PUBLIC profile template ---
            total_upvotes = 0
            try:
                total_upvotes_row = conn.execute('''
                     SELECT SUM(CASE WHEN v.vote_type = 1 THEN 1 ELSE 0 END) as total_ups
                     FROM votes v JOIN snippets s ON v.snippet_id = s.id
                     WHERE s.user_id = ? AND s.is_private = 0
                ''', (profile_user_id,)).fetchone()
                if total_upvotes_row and total_upvotes_row['total_ups'] is not None:
                    total_upvotes = total_upvotes_row['total_ups']
            except sqlite3.Error as e_upvotes:
                 app.logger.warning(f"DB error fetching total upvotes for profile {profile_user_id}: {e_upvotes}")

            stats_tuple = (followers_count, following_count, snippet_count, total_upvotes)
            # --- Start Debug Print ---
            print(f"DEBUG: Calculated stats_tuple: {stats_tuple}. Attempting to render user_profile.html") # Keep this print
            # --- End Debug Print ---
            return render_template('user_profile.html',
                                   user=user_data_row,
                                   stats=stats_tuple,
                                   snippets=snippets_data_for_template,
                                   is_following=is_following,
                                   join_date=join_date_obj
                                  )

        # This print should ideally NOT be reached
        # print("DEBUG: *** MAJOR WARNING: Reached end of TRY block without returning! Check conditional logic. ***")

    # --- Error Handling (Keep `raise e` active for debugging template errors) ---
    except sqlite3.Error as e:
        app.logger.error(f"DB Error rendering profile for user '{username or 'self'}': {e}")
        flash("Error loading profile due to a database issue.", "error")
        print(f"DEBUG: *** sqlite3.Error caught: {e} ***")
        raise e # Let Flask show the error page during debug

    except Exception as e:
        app.logger.error(f"General Error rendering profile for user '{username or 'self'}': {e}", exc_info=True)
        flash("An unexpected error occurred while loading the profile.", "error")
        print(f"DEBUG: *** Exception caught: {e} ***")
        raise e # Let Flask show the error page during debug

    # This print should definitely NOT be reached if logic is correct
    # print("DEBUG: *** MAJOR WARNING: Reached end of FUNCTION without returning! Check logic. ***")
    # Fallback return removed as `raise e` should handle errors now

# --- Setup/Settings Routes ---
@app.route('/setup_profile', methods=['GET', 'POST'])
def setup_profile():
    user_id = get_current_user_id()
    if not user_id:
        return redirect(url_for('login'))

    conn = get_db()
    try:
        user = conn.execute('''
            SELECT id, username, email, password, created_at, profile_picture,
                   bio, age, dob, profession, profile_setup, full_name, status,
                   experience, education, skills, country, website
            FROM users
            WHERE id = ?
        ''', (user_id,)).fetchone()

        if not user:
            flash('User not found.', 'error')
            return redirect(url_for('login'))

        if user['profile_setup'] == 1:
            flash('Profile already set up. Edit via Settings.', 'info')
            return redirect(url_for('profile'))

        if request.method == 'POST':
            # Extract form data
            bio = request.form.get('bio')
            age = request.form.get('age')
            dob = request.form.get('dob')
            profession = request.form.get('profession')
            full_name = request.form.get('full_name')
            status = request.form.get('status')
            experience = request.form.get('experience')
            education = request.form.get('education')
            skills = ','.join(request.form.getlist('skills[]')) if request.form.getlist('skills[]') else ''
            country = request.form.get('country')
            website = request.form.get('website')
            filename = user['profile_picture'] # Keep existing picture unless new one uploaded

            # Handle file upload
            if 'profile_picture' in request.files:
                file = request.files['profile_picture']
                if file.filename != '' and allowed_file(file.filename):
                    # Ensure secure filename includes user ID for uniqueness
                    base, ext = os.path.splitext(file.filename)
                    filename = secure_filename(f"{user_id}_{base}{ext}")
                    try:
                        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    except Exception as e_save:
                        app.logger.error(f"Error saving profile picture '{filename}' for user {user_id}: {e_save}")
                        flash("Error saving profile picture.", "error")
                        # Decide if you want to proceed without the picture or return
                        # return render_template('setup_profile.html', user=user) # Or maybe revert filename?

            # Basic Validation
            if not bio or len(bio) > 200:
                flash('Bio is required and must be under 200 characters.', 'error')
            elif age and (not age.isdigit() or int(age) < 13 or int(age) > 120):
                flash('Age must be a number between 13 and 120.', 'error')
            elif dob and not re.match(r'^\d{4}-\d{2}-\d{2}$', dob):
                flash('Date of birth must be in YYYY-MM-DD format.', 'error')
            else:
                 # Update user data
                conn.execute('''
                    UPDATE users
                    SET bio = ?, age = ?, dob = ?, profession = ?, full_name = ?,
                        status = ?, experience = ?, education = ?, skills = ?,
                        country = ?, website = ?, profile_picture = ?, profile_setup = 1
                    WHERE id = ?
                ''', (bio, int(age) if age else None, dob, profession, full_name,
                      status, int(experience) if experience else None, education,
                      skills, country, website, filename, user_id))
                conn.commit()
                flash('Profile set up successfully!', 'success')
                return redirect(url_for('profile'))

            # If validation fails on POST, re-render form
            # It will fall through to the render_template below

        # Render form for GET or failed POST
        return render_template('setup_profile.html', user=user)

    except sqlite3.Error as e:
        conn.rollback()
        app.logger.error(f"Database error during profile setup for user {user_id}: {e}")
        flash("Database error during profile setup.", "error")
        # In case of DB error during GET/POST, redirecting might be safer
        # than trying to re-render with potentially inconsistent data.
        return redirect(url_for('profile')) # Redirect somewhere sensible on DB error
    except Exception as e: # Catch potential non-DB errors during POST processing
        app.logger.error(f"General error during profile setup for user {user_id}: {e}", exc_info=True)
        flash("An unexpected error occurred during profile setup.", "error")
        # Re-render form if possible, otherwise redirect
        # Re-fetching user might fail if the error was DB-related initially
        user_data_for_render = user if 'user' in locals() else None # Check if user was fetched
        if user_data_for_render:
             return render_template('setup_profile.html', user=user_data_for_render)
        else:
             return redirect(url_for('profile'))


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    user_id = get_current_user_id()
    if not user_id:
        flash('Please login to access settings.', 'error')
        return redirect(url_for('login'))

    conn = get_db()
    try:
        if request.method == 'POST':
            # Extract form data
            bio = request.form.get('bio')
            age = request.form.get('age')
            dob = request.form.get('dob')
            profession = request.form.get('profession')
            full_name = request.form.get('full_name')
            status = request.form.get('status')
            experience = request.form.get('experience')
            education = request.form.get('education')
            skills = ','.join(request.form.getlist('skills')) if request.form.getlist('skills') else ''
            country = request.form.get('country')
            website = request.form.get('website')

            # Get current profile picture
            current_user = conn.execute('SELECT profile_picture FROM users WHERE id = ?', (user_id,)).fetchone()
            filename = current_user['profile_picture'] if current_user else None

            # Handle file upload
            if 'profile_picture' in request.files:
                file = request.files['profile_picture']
                if file.filename != '' and allowed_file(file.filename):
                    base, ext = os.path.splitext(file.filename)
                    filename = secure_filename(f"{user_id}_{base}{ext}")
                    try:
                        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    except Exception as e_save:
                        app.logger.error(f"Error saving profile picture '{filename}' in settings for user {user_id}: {e_save}")
                        flash("Error saving profile picture.", "error")
                        filename = current_user['profile_picture'] if current_user else None  # Revert to old picture

            # Validation
            errors = []
            # Age: Optional, must be 13–120 if provided
            if age and (not age.isdigit() or int(age) < 13 or int(age) > 120):
                errors.append('Age must be a number between 13 and 120.')
            # DOB: Optional, must be YYYY-MM-DD if provided
            if dob and not re.match(r'^\d{4}-\d{2}-\d{2}$', dob):
                errors.append('Date of birth must be in YYYY-MM-DD format.')
            # Experience: Optional, must be 0–50 if provided
            if experience and (not experience.isdigit() or int(experience) < 0 or int(experience) > 50):
                errors.append('Experience must be a number between 0 and 50.')
            # Website: Optional, basic URL check if provided
            if website and not re.match(r'^https?://[^\s/$.?#].[^\s]*$', website):
                errors.append('Website must be a valid URL (e.g., https://example.com).')
            # Profession: Optional, must be valid option if provided
            valid_professions = [
                '', 'software_developer', 'data_scientist', 'web_designer', 'student',
                'teacher', 'engineer', 'marketing_specialist', 'other'
            ]
            if profession and profession not in valid_professions:
                errors.append('Invalid profession selected.')
            # Status: Optional, must be valid option if provided
            valid_statuses = ['', 'student', 'working_professional', 'freelancer', 'other']
            if status and status not in valid_statuses:
                errors.append('Invalid status selected.')
            # Education: Optional, must be valid option if provided
            valid_educations = [
                '', 'high_school', 'associate', 'bachelor', 'master', 'phd',
                'certificate', 'none'
            ]
            if education and education not in valid_educations:
                errors.append('Invalid education selected.')
            # Country: Optional, must be valid option if provided
            valid_countries = ['', 'india', 'united_states', 'united_kingdom', 'canada', 'australia']
            if country and country not in valid_countries:
                errors.append('Invalid country selected.')

            if errors:
                for error in errors:
                    flash(error, 'error')
                # Re-render form with user data
                user = conn.execute('''
                    SELECT id, username, email, bio, age, dob, profession, profile_picture,
                           full_name, status, experience, education, skills, country, website
                    FROM users WHERE id = ?
                ''', (user_id,)).fetchone()
                return render_template('settings.html', user=user)

            # Update user data
            conn.execute('''
                UPDATE users
                SET bio = ?, age = ?, dob = ?, profession = ?, full_name = ?,
                    status = ?, experience = ?, education = ?, skills = ?,
                    country = ?, website = ?, profile_picture = ?
                WHERE id = ?
            ''', (
                bio if bio and bio.strip() else None,
                int(age) if age and age.isdigit() else None,
                dob if dob else None,
                profession if profession else None,
                full_name if full_name and full_name.strip() else None,
                status if status else None,
                int(experience) if experience and experience.isdigit() else None,
                education if education else None,
                skills if skills else None,
                country if country else None,
                website if website and website.strip() else None,
                filename,
                user_id
            ))
            conn.commit()
            flash('Settings updated successfully!', 'success')
            return redirect(url_for('profile'))

        # GET Request: Fetch user data for the form
        user = conn.execute('''
            SELECT id, username, email, bio, age, dob, profession, profile_picture,
                   full_name, status, experience, education, skills, country, website
            FROM users WHERE id = ?
        ''', (user_id,)).fetchone()

        if not user:
            flash('User not found.', 'error')
            return redirect(url_for('login'))

        return render_template('settings.html', user=user)

    except sqlite3.Error as e:
        conn.rollback()
        app.logger.error(f"Database error during settings update for user {user_id}: {e}")
        flash("Database error saving settings.", "error")
        user = conn.execute('''
            SELECT id, username, email, bio, age, dob, profession, profile_picture,
                   full_name, status, experience, education, skills, country, website
            FROM users WHERE id = ?
        ''', (user_id,)).fetchone()
        return render_template('settings.html', user=user)


@app.route('/upload_profile_picture', methods=['POST'])
def upload_profile_picture():
    user_id = get_current_user_id()
    if not user_id:
        flash('Please login first.', 'error')
        return redirect(url_for('login'))

    if 'profile_picture' not in request.files:
        flash('No file part', 'error')
        return redirect(request.referrer or url_for('profile')) # Go back

    file = request.files['profile_picture']

    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(request.referrer or url_for('profile'))

    if file and allowed_file(file.filename):
        base, ext = os.path.splitext(file.filename)
        filename = secure_filename(f"{user_id}_{base}{ext}")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        conn = get_db()
        try:
            file.save(file_path)
            conn.execute('UPDATE users SET profile_picture = ? WHERE id = ?', (filename, user_id))
            conn.commit()
            flash('Profile picture updated successfully!', 'success')
            return redirect(url_for('profile'))
        except sqlite3.Error as e:
            conn.rollback()
            app.logger.error(f"DB Error updating profile picture filename for user {user_id}: {e}")
            flash('Database error saving picture reference.', 'error')
        except Exception as e_save:
             app.logger.error(f"Error saving profile picture file '{filename}' for user {user_id}: {e_save}")
             flash('Error saving picture file.', 'error')
        return redirect(request.referrer or url_for('profile'))

    else: # File type not allowed
        flash('Invalid file type. Allowed types: png, jpg, jpeg, gif', 'error')
        return redirect(request.referrer or url_for('profile'))

# --- Follower/Following Routes ---
@app.route('/get_followers')
def get_followers():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'message': 'Please login first'}), 401

    conn = get_db()
    try:
        followers = conn.execute('''
            SELECT u.username, u.profile_picture,
                   (SELECT COUNT(*) FROM snippets WHERE user_id = u.id AND is_private = 0) as snippet_count
            FROM users u
            JOIN followers f ON u.id = f.follower_id
            WHERE f.followed_id = ?
        ''', (user_id,)).fetchall()

        return jsonify({
            'followers': [{'username': f['username'], 'snippet_count': f['snippet_count'], 'profile_picture': f['profile_picture']} for f in followers]
        })
    except sqlite3.Error as e:
        app.logger.error(f"DB Error fetching followers for user {user_id}: {e}")
        return jsonify({'success': False, 'message': 'Database error'}), 500


@app.route('/get_following')
def get_following():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'message': 'Please login first'}), 401

    conn = get_db()
    try:
        following = conn.execute('''
            SELECT u.username, u.profile_picture,
                   (SELECT COUNT(*) FROM snippets WHERE user_id = u.id AND is_private = 0) as snippet_count
            FROM users u
            JOIN followers f ON u.id = f.followed_id
            WHERE f.follower_id = ?
        ''', (user_id,)).fetchall()

        return jsonify({
            'following': [{'username': f['username'], 'snippet_count': f['snippet_count'], 'profile_picture': f['profile_picture']} for f in following]
        })
    except sqlite3.Error as e:
        app.logger.error(f"DB Error fetching following list for user {user_id}: {e}")
        return jsonify({'success': False, 'message': 'Database error'}), 500

@app.route('/follow/<username>', methods=['POST'])
def follow_user(username):
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'message': 'Please login first'}), 401

    conn = get_db()
    try:
        target_user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()

        if not target_user:
            return jsonify({'success': False, 'message': 'User not found'}), 404

        target_user_id = target_user['id']
        if target_user_id == user_id:
            return jsonify({'success': False, 'message': 'Cannot follow yourself'}), 400

        conn.execute('INSERT INTO followers (follower_id, followed_id) VALUES (?, ?)', (user_id, target_user_id))
        conn.commit()
        return jsonify({'success': True, 'message': f'Now following {username}'})

    except sqlite3.IntegrityError: # Already following
        conn.rollback()
        # It's okay if they are already following, return success? Or a specific status?
        # Returning success might be better UX than an error here.
        # return jsonify({'success': False, 'message': 'Already following'}), 409 # Conflict
        return jsonify({'success': True, 'message': f'Already following {username}'})
    except sqlite3.Error as e:
        conn.rollback()
        app.logger.error(f"DB Error user {user_id} following {username}: {e}")
        return jsonify({'success': False, 'message': 'Database error'}), 500

@app.route('/unfollow/<username>', methods=['POST'])
def unfollow_user(username):
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'message': 'Please login first'}), 401

    conn = get_db()
    try:
        target_user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()

        if not target_user:
             return jsonify({'success': False, 'message': 'User not found'}), 404

        target_user_id = target_user['id']

        # Check if actually following before deleting? Optional.
        deleted = conn.execute('''
            DELETE FROM followers
            WHERE follower_id = ? AND followed_id = ?
        ''', (user_id, target_user_id))
        conn.commit()

        # Check if a row was actually deleted using deleted.rowcount (might be driver dependent)
        # if deleted.rowcount > 0:
        return jsonify({'success': True, 'message': f'Unfollowed {username}'})
        # else:
        #     # If not following, is it an error or success? Success is usually better UX.
        #     return jsonify({'success': True, 'message': f'You were not following {username}'})

    except sqlite3.Error as e:
        conn.rollback()
        app.logger.error(f"DB Error user {user_id} unfollowing {username}: {e}")
        return jsonify({'success': False, 'message': 'Database error'}), 500


# --- Explore and Snippet Viewing ---

# Helper function for trending topics
def get_trending_topics():
    """Fetches top 10 most frequent languages from recent public snippets."""
    conn = get_db() # Use get_db
    try:
        cursor = conn.execute("""
            SELECT language, COUNT(*) as count FROM snippets
            WHERE is_private = 0 AND language IS NOT NULL AND language != '' AND created_at > date('now', '-7 days')
            GROUP BY language ORDER BY count DESC, language ASC LIMIT 10
        """)
        # Return list of dicts (Row objects behave like dicts)
        return cursor.fetchall()
    except sqlite3.Error as e:
        app.logger.error(f"Database error in get_trending_topics: {e}")
        return [] # Return empty list on error

@app.route('/explore')
def explore():
    viewer_user_id = get_current_user_id()
    sort = request.args.get('sort', 'newest')
    topic_filter = request.args.get('topic')
    conn = get_db()

    snippets_data = []
    user_favorites_ids = set()
    user_bookmarks_ids = set()

    try:
        query = """
            SELECT
                s.id, s.title, s.language, s.description, s.created_at, s.views,
                s.user_id, -- Include owner ID
                u.username AS owner_username,
                COALESCE(v.upvotes, 0) as upvotes,
                COALESCE(v.downvotes, 0) as downvotes
            FROM snippets s
            JOIN users u ON s.user_id = u.id
            LEFT JOIN ( -- Pre-calculate votes per snippet
                SELECT
                    snippet_id,
                    SUM(CASE WHEN vote_type = 1 THEN 1 ELSE 0 END) as upvotes,
                    SUM(CASE WHEN vote_type = -1 THEN 1 ELSE 0 END) as downvotes
                FROM votes
                GROUP BY snippet_id
            ) v ON s.id = v.snippet_id
            WHERE s.is_private = 0
        """
        params = []

        if topic_filter:
            query += " AND s.language = ?"
            params.append(topic_filter)

        if sort == 'most-upvoted':
            query += " ORDER BY (COALESCE(v.upvotes, 0) - COALESCE(v.downvotes, 0)) DESC, s.created_at DESC"
        elif sort == 'trending':
             # Add a simple trending logic (e.g., recent + votes/views)
             # This is a basic example: votes in last 7 days
             query += """
                 ORDER BY (
                     SELECT COUNT(*) FROM votes v_trend
                     WHERE v_trend.snippet_id = s.id AND v_trend.created_at > datetime('now', '-7 days') AND v_trend.vote_type = 1
                 ) DESC, s.created_at DESC
             """
        else: # Default 'newest'
            query += " ORDER BY s.created_at DESC"

        snippets_rows = conn.execute(query, params).fetchall()

        for row in snippets_rows:
            snippet_dict = dict(row)
            snippet_dict['created_at'] = parse_db_date(snippet_dict.get('created_at'))
            snippets_data.append(snippet_dict)

        if viewer_user_id:
             try:
                fav_rows = conn.execute('SELECT snippet_id FROM favorites WHERE user_id = ?', (viewer_user_id,)).fetchall()
                user_favorites_ids = {row['snippet_id'] for row in fav_rows}
             except sqlite3.Error as e: app.logger.warning(f"DB Err fav explore user {viewer_user_id}: {e}")
             try:
                bookmark_rows = conn.execute('SELECT snippet_id FROM bookmarks WHERE user_id = ?', (viewer_user_id,)).fetchall()
                user_bookmarks_ids = {row['snippet_id'] for row in bookmark_rows}
             except sqlite3.Error as e: app.logger.warning(f"DB Err bookmark explore user {viewer_user_id}: {e}")

    except sqlite3.Error as e:
        app.logger.error(f"Database error in explore route: {e}")
        flash('An error occurred loading snippets.', 'error')
        snippets_data = []
        user_favorites_ids = set()
        user_bookmarks_ids = set()

    trending_topics_data = get_trending_topics() # Fetch using helper

    return render_template('explore.html',
                           snippets=snippets_data,
                           trending_topics=trending_topics_data, # Pass fetched data
                           current_sort=sort,
                           current_topic=topic_filter,
                           user_favorites_ids=user_favorites_ids,
                           user_bookmarks_ids=user_bookmarks_ids)


@app.route('/explore/snippet/<int:id>')
def view_snippet_explore(id):
    """Displays a single public snippet, comments, and viewer's interaction status."""
    conn = get_db()
    viewer_user_id = get_current_user_id()

    snippet_dict = None
    root_comments = []
    is_bookmarked = False
    is_favorited = False # Favorite status of viewer for THIS snippet
    user_vote = None

    try:
        snippet_row = conn.execute("""
            SELECT
                s.*, u.username as owner_username,
                COALESCE(v.upvotes, 0) as upvotes,
                COALESCE(v.downvotes, 0) as downvotes
            FROM snippets s
            JOIN users u ON s.user_id = u.id
            LEFT JOIN (
                 SELECT snippet_id, SUM(CASE WHEN vote_type = 1 THEN 1 ELSE 0 END) as upvotes,
                        SUM(CASE WHEN vote_type = -1 THEN 1 ELSE 0 END) as downvotes
                 FROM votes GROUP BY snippet_id
            ) v ON s.id = v.snippet_id
            WHERE s.id = ? AND s.is_private = 0
        """, (id,)).fetchone()

        if not snippet_row:
            flash('Snippet not found or is private', 'error')
            return redirect(url_for('explore'))

        snippet_dict = dict(snippet_row)

        # Increment View Count (Best effort)
        try:
            conn.execute('UPDATE snippets SET views = COALESCE(views, 0) + 1 WHERE id = ?', (id,))
            conn.commit()
        except sqlite3.Error as e_view:
            conn.rollback() # Rollback only the view count update
            app.logger.warning(f"Failed to increment view count for snippet {id}: {e_view}")

        # Fetch Comments (Nested Structure)
        comments_rows = conn.execute('''
            SELECT c.id, c.content, c.created_at, u.username, u.profile_picture, c.parent_id
            FROM comments c JOIN users u ON c.user_id = u.id
            WHERE c.snippet_id = ?
            ORDER BY c.parent_id NULLS FIRST, c.created_at ASC
        ''', (id,)).fetchall()

        comments_by_id = {}
        for row in comments_rows:
            comment = dict(row)
            comment['created_at'] = parse_db_date(comment.get('created_at'))
            comment['replies'] = []
            comments_by_id[comment['id']] = comment

        root_comments = []
        for comment_id, comment in comments_by_id.items():
            parent_id = comment['parent_id']
            if parent_id is None:
                root_comments.append(comment)
            elif parent_id in comments_by_id:
                 comments_by_id[parent_id]['replies'].append(comment)

        # Fetch Viewer's Status (Vote, Bookmark, Favorite) IF Logged In
        if viewer_user_id:
             try:
                 bookmark_check = conn.execute('SELECT 1 FROM bookmarks WHERE user_id = ? AND snippet_id = ?', (viewer_user_id, id)).fetchone()
                 is_bookmarked = bool(bookmark_check)
             except sqlite3.Error as e_bm: app.logger.warning(f"DB error checking bookmark status snip {id} user {viewer_user_id}: {e_bm}")
             try:
                 vote_check = conn.execute('SELECT vote_type FROM votes WHERE user_id = ? AND snippet_id = ?', (viewer_user_id, id)).fetchone()
                 if vote_check: user_vote = vote_check['vote_type']
             except sqlite3.Error as e_vt: app.logger.warning(f"DB error checking vote status snip {id} user {viewer_user_id}: {e_vt}")
             try:
                 fav_check = conn.execute('SELECT 1 FROM favorites WHERE user_id = ? AND snippet_id = ?', (viewer_user_id, id)).fetchone()
                 is_favorited = bool(fav_check)
             except sqlite3.Error as e_fv: app.logger.warning(f"DB error checking favorite status snip {id} user {viewer_user_id}: {e_fv}")


        # Parse Snippet Dates
        snippet_dict['created_at'] = parse_db_date(snippet_dict.get('created_at'))
        snippet_dict['updated_at'] = parse_db_date(snippet_dict.get('updated_at')) # If updated_at exists

        return render_template('view_snippet_explore.html',
                             snippet=snippet_dict,
                             comments=root_comments,
                             is_bookmarked=is_bookmarked,
                             is_favorited=is_favorited,
                             user_vote=user_vote)

    except sqlite3.Error as e:
        app.logger.error(f"DB Error viewing public snippet {id}: {e}")
        flash('Error loading snippet details.', 'error')
        return redirect(url_for('explore'))
    except Exception as e:
        app.logger.error(f"General Error viewing public snippet {id}: {e}", exc_info=True)
        flash("An unexpected error occurred.", "error")
        return redirect(url_for('explore'))

# --- Snippet Management (Own) ---
@app.route('/snippet/new', methods=['GET', 'POST'])
def new_snippet():
    user_id = get_current_user_id()
    if not user_id:
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if is_ajax:
            return jsonify({'success': False, 'message': 'Please login first.'}), 401
        flash('Please login first.', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        title = request.form.get('title')
        code = request.form.get('code')
        language = request.form.get('language')
        description = request.form.get('description', '')
        # Add is_private if you have a checkbox in the form
        is_private = bool(request.form.get('is_private')) # Example: <input type="checkbox" name="is_private">

        if not title or not code or not language:
            msg = 'Title, code, and language are required.'
            if is_ajax: return jsonify({'success': False, 'message': msg}), 400
            flash(msg, 'error'); return render_template('new_snippet.html')

        conn = get_db()
        try:
            cursor = conn.execute('''
                INSERT INTO snippets (user_id, title, code, language, description, is_private)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, title, code.strip(), language, description, is_private))
            snippet_id = cursor.lastrowid
            conn.commit()

            redirect_url = url_for('view_snippet', id=snippet_id) # Redirect to the private view
            if is_ajax:
                return jsonify({
                    'success': True,
                    'message': 'Snippet created successfully!',
                    'redirect': redirect_url
                }), 201
            flash('Snippet created successfully!', 'success')
            return redirect(redirect_url)

        except sqlite3.Error as e:
            conn.rollback()
            app.logger.error(f"DB Error creating snippet for user {user_id}: {e}")
            msg = 'Database error creating snippet.'
            if is_ajax: return jsonify({'success': False, 'message': msg}), 500
            flash(msg, 'error'); return render_template('new_snippet.html')

    return render_template('new_snippet.html')

@app.route('/snippet/<int:id>')
def view_snippet(id):
    """View own or accessible snippet (private view if owner)."""
    user_id = get_current_user_id()
    if not user_id:
        flash('Please login first.', 'error')
        return redirect(url_for('login'))

    conn = get_db()
    try:
        # Fetch snippet, check if user owns it or if it's public
        # Also fetch owner username for display
        snippet = conn.execute('''
            SELECT s.*, u.username AS owner_username
            FROM snippets s
            JOIN users u ON s.user_id = u.id
            WHERE s.id = ? AND (s.user_id = ? OR s.is_private = 0)
        ''', (id, user_id)).fetchone()

        if snippet is None:
            flash('Snippet not found or you do not have permission to view it.', 'error')
            return redirect(url_for('profile')) # Or explore?

        # Increment view count (only if viewer is not the owner?) - Optional logic
        if snippet['user_id'] != user_id:
            try:
                conn.execute('UPDATE snippets SET views = COALESCE(views, 0) + 1 WHERE id = ?', (id,))
                conn.commit()
            except sqlite3.Error as e_view:
                conn.rollback()
                app.logger.warning(f"Failed to increment view count for snippet {id} (viewer {user_id}): {e_view}")

        # Prepare data for template
        snippet_data = dict(snippet)
        snippet_data['created_at'] = parse_db_date(snippet_data.get('created_at'))
        snippet_data['updated_at'] = parse_db_date(snippet_data.get('updated_at'))

        # Fetch comments, votes, favorite status etc. if needed for this view
        # (Similar logic as view_snippet_explore can be added here if required)
        # For simplicity, just showing snippet details now

        return render_template('view_snippet.html', snippet=snippet_data) # Pass dict

    except sqlite3.Error as e:
        conn.rollback() # Rollback view count if it was attempted before error
        app.logger.error(f"DB Error viewing snippet {id} for user {user_id}: {e}")
        flash('Error loading snippet.', 'error')
        return redirect(url_for('profile'))


@app.route('/snippet/edit/<int:id>', methods=['GET', 'POST'])
def edit_snippet(id):
    user_id = get_current_user_id()
    if not user_id:
        flash('Please login first.', 'error')
        return redirect(url_for('login'))

    conn = get_db()
    try:
        # Fetch snippet only if user owns it
        snippet = conn.execute('''
            SELECT id, title, code, language, description, is_private
            FROM snippets
            WHERE id = ? AND user_id = ?
        ''', (id, user_id)).fetchone()

        if not snippet:
            flash('Snippet not found or unauthorized.', 'error')
            return redirect(url_for('profile'))

        if request.method == 'POST':
            title = request.form.get('title')
            code = request.form.get('code')
            language = request.form.get('language')
            description = request.form.get('description')
            is_private = bool(request.form.get('is_private')) # Get checkbox value

            if not title or not code or not language:
                 flash('Title, code, and language are required.', 'error')
                 # Re-render form with existing data on validation error
                 return render_template('edit_snippet.html', snippet=snippet)

            conn.execute('''
                UPDATE snippets
                SET title = ?, code = ?, language = ?, description = ?, is_private = ?,
                    updated_at = CURRENT_TIMESTAMP -- Update timestamp on edit
                WHERE id = ? AND user_id = ?
            ''', (title, code, language, description, is_private, id, user_id))
            conn.commit()
            flash('Snippet updated successfully!', 'success')
            return redirect(url_for('view_snippet', id=id)) # Redirect to the private view

        # GET request: render edit form
        return render_template('edit_snippet.html', snippet=snippet) # Pass Row object

    except sqlite3.Error as e:
        conn.rollback()
        app.logger.error(f"DB Error editing snippet {id} for user {user_id}: {e}")
        flash('Database error saving snippet.', 'error')
        # Fetch snippet again to render form if update failed
        snippet = conn.execute('SELECT * FROM snippets WHERE id = ? AND user_id = ?', (id, user_id)).fetchone()
        if snippet:
            return render_template('edit_snippet.html', snippet=snippet)
        else: # If fetch fails after error, redirect
            return redirect(url_for('profile'))


@app.route('/snippet/<int:id>/delete', methods=['POST'])
def delete_snippet(id):
    user_id = get_current_user_id()
    if not user_id:
         # Can return JSON error if called via JS, or redirect otherwise
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Authentication required'}), 401
        flash('Please login first.', 'error')
        return redirect(url_for('login'))

    conn = get_db()
    try:
        # Ensure user owns the snippet before deleting
        # Also delete related data (votes, comments, favorites, bookmarks) - IMPORTANT
        conn.execute('BEGIN') # Use transaction
        snippet_check = conn.execute('SELECT id FROM snippets WHERE id = ? AND user_id = ?', (id, user_id)).fetchone()

        if not snippet_check:
             conn.execute('ROLLBACK')
             msg = 'Snippet not found or unauthorized.'
             if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                 return jsonify({'success': False, 'message': msg}), 404
             flash(msg, 'error')
             return redirect(url_for('profile'))

        # Delete related data first (adjust table names if different)
        conn.execute('DELETE FROM votes WHERE snippet_id = ?', (id,))
        conn.execute('DELETE FROM comments WHERE snippet_id = ?', (id,))
        conn.execute('DELETE FROM favorites WHERE snippet_id = ?', (id,))
        conn.execute('DELETE FROM bookmarks WHERE snippet_id = ?', (id,))
        # Potentially delete ratings if using that system
        # conn.execute('DELETE FROM ratings WHERE snippet_id = ?', (id,))

        # Delete the snippet itself
        conn.execute('DELETE FROM snippets WHERE id = ? AND user_id = ?', (id, user_id))
        conn.execute('COMMIT') # Commit transaction

        msg = 'Snippet deleted successfully!'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': msg, 'redirect': url_for('profile')})
        flash(msg, 'success')
        return redirect(url_for('profile'))

    except sqlite3.Error as e:
        conn.execute('ROLLBACK') # Rollback transaction on error
        app.logger.error(f"DB Error deleting snippet {id} for user {user_id}: {e}")
        msg = 'Database error deleting snippet.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': msg}), 500
        flash(msg, 'error')
        return redirect(url_for('profile'))

# --- Favorites & Bookmarks ---

@app.route('/snippet/<int:snippet_id>/toggle_favorite', methods=['POST'])
def toggle_favorite(snippet_id):
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'Authentication required', 'action': 'login'}), 401

    conn = get_db()
    try:
        # Check if snippet exists and is accessible (public or own private)
        snippet = conn.execute('SELECT id FROM snippets WHERE id = ? AND (is_private = 0 OR user_id = ?)',
                              (snippet_id, user_id)).fetchone()
        if not snippet:
            return jsonify({'success': False, 'error': 'Snippet not found or not accessible'}), 404

        existing_favorite = conn.execute('SELECT 1 FROM favorites WHERE user_id = ? AND snippet_id = ?',
                                        (user_id, snippet_id)).fetchone()

        if existing_favorite:
            conn.execute('DELETE FROM favorites WHERE user_id = ? AND snippet_id = ?', (user_id, snippet_id))
            conn.commit()
            app.logger.info(f"User {user_id} unfavorited snippet {snippet_id}")
            return jsonify({'success': True, 'status': 'removed'})
        else:
            # Use INSERT OR IGNORE to prevent potential race conditions if clicked twice fast
            conn.execute('INSERT OR IGNORE INTO favorites (user_id, snippet_id) VALUES (?, ?)', (user_id, snippet_id))
            conn.commit()
            # Check if it was actually inserted (might have been ignored)
            new_fav = conn.execute('SELECT 1 FROM favorites WHERE user_id = ? AND snippet_id = ?',
                                     (user_id, snippet_id)).fetchone()
            if new_fav:
                app.logger.info(f"User {user_id} favorited snippet {snippet_id}")
                return jsonify({'success': True, 'status': 'added'})
            else: # Should not happen with OR IGNORE unless deleted between insert and select
                 app.logger.warning(f"Favorite toggle race condition or issue for user {user_id} snippet {snippet_id}")
                 return jsonify({'success': False, 'error': 'Toggle failed, please retry'}), 500


    except sqlite3.Error as e:
        conn.rollback()
        app.logger.error(f"DB error toggle favorite snip {snippet_id} user {user_id}: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500


@app.route('/favorites')
def view_favorites():
    user_id = get_current_user_id()
    if not user_id:
        flash('Please login to view your favorites.', 'warning')
        return redirect(url_for('login'))

    conn = get_db()
    try:
        favorite_snippets_rows = conn.execute('''
            SELECT
                s.id, s.title, s.language, s.code, s.description, s.created_at,
                s.updated_at, s.is_private, s.views, s.user_id as owner_id,
                u.username as owner_username, f.favorited_at,
                COALESCE(v.upvotes, 0) as upvotes, COALESCE(v.downvotes, 0) as downvotes
            FROM favorites f
            JOIN snippets s ON f.snippet_id = s.id
            JOIN users u ON s.user_id = u.id
            LEFT JOIN (
                 SELECT snippet_id, SUM(CASE WHEN vote_type = 1 THEN 1 ELSE 0 END) as upvotes,
                        SUM(CASE WHEN vote_type = -1 THEN 1 ELSE 0 END) as downvotes
                 FROM votes GROUP BY snippet_id
            ) v ON s.id = v.snippet_id
            WHERE f.user_id = ?
              AND (s.is_private = 0 OR s.user_id = ?) -- Show favorited public or OWN private snippets
            ORDER BY f.favorited_at DESC
        ''', (user_id, user_id)).fetchall() # Pass user_id twice for the OR condition

        user_favorites_ids = {row['id'] for row in favorite_snippets_rows}
        user_bookmarks_ids = set() # Fetch bookmarks if bookmark button is shown on favorite cards
        try:
            bookmark_rows = conn.execute('SELECT snippet_id FROM bookmarks WHERE user_id = ?', (user_id,)).fetchall()
            user_bookmarks_ids = {row['snippet_id'] for row in bookmark_rows}
        except sqlite3.Error as e_book:
            app.logger.warning(f"DB Error fetching bookmarks on favorites page for user {user_id}: {e_book}")


        favorite_snippets_data = []
        for row in favorite_snippets_rows:
            snippet_dict = dict(row)
            # Use the robust parse_db_date helper
            snippet_dict['created_at'] = parse_db_date(snippet_dict.get('created_at'))
            snippet_dict['favorited_at'] = parse_db_date(snippet_dict.get('favorited_at'))
            snippet_dict['updated_at'] = parse_db_date(snippet_dict.get('updated_at'))
            favorite_snippets_data.append(snippet_dict)

        return render_template('favorites.html',
                               snippets=favorite_snippets_data,
                               user_favorites_ids=user_favorites_ids,
                               user_bookmarks_ids=user_bookmarks_ids) # Pass bookmarks if needed

    except sqlite3.Error as e:
         app.logger.error(f"DB Error fetching favorites for user {user_id}: {e}")
         flash("Could not load favorites due to a database error.", "error")
         return redirect(url_for('profile'))


@app.route('/snippet/<int:snippet_id>/toggle_bookmark', methods=['POST'])
def toggle_bookmark(snippet_id):
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'Authentication required', 'action': 'login'}), 401

    conn = get_db()
    try:
        # Ensure the snippet exists and is PUBLIC (usually only bookmark public things)
        # Adjust logic if you allow bookmarking private snippets
        snippet = conn.execute(
            'SELECT id FROM snippets WHERE id = ? AND is_private = 0', (snippet_id,)
        ).fetchone()
        if not snippet:
            return jsonify({'success': False, 'error': 'Public snippet not found'}), 404

        existing_bookmark = conn.execute(
            'SELECT 1 FROM bookmarks WHERE user_id = ? AND snippet_id = ?', (user_id, snippet_id)
        ).fetchone()

        if existing_bookmark:
            conn.execute('DELETE FROM bookmarks WHERE user_id = ? AND snippet_id = ?', (user_id, snippet_id))
            conn.commit()
            app.logger.info(f"User {user_id} removed bookmark: {snippet_id}")
            return jsonify({'success': True, 'status': 'removed'})
        else:
            # Use INSERT OR IGNORE
            conn.execute('INSERT OR IGNORE INTO bookmarks (user_id, snippet_id) VALUES (?, ?)', (user_id, snippet_id))
            conn.commit()
            # Verify insertion
            new_bookmark = conn.execute('SELECT 1 FROM bookmarks WHERE user_id = ? AND snippet_id = ?', (user_id, snippet_id)).fetchone()
            if new_bookmark:
                app.logger.info(f"User {user_id} added bookmark: {snippet_id}")
                return jsonify({'success': True, 'status': 'added'})
            else:
                app.logger.warning(f"Bookmark toggle race condition or issue for user {user_id} snippet {snippet_id}")
                return jsonify({'success': False, 'error': 'Toggle failed, please retry'}), 500

    except sqlite3.Error as e:
        conn.rollback()
        app.logger.error(f"DB error toggle bookmark snip {snippet_id} user {user_id}: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500

@app.route('/bookmarks')
def view_bookmarks():
    user_id = get_current_user_id()
    if not user_id:
        flash('Please login to view bookmarks.', 'warning')
        return redirect(url_for('login'))

    conn = get_db()
    try:
        rows = conn.execute('''
            SELECT
                s.id, s.title, s.language, s.description, s.created_at, s.updated_at,
                s.is_private, s.views, s.user_id as owner_id,
                u.username as owner_username, b.bookmarked_at,
                COALESCE(v.upvotes, 0) as upvotes, COALESCE(v.downvotes, 0) as downvotes
            FROM bookmarks b
            JOIN snippets s ON b.snippet_id = s.id
            JOIN users u ON s.user_id = u.id
            LEFT JOIN (
                 SELECT snippet_id, SUM(CASE WHEN vote_type = 1 THEN 1 ELSE 0 END) as upvotes,
                        SUM(CASE WHEN vote_type = -1 THEN 1 ELSE 0 END) as downvotes
                 FROM votes GROUP BY snippet_id
            ) v ON s.id = v.snippet_id
            WHERE b.user_id = ? AND s.is_private = 0 -- Only show if snippet still exists & is public
            ORDER BY b.bookmarked_at DESC
        ''', (user_id,)).fetchall()

        bookmarks_data = []
        for row in rows:
            snippet_dict = dict(row)
            snippet_dict['created_at'] = parse_db_date(snippet_dict.get('created_at'))
            snippet_dict['bookmarked_at'] = parse_db_date(snippet_dict.get('bookmarked_at'))
            snippet_dict['updated_at'] = parse_db_date(snippet_dict.get('updated_at'))
            bookmarks_data.append(snippet_dict)

        user_bookmarks_ids = {snippet['id'] for snippet in bookmarks_data}
        # Fetch viewer's FAVORITES to correctly display favorite button state if shown on bookmark cards
        user_favorites_ids = set()
        try:
             fav_rows = conn.execute('SELECT snippet_id FROM favorites WHERE user_id=?', (user_id,)).fetchall()
             user_favorites_ids = {r['snippet_id'] for r in fav_rows}
        except sqlite3.Error as e_fav:
             app.logger.warning(f"DB Error fetching favorites on bookmarks page for user {user_id}: {e_fav}")

        return render_template('bookmarks.html',
                               snippets=bookmarks_data,
                               user_bookmarks_ids=user_bookmarks_ids,
                               user_favorites_ids=user_favorites_ids)

    except sqlite3.Error as e:
         app.logger.error(f"DB Error fetching bookmarks user {user_id}: {e}")
         flash("Could not load bookmarks.", "error")
         return redirect(url_for('profile'))

# --- Voting ---
@app.route('/upvote_snippet/<int:id>', methods=['POST'])
def upvote_snippet(id):
    user_id = get_current_user_id()
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if not user_id:
        if is_ajax: return jsonify({'success': False, 'message': 'Please login to vote'}), 401
        flash('Please login to vote.', 'error'); return redirect(url_for('login'))

    conn = get_db()
    try:
        # Ensure snippet exists and is accessible (public or own private)
        # Important: Don't allow voting on non-accessible snippets
        snippet = conn.execute('SELECT id FROM snippets WHERE id = ? AND (is_private = 0 OR user_id = ?)',
                              (id, user_id)).fetchone()
        if not snippet:
            if is_ajax: return jsonify({'success': False, 'message': 'Snippet not found or not accessible'}), 404
            flash('Snippet not found or not accessible.', 'error'); return redirect(request.referrer or url_for('explore'))

        existing_vote_row = conn.execute(
            'SELECT vote_type FROM votes WHERE user_id = ? AND snippet_id = ?',
            (user_id, id)
        ).fetchone()
        current_vote = existing_vote_row['vote_type'] if existing_vote_row else None
        new_vote_state = None

        conn.execute('BEGIN') # Use transaction
        if current_vote == 1: # Clicking upvote again
            conn.execute('DELETE FROM votes WHERE user_id = ? AND snippet_id = ?', (user_id, id))
            new_vote_state = None
        elif current_vote == -1: # Switching from downvote to upvote
            conn.execute('UPDATE votes SET vote_type = 1, created_at = CURRENT_TIMESTAMP WHERE user_id = ? AND snippet_id = ?', (user_id, id))
            new_vote_state = 1
        else: # No existing vote or vote was removed
            conn.execute('INSERT INTO votes (user_id, snippet_id, vote_type) VALUES (?, ?, 1)', (user_id, id))
            new_vote_state = 1
        conn.commit() # Commit transaction

        # Recalculate counts AFTER changes
        counts = conn.execute('''
            SELECT
                SUM(CASE WHEN vote_type = 1 THEN 1 ELSE 0 END) as upvotes,
                SUM(CASE WHEN vote_type = -1 THEN 1 ELSE 0 END) as downvotes
            FROM votes WHERE snippet_id = ?
        ''', (id,)).fetchone()
        upvotes = counts['upvotes'] if counts else 0
        downvotes = counts['downvotes'] if counts else 0

        if is_ajax:
            return jsonify({'success': True, 'upvotes': upvotes, 'downvotes': downvotes, 'user_vote': new_vote_state})
        flash('Vote recorded!', 'success')
        return redirect(request.referrer or url_for('explore'))

    except sqlite3.Error as e:
        conn.rollback()
        app.logger.error(f"DB Error upvoting snippet {id} for user {user_id}: {e}")
        if is_ajax: return jsonify({'success': False, 'message': 'Database error occurred.'}), 500
        flash('Database error occurred.', 'error'); return redirect(request.referrer or url_for('explore'))


@app.route('/downvote_snippet/<int:id>', methods=['POST'])
def downvote_snippet(id):
    user_id = get_current_user_id()
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if not user_id:
        if is_ajax: return jsonify({'success': False, 'message': 'Please login to vote'}), 401
        flash('Please login to vote.', 'error'); return redirect(url_for('login'))

    conn = get_db()
    try:
         # Ensure snippet exists and is accessible (public or own private)
        snippet = conn.execute('SELECT id FROM snippets WHERE id = ? AND (is_private = 0 OR user_id = ?)',
                              (id, user_id)).fetchone()
        if not snippet:
            if is_ajax: return jsonify({'success': False, 'message': 'Snippet not found or not accessible'}), 404
            flash('Snippet not found or not accessible.', 'error'); return redirect(request.referrer or url_for('explore'))

        existing_vote_row = conn.execute(
            'SELECT vote_type FROM votes WHERE user_id = ? AND snippet_id = ?',
            (user_id, id)
        ).fetchone()
        current_vote = existing_vote_row['vote_type'] if existing_vote_row else None
        new_vote_state = None

        conn.execute('BEGIN') # Use transaction
        if current_vote == -1: # Clicking downvote again
            conn.execute('DELETE FROM votes WHERE user_id = ? AND snippet_id = ?', (user_id, id))
            new_vote_state = None
        elif current_vote == 1: # Switching from upvote to downvote
            conn.execute('UPDATE votes SET vote_type = -1, created_at = CURRENT_TIMESTAMP WHERE user_id = ? AND snippet_id = ?', (user_id, id))
            new_vote_state = -1
        else: # No existing vote or vote was removed
            conn.execute('INSERT INTO votes (user_id, snippet_id, vote_type) VALUES (?, ?, -1)', (user_id, id))
            new_vote_state = -1
        conn.commit() # Commit transaction

        # Recalculate counts AFTER changes
        counts = conn.execute('''
            SELECT
                SUM(CASE WHEN vote_type = 1 THEN 1 ELSE 0 END) as upvotes,
                SUM(CASE WHEN vote_type = -1 THEN 1 ELSE 0 END) as downvotes
            FROM votes WHERE snippet_id = ?
        ''', (id,)).fetchone()
        upvotes = counts['upvotes'] if counts else 0
        downvotes = counts['downvotes'] if counts else 0

        if is_ajax:
            return jsonify({'success': True, 'upvotes': upvotes, 'downvotes': downvotes, 'user_vote': new_vote_state})
        flash('Vote recorded!', 'success')
        return redirect(request.referrer or url_for('explore'))

    except sqlite3.Error as e:
        conn.rollback()
        app.logger.error(f"DB Error downvoting snippet {id} for user {user_id}: {e}")
        if is_ajax: return jsonify({'success': False, 'message': 'Database error occurred.'}), 500
        flash('Database error occurred.', 'error'); return redirect(request.referrer or url_for('explore'))

# --- Misc Routes ---
@app.route('/search_users')
def search_users():
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify({'users': []})

    conn = get_db()
    try:
        search_term = f'%{query}%'
        users = conn.execute('''
            SELECT u.username, u.profile_picture,
                   (SELECT COUNT(*) FROM snippets WHERE user_id = u.id AND is_private = 0) as snippet_count
            FROM users u
            WHERE u.username LIKE ?
            LIMIT 10 -- Limit results
        ''', (search_term,)).fetchall()

        return jsonify({
            'users': [
                {'username': user['username'], 'snippet_count': user['snippet_count'], 'profile_picture': user['profile_picture']}
                for user in users
            ]
        })
    except sqlite3.Error as e:
        app.logger.error(f"Database error in search_users for query '{query}': {e}")
        return jsonify({'users': [], 'error': 'Database search error'}), 500


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))

# --- Optional Rating Route (Consider removing if up/down votes suffice) ---
@app.route('/rate/<int:snippet_id>', methods=['POST'])
def rate_snippet(snippet_id):
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    data = request.get_json()
    rating = data.get('rating')

    if not isinstance(rating, int) or not (1 <= rating <= 5):
        return jsonify({'success': False, 'error': 'Invalid rating (must be 1-5)'}), 400

    conn = get_db()
    try:
        # Check if snippet exists and is accessible
        snippet = conn.execute('SELECT id FROM snippets WHERE id = ? AND (is_private = 0 OR user_id = ?)',
                              (snippet_id, user_id)).fetchone()
        if not snippet:
            return jsonify({'success': False, 'error': 'Snippet not found or not accessible'}), 404

        conn.execute('BEGIN')
        # Insert or update rating
        conn.execute('''
            INSERT OR REPLACE INTO ratings (snippet_id, user_id, rating)
            VALUES (?, ?, ?)
        ''', (snippet_id, user_id, rating))

        # Update aggregate columns in snippets table
        conn.execute('''
            UPDATE snippets
            SET rating_total = (SELECT SUM(rating) FROM ratings WHERE snippet_id = :sid),
                rating_count = (SELECT COUNT(*) FROM ratings WHERE snippet_id = :sid)
            WHERE id = :sid
        ''', {'sid': snippet_id})
        conn.commit()

        # Fetch updated average rating
        updated_snippet = conn.execute(
            'SELECT rating_total, rating_count FROM snippets WHERE id = ?', (snippet_id,)
        ).fetchone()

        new_avg_rating = 0
        rating_count = 0
        if updated_snippet and updated_snippet['rating_count'] > 0:
             rating_count = updated_snippet['rating_count']
             new_avg_rating = round(updated_snippet['rating_total'] / rating_count, 1)

        return jsonify({
            'success': True,
            'new_rating': new_avg_rating,
            'rating_count': rating_count
        })

    except sqlite3.Error as e:
        conn.rollback()
        app.logger.error(f"DB Error rating snippet {snippet_id} by user {user_id}: {e}")
        return jsonify({'success': False, 'error': 'Database error occurred'}), 500

# --- Main Execution ---
import os # Ensure os is imported if not already

# ... your Flask app setup (app = Flask(...), routes, etc.) ...

# --- Main Execution ---
if __name__ == '__main__':
    upload_folder = app.config.get('UPLOAD_FOLDER', 'static/uploads') # Get folder path safely
    # Ensure upload folder exists
    if not os.path.exists(upload_folder):
         try:
            os.makedirs(upload_folder)
            print(f"Created upload folder: {upload_folder}")
         except OSError as e:
            print(f"Error creating upload folder {upload_folder}: {e}")

    # Run the app, listening on all interfaces on port 1513
    # Set debug=False if you want to test closer to production (less error info)
    # Set debug=True for development features (like auto-reload)
    print("--- Starting Flask Development Server ---")
    print("Access locally: http://127.0.0.1:1513")
    print("Attempting to listen on all network interfaces...")
    print("(You might need to allow this through your firewall)")

    try:
        # Try running on 0.0.0.0
        app.run(host='0.0.0.0', port=1513, debug=True) # Keep debug=True for local testing/reloading
    except OSError as e:
         print(f"\nError starting server on 0.0.0.0: {e}")
         print("This might be a permissions issue or the port might be in use.")
         print("Falling back to localhost (127.0.0.1). Only accessible on this machine.")
         try:
             app.run(host='127.0.0.1', port=1513, debug=True)
         except Exception as inner_e:
             print(f"Could not start server even on localhost: {inner_e}")