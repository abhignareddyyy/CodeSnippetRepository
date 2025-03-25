from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import os
from database import init_db, migrate_db
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, Email

app = Flask(__name__)
app.secret_key = 'mykey1234'  # Change this to a secure secret key in production

# Configure upload folder
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure the upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Initialize and migrate database
init_db()
migrate_db()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Define Login Form
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    submit = SubmitField('Sign in')

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('profile'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        try:
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            
            if not username or len(username) < 3:
                if is_ajax:
                    return jsonify({"success": False, "message": "Username must be at least 3 characters long"})
                flash('Username must be at least 3 characters long', 'error')
                return render_template('register.html')
            
            if not email or '@' not in email:
                if is_ajax:
                    return jsonify({"success": False, "message": "Please enter a valid email address"})
                flash('Please enter a valid email address', 'error')
                return render_template('register.html')
                
            if not password or len(password) < 8:
                if is_ajax:
                    return jsonify({"success": False, "message": "Password must be at least 8 characters long"})
                flash('Password must be at least 8 characters long', 'error')
                return render_template('register.html')

            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            
            existing_user = c.execute(
                'SELECT id FROM users WHERE username = ? OR email = ?', 
                (username, email)
            ).fetchone()
            
            if existing_user:
                conn.close()
                if is_ajax:
                    return jsonify({"success": False, "message": "Username or email already exists!"})
                flash('Username or email already exists!', 'error')
                return render_template('register.html')
                
            c.execute(
                'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                (username, email, generate_password_hash(password))
            )
            conn.commit()
            conn.close()
            
            if is_ajax:
                return jsonify({"success": True, "message": "Registration successful!", "redirect": url_for('login')})
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
                
        except sqlite3.Error as e:
            print(f"Database error: {str(e)}")
            if is_ajax:
                return jsonify({"success": False, "message": "Database error occurred. Please try again."})
            flash('Database error occurred. Please try again.', 'error')
            return render_template('register.html')
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            if is_ajax:
                return jsonify({"success": False, "message": "An unexpected error occurred. Please try again."})
            flash('An unexpected error occurred. Please try again.', 'error')
            return render_template('register.html')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if request.method == 'POST' and form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        user = c.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user[3], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            
            if is_ajax:
                return jsonify({'success': True, 'message': 'Logged in successfully!', 'redirect': url_for('profile')})
            flash('Logged in successfully!', 'success')
            return redirect(url_for('profile'))
        else:
            if is_ajax:
                return jsonify({'success': False, 'message': 'Invalid username or password!'})
            flash('Invalid username or password!', 'error')
    
    if is_ajax and form.errors:
        errors = {field.name: field.errors for field in form if field.errors}
        return jsonify({'success': False, 'message': 'Validation failed', 'errors': errors})
    
    return render_template('login.html', form=form)

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('profile'))

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    user = c.execute('''
        SELECT u.id, u.username, u.email,
               (SELECT COUNT(*) FROM followers WHERE followed_id = u.id) as followers_count,
               (SELECT COUNT(*) FROM followers WHERE follower_id = u.id) as following_count,
               (SELECT COUNT(*) FROM snippets WHERE user_id = u.id) as snippets_count,
               u.created_at, u.profile_picture
        FROM users u 
        WHERE u.id = ?
    ''', (session['user_id'],)).fetchone()
    
    snippets = c.execute('''
        SELECT id, title, language, created_at,
               (SELECT COUNT(*) FROM votes WHERE snippet_id = snippets.id AND vote_type = 'up') as upvotes,
               (SELECT COUNT(*) FROM votes WHERE snippet_id = snippets.id AND vote_type = 'down') as downvotes,
               code, views
        FROM snippets 
        WHERE user_id = ? 
        ORDER BY created_at DESC
    ''', (session['user_id'],)).fetchall()
    
    snippet_views_map = {snippet[0]: snippet[7] for snippet in snippets}
    
    conn.close()
    
    if user is None:
        session.clear()
        return redirect(url_for('login'))
        
    return render_template('profile.html', 
                         user=user, 
                         snippets=snippets,
                         followers_count=user[3],
                         following_count=user[4],
                         snippet_count=user[5],
                         join_date=user[6],
                         profile_picture=user[7],
                         snippet_views_map=snippet_views_map)

@app.route('/upload_profile_picture', methods=['POST'])
def upload_profile_picture():
    if 'user_id' not in session:
        flash('Please login first.', 'error')
        return redirect(url_for('login'))
    
    if 'profile_picture' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('profile'))
    
    file = request.files['profile_picture']
    
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('profile'))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{session['user_id']}_{file.filename}")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('UPDATE users SET profile_picture = ? WHERE id = ?', 
                 (filename, session['user_id']))
        conn.commit()
        conn.close()
        
        flash('Profile picture updated successfully!', 'success')
        return redirect(url_for('profile'))
    
    flash('Invalid file type. Allowed types: png, jpg, jpeg, gif', 'error')
    return redirect(url_for('profile'))

#followers and following
@app.route('/get_followers')
def get_followers():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please login first'}), 401
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    followers = c.execute('''
        SELECT u.username, 
               (SELECT COUNT(*) FROM snippets WHERE user_id = u.id AND is_private = 0) as snippet_count,
               u.profile_picture
        FROM users u
        JOIN followers f ON u.id = f.follower_id
        WHERE f.followed_id = ?
    ''', (session['user_id'],)).fetchall()
    
    conn.close()
    
    return jsonify({
        'followers': [{'username': f[0], 'snippet_count': f[1], 'profile_picture': f[2]} for f in followers]
    })

@app.route('/get_following')
def get_following():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please login first'}), 401
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    following = c.execute('''
        SELECT u.username, 
               (SELECT COUNT(*) FROM snippets WHERE user_id = u.id AND is_private = 0) as snippet_count,
               u.profile_picture
        FROM users u
        JOIN followers f ON u.id = f.followed_id
        WHERE f.follower_id = ?
    ''', (session['user_id'],)).fetchall()
    
    conn.close()
    
    return jsonify({
        'following': [{'username': f[0], 'snippet_count': f[1], 'profile_picture': f[2]} for f in following]
    })

@app.route('/explore')
def explore():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    trending_topics = c.execute('''
        SELECT language, COUNT(*) as count
        FROM snippets
        WHERE is_private = 0 AND created_at >= datetime('now', '-30 days')
        GROUP BY language
        ORDER BY count DESC
        LIMIT 5
    ''').fetchall()
    
    topic_filter = request.args.get('topic', '')
    sort = request.args.get('sort', 'newest')
    
    base_query = '''
        SELECT snippets.id, snippets.title, snippets.language, snippets.description, 
               snippets.created_at, users.username,
               (SELECT COUNT(*) FROM votes WHERE snippet_id = snippets.id AND vote_type = 'up') as upvotes,
               (SELECT COUNT(*) FROM votes WHERE snippet_id = snippets.id AND vote_type = 'down') as downvotes,
               snippets.user_id
        FROM snippets 
        JOIN users ON snippets.user_id = users.id 
        WHERE snippets.is_private = 0
    '''
    params = []
    
    if topic_filter:
        base_query += ' AND snippets.language = ?'
        params.append(topic_filter)
    
    if sort == 'most-upvoted':
        base_query += ' ORDER BY upvotes DESC, created_at DESC'
    elif sort == 'trending':
        base_query += '''
            ORDER BY (
                SELECT COUNT(*) FROM votes v 
                WHERE v.snippet_id = snippets.id AND v.vote_type = 'up' 
                AND v.created_at >= datetime('now', '-7 days')
            ) DESC, created_at DESC
        '''
    else:
        base_query += ' ORDER BY snippets.created_at DESC'
    
    snippets = c.execute(base_query, params).fetchall()
    conn.close()
    
    return render_template('explore.html', snippets=snippets, trending_topics=trending_topics, sort=sort)

@app.route('/explore/snippet/<int:id>')
def view_snippet_explore(id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    snippet = c.execute("""
        SELECT s.id, s.title, s.code, s.language, s.description, 
               s.created_at, u.username, u.id as user_id
        FROM snippets s
        JOIN users u ON s.user_id = u.id
        WHERE s.id = ? AND s.is_private = 0
    """, (id,)).fetchone()
    
    if snippet is None:
        conn.close()
        flash('Snippet not found or is private', 'error')
        return redirect(url_for('explore'))
    
    comments = c.execute('''
        SELECT c.id, c.content, c.created_at, u.username, c.parent_id
        FROM comments c
        JOIN users u ON c.user_id = u.id
        WHERE c.snippet_id = ? AND c.parent_id IS NULL
        ORDER BY c.created_at DESC
    ''', (id,)).fetchall()
    
    comments_list = []
    for comment in comments:
        comment_dict = {
            'id': comment[0],
            'content': comment[1],
            'created_at': comment[2],
            'username': comment[3],
            'parent_id': comment[4],
            'replies': []
        }
        replies = c.execute('''
            SELECT c.id, c.content, c.created_at, u.username
            FROM comments c
            JOIN users u ON c.user_id = u.id
            WHERE c.parent_id = ?
            ORDER BY c.created_at ASC
        ''', (comment[0],)).fetchall()
        comment_dict['replies'] = [{'id': r[0], 'content': r[1], 'created_at': r[2], 'username': r[3]} for r in replies]
        comments_list.append(comment_dict)
    
    conn.close()
    
    return render_template('view_snippet_explore.html', 
                         snippet=snippet, 
                         comments=comments_list)

@app.route('/api/comments', methods=['POST'])
def create_comment():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Please login to comment'}), 401
        
    data = request.json
    
    if not data.get('content') or not data.get('snippet_id'):
        return jsonify({'success': False, 'error': 'Content and snippet ID are required'}), 400
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    try:
        snippet = c.execute('SELECT id FROM snippets WHERE id = ?', 
                          (data['snippet_id'],)).fetchone()
        if not snippet:
            conn.close()
            return jsonify({'success': False, 'error': 'Snippet not found'}), 404
            
        if data.get('parent_id'):
            parent = c.execute('SELECT id FROM comments WHERE id = ?', 
                             (data['parent_id'],)).fetchone()
            if not parent:
                conn.close()
                return jsonify({'success': False, 'error': 'Parent comment not found'}), 404
        
        c.execute('''
            INSERT INTO comments (snippet_id, user_id, parent_id, content)
            VALUES (?, ?, ?, ?)
        ''', (data['snippet_id'], session['user_id'], data.get('parent_id'), data['content']))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Comment posted successfully'})
    except sqlite3.Error as e:
        print(f"Database error: {str(e)}")
        conn.close()
        return jsonify({'success': False, 'error': 'Database error occurred'}), 500

@app.route('/user/<username>')
def user_profile(username):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    user = c.execute('''
        SELECT id, username, email 
        FROM users 
        WHERE username = ?
    ''', (username,)).fetchone()
    
    if user is None:
        conn.close()
        flash('User not found!', 'error')
        return redirect(url_for('explore'))
    
    stats = c.execute('''
        SELECT 
            (SELECT COUNT(*) FROM followers WHERE followed_id = ?) as followers_count,
            (SELECT COUNT(*) FROM followers WHERE follower_id = ?) as following_count,
            (SELECT COUNT(*) FROM snippets WHERE user_id = ?) as snippets_count,
            (SELECT COUNT(*) FROM votes v 
             JOIN snippets s ON v.snippet_id = s.id 
             WHERE s.user_id = ? AND v.vote_type = 'up') as total_upvotes
    ''', (user[0], user[0], user[0], user[0])).fetchone()
    
    is_following = False
    if 'user_id' in session:
        is_following = c.execute('''
            SELECT EXISTS(
                SELECT 1 FROM followers 
                WHERE follower_id = ? AND followed_id = ?
            )
        ''', (session['user_id'], user[0])).fetchone()[0]
    
    snippets = c.execute('''
        SELECT s.id, s.title, s.language, s.created_at,
               (SELECT COUNT(*) FROM votes WHERE snippet_id = s.id AND vote_type = 'up') as upvotes,
               (SELECT COUNT(*) FROM votes WHERE snippet_id = s.id AND vote_type = 'down') as downvotes
        FROM snippets s
        WHERE s.user_id = ? AND s.is_private = 0
        ORDER BY s.created_at DESC
    ''', (user[0],)).fetchall()
    
    conn.close()
    
    return render_template('user_profile.html', 
                         user=user,
                         snippets=snippets,
                         stats=stats,
                         is_following=is_following)

@app.route('/snippet/new', methods=['GET', 'POST'])
def new_snippet():
    if 'user_id' not in session:
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
        
        if not title or not code or not language:
            if is_ajax:
                return jsonify({'success': False, 'message': 'Title, code, and language are required.'}), 400
            flash('Title, code, and language are required.', 'error')
            return render_template('new_snippet.html')
        
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('''
            INSERT INTO snippets (user_id, title, code, language, description)
            VALUES (?, ?, ?, ?, ?)
        ''', (session['user_id'], title, code.strip(), language, description))
        snippet_id = c.lastrowid
        conn.commit()
        conn.close()
        
        if is_ajax:
            return jsonify({
                'success': True, 
                'message': 'Snippet created successfully!',
                'redirect': url_for('view_snippet', id=snippet_id, _external=True)
            }), 201
        
        flash('Snippet created successfully!', 'success')
        return redirect(url_for('profile'))
    
    return render_template('new_snippet.html')

@app.route('/search_users')
def search_users():
    query = request.args.get('query', '').strip()
    
    if not query:
        return jsonify({'users': []})
    
    try:
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        
        search_query = f'%{query}%'
        users = c.execute('''
            SELECT u.username, 
                   (SELECT COUNT(*) FROM snippets WHERE user_id = u.id AND is_private = 0) as snippet_count
            FROM users u 
            WHERE u.username LIKE ? 
            LIMIT 5
        ''', (search_query,)).fetchall()
        
        conn.close()
        
        return jsonify({
            'users': [
                {'username': user[0], 'snippet_count': user[1]} 
                for user in users
            ]
        })
    except sqlite3.Error as e:
        print(f"Database error in search_users: {e}")
        return jsonify({'users': []}), 500

@app.route('/follow/<username>', methods=['POST'])
def follow_user(username):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please login first'}), 401

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    target_user = c.execute('SELECT id FROM users WHERE username = ?', 
                          (username,)).fetchone()
    
    if not target_user:
        conn.close()
        return jsonify({'success': False, 'message': 'User not found'}), 404
        
    if target_user[0] == session['user_id']:
        conn.close()
        return jsonify({'success': False, 'message': 'Cannot follow yourself'}), 400
    
    try:
        c.execute('''
            INSERT INTO followers (follower_id, followed_id)
            VALUES (?, ?)
        ''', (session['user_id'], target_user[0]))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': f'Now following {username}'})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'success': False, 'message': 'Already following'}), 400

@app.route('/unfollow/<username>', methods=['POST'])
def unfollow_user(username):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please login first'}), 401

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    target_user = c.execute('SELECT id FROM users WHERE username = ?', 
                          (username,)).fetchone()
    
    if not target_user:
        conn.close()
        return jsonify({'success': False, 'message': 'User not found'}), 404
    
    c.execute('''
        DELETE FROM followers 
        WHERE follower_id = ? AND followed_id = ?
    ''', (session['user_id'], target_user[0]))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': f'Unfollowed {username}'})

@app.route('/snippet/<int:id>')
def view_snippet(id):
    if 'user_id' not in session:
        flash('Please login first.', 'error')
        return redirect(url_for('login'))
        
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    c.execute('UPDATE snippets SET views = views + 1 WHERE id = ?', (id,))
    
    snippet = c.execute('''
        SELECT snippets.id, snippets.title, snippets.code, snippets.language, 
               snippets.description, snippets.created_at, users.username,
               snippets.user_id
        FROM snippets 
        JOIN users ON snippets.user_id = users.id 
        WHERE snippets.id = ?
    ''', (id,)).fetchone()
    
    conn.commit()
    conn.close()
    
    if snippet is None:
        flash('Snippet not found!', 'error')
        return redirect(url_for('explore'))
        
    return render_template('view_snippet.html', snippet=snippet)

@app.route('/snippet/edit/<int:id>', methods=['GET', 'POST'])
def edit_snippet(id):
    if 'user_id' not in session:
        flash('Please login first.', 'error')
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    snippet = c.execute('''
        SELECT id, title, code, language, description, is_private 
        FROM snippets 
        WHERE id = ? AND user_id = ?
    ''', (id, session['user_id'])).fetchone()
    
    if not snippet:
        conn.close()
        flash('Snippet not found or unauthorized.', 'error')
        return redirect(url_for('profile'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        code = request.form.get('code')
        language = request.form.get('language')
        description = request.form.get('description')
        is_private = bool(request.form.get('is_private'))
        
        c.execute('''
            UPDATE snippets 
            SET title = ?, code = ?, language = ?, description = ?, is_private = ?
            WHERE id = ? AND user_id = ?
        ''', (title, code, language, description, is_private, id, session['user_id']))
        
        conn.commit()
        conn.close()
        flash('Snippet updated successfully!', 'success')
        return redirect(url_for('view_snippet', id=id))
    
    conn.close()
    return render_template('edit_snippet.html', snippet=snippet)

@app.route('/snippet/<int:id>/delete', methods=['POST'])
def delete_snippet(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('DELETE FROM snippets WHERE id = ? AND user_id = ?', 
             (id, session['user_id']))
    conn.commit()
    conn.close()
    
    flash('Snippet deleted successfully!', 'success')
    return redirect(url_for('profile'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))

@app.route('/rate/<int:snippet_id>', methods=['POST'])
def rate_snippet(snippet_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    data = request.get_json()
    rating = data.get('rating')
    
    if not rating or not (1 <= rating <= 5):
        return jsonify({'success': False, 'error': 'Invalid rating'}), 400
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    try:
        c.execute('''
            INSERT OR REPLACE INTO ratings (snippet_id, user_id, rating)
            VALUES (?, ?, ?)
        ''', (snippet_id, session['user_id'], rating))
        
        c.execute('''
            UPDATE snippets 
            SET rating_total = (
                SELECT SUM(rating) FROM ratings WHERE snippet_id = ?
            ),
            rating_count = (
                SELECT COUNT(*) FROM ratings WHERE snippet_id = ?
            )
            WHERE id = ?
        ''', (snippet_id, snippet_id, snippet_id))
        
        conn.commit()
        
        snippet = c.execute('''
            SELECT rating_total, rating_count 
            FROM snippets 
            WHERE id = ?
        ''', (snippet_id,)).fetchone()
        
        new_rating = round(snippet[0] / snippet[1], 1) if snippet[1] > 0 else 0
        
        conn.close()
        return jsonify({
            'success': True, 
            'new_rating': new_rating,
            'rating_count': snippet[1]
        })
    except sqlite3.Error as e:
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/upvote_snippet/<int:id>', methods=['POST'])
def upvote_snippet(id):
    if 'user_id' not in session:
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if is_ajax:
            return jsonify({'success': False, 'message': 'Please login to vote'}), 401
        flash('Please login to vote.', 'error')
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    existing_vote = c.execute('''
        SELECT vote_type FROM votes 
        WHERE user_id = ? AND snippet_id = ?
    ''', (session['user_id'], id)).fetchone()
    
    if existing_vote:
        if existing_vote[0] == 'up':
            c.execute('DELETE FROM votes WHERE user_id = ? AND snippet_id = ?',
                     (session['user_id'], id))
        else:
            c.execute('''
                UPDATE votes 
                SET vote_type = 'up' 
                WHERE user_id = ? AND snippet_id = ?
            ''', (session['user_id'], id))
    else:
        c.execute('''
            INSERT INTO votes (user_id, snippet_id, vote_type)
            VALUES (?, ?, 'up')
        ''', (session['user_id'], id))
    
    upvotes = c.execute('SELECT COUNT(*) FROM votes WHERE snippet_id = ? AND vote_type = "up"', (id,)).fetchone()[0]
    conn.commit()
    conn.close()
    
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if is_ajax:
        return jsonify({'success': True, 'upvotes': upvotes})
    return redirect(request.referrer or url_for('explore'))

@app.route('/downvote_snippet/<int:id>', methods=['POST'])
def downvote_snippet(id):
    if 'user_id' not in session:
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if is_ajax:
            return jsonify({'success': False, 'message': 'Please login to vote'}), 401
        flash('Please login to vote.', 'error')
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    existing_vote = c.execute('''
        SELECT vote_type FROM votes 
        WHERE user_id = ? AND snippet_id = ?
    ''', (session['user_id'], id)).fetchone()
    
    if existing_vote:
        if existing_vote[0] == 'down':
            c.execute('DELETE FROM votes WHERE user_id = ? AND snippet_id = ?',
                     (session['user_id'], id))
        else:
            c.execute('''
                UPDATE votes 
                SET vote_type = 'down' 
                WHERE user_id = ? AND snippet_id = ?
            ''', (session['user_id'], id))
    else:
        c.execute('''
            INSERT INTO votes (user_id, snippet_id, vote_type)
            VALUES (?, ?, 'down')
        ''', (session['user_id'], id))
    
    downvotes = c.execute('SELECT COUNT(*) FROM votes WHERE snippet_id = ? AND vote_type = "down"', (id,)).fetchone()[0]
    conn.commit()
    conn.close()
    
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if is_ajax:
        return jsonify({'success': True, 'downvotes': downvotes})
    return redirect(request.referrer or url_for('explore'))

if __name__ == '__main__':
    app.run(debug=True, port=5001)