from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from database import init_db
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, Email

app = Flask(__name__)
app.secret_key = 'mykey1234'  # Change this to a secure secret key

# Initialize database
init_db()

# Define Login Form
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    submit = SubmitField('Sign in')  # Matches your template's button text

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('profile'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Check if it's an AJAX request
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        try:
            # Get form data with validation
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            
            # Add input validation
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
            
            try:
                # Check if username or email already exists
                existing_user = c.execute(
                    'SELECT id FROM users WHERE username = ? OR email = ?', 
                    (username, email)
                ).fetchone()
                
                if existing_user:
                    if is_ajax:
                        return jsonify({"success": False, "message": "Username or email already exists!"})
                    flash('Username or email already exists!', 'error')
                    return render_template('register.html')
                
                # Insert new user
                c.execute(
                    'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                    (username, email, generate_password_hash(password))
                )
                conn.commit()
                
                if is_ajax:
                    return jsonify({"success": True, "message": "Registration successful!", "redirect": url_for('login')})
                flash('Registration successful! Please login.', 'success')
                return redirect(url_for('login'))
                
            except sqlite3.Error as e:
                print(f"Database error: {str(e)}")  # Log the error
                if is_ajax:
                    return jsonify({"success": False, "message": "Database error occurred. Please try again."})
                flash('Database error occurred. Please try again.', 'error')
                return render_template('register.html')
            finally:
                conn.close()
                
        except Exception as e:
            print(f"Unexpected error: {str(e)}")  # Log the error
            if is_ajax:
                return jsonify({"success": False, "message": "An unexpected error occurred. Please try again."})
            flash('An unexpected error occurred. Please try again.', 'error')
            return render_template('register.html')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if request.method == 'POST':
        if form.validate_on_submit():  # Validates form data including CSRF
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
        else:
            if is_ajax:
                # Return validation errors as JSON
                errors = {field.name: field.errors for field in form if field.errors}
                return jsonify({'success': False, 'message': 'Validation failed', 'errors': errors})
            # For non-AJAX, errors will be shown in the template via form.errors
    
    return render_template('login.html', form=form)

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('profile'))  # Or your actual dashboard implementation

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Get user info and counts
    user = c.execute('''
        SELECT u.id, u.username, u.email,
               (SELECT COUNT(*) FROM followers WHERE followed_id = u.id) as followers_count,
               (SELECT COUNT(*) FROM followers WHERE follower_id = u.id) as following_count,
               (SELECT COUNT(*) FROM snippets WHERE user_id = u.id) as snippets_count
        FROM users u 
        WHERE u.id = ?
    ''', (session['user_id'],)).fetchone()
    
    # Get user's snippets
    snippets = c.execute('''
        SELECT id, title, language, created_at,
               (SELECT COUNT(*) FROM votes WHERE snippet_id = snippets.id AND vote_type = 'up') as upvotes,
               (SELECT COUNT(*) FROM votes WHERE snippet_id = snippets.id AND vote_type = 'down') as downvotes
        FROM snippets 
        WHERE user_id = ? 
        ORDER BY created_at DESC
    ''', (session['user_id'],)).fetchall()
    
    conn.close()
    
    if user is None:
        session.clear()
        return redirect(url_for('login'))
        
    return render_template('profile.html', 
                         user=user, 
                         snippets=snippets,
                         followers_count=user[3],
                         following_count=user[4],
                         snippet_count=user[5])

@app.route('/explore')
def explore():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Get snippets with user info and votes
    snippets = c.execute('''
        SELECT snippets.id, snippets.title, snippets.language, snippets.description, 
               snippets.created_at, users.username,
               (SELECT COUNT(*) FROM votes WHERE snippet_id = snippets.id AND vote_type = 'up') as upvotes,
               (SELECT COUNT(*) FROM votes WHERE snippet_id = snippets.id AND vote_type = 'down') as downvotes
        FROM snippets 
        JOIN users ON snippets.user_id = users.id 
        ORDER BY snippets.created_at DESC
    ''').fetchall()
    
    conn.close()
    return render_template('explore.html', snippets=snippets)

@app.route('/explore/snippet/<int:id>')
def view_snippet_explore(id):
    """Route for viewing snippets from explore page"""
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Query to get snippet details including username and timestamps
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
    
    # Get comments with replies
    comments = c.execute('''
        SELECT c.id, c.content, c.created_at, u.username, c.parent_id
        FROM comments c
        JOIN users u ON c.user_id = u.id
        WHERE c.snippet_id = ? AND c.parent_id IS NULL
        ORDER BY c.created_at DESC
    ''', (id,)).fetchall()
    
    # Convert comments to list of dicts and get replies
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
    
    # Validate required fields
    if not data.get('content'):
        return jsonify({'success': False, 'error': 'Comment content is required'}), 400
    if not data.get('snippet_id'):
        return jsonify({'success': False, 'error': 'Snippet ID is required'}), 400
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    try:
        # Verify snippet exists
        snippet = c.execute('SELECT id FROM snippets WHERE id = ?', 
                          (data['snippet_id'],)).fetchone()
        if not snippet:
            return jsonify({'success': False, 'error': 'Snippet not found'}), 404
            
        # If it's a reply, verify parent comment exists
        if data.get('parent_id'):
            parent = c.execute('SELECT id FROM comments WHERE id = ?', 
                             (data['parent_id'],)).fetchone()
            if not parent:
                return jsonify({'success': False, 'error': 'Parent comment not found'}), 404
        
        c.execute('''
            INSERT INTO comments (snippet_id, user_id, parent_id, content)
            VALUES (?, ?, ?, ?)
        ''', (data['snippet_id'], session['user_id'], data.get('parent_id'), data['content']))
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Comment posted successfully'})
    except sqlite3.Error as e:
        print(f"Database error: {str(e)}")  # Log the error
        return jsonify({'success': False, 'error': 'Database error occurred'}), 500
    except Exception as e:
        print(f"Unexpected error: {str(e)}")  # Log the error
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500
    finally:
        conn.close()

@app.route('/user/<username>')
def user_profile(username):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Get user info
    user = c.execute('''
        SELECT id, username, email 
        FROM users 
        WHERE username = ?
    ''', (username,)).fetchone()
    
    if user is None:
        flash('User not found!', 'error')
        return redirect(url_for('explore'))
    
    # Get followers and following counts
    stats = c.execute('''
        SELECT 
            (SELECT COUNT(*) FROM followers WHERE followed_id = ?) as followers_count,
            (SELECT COUNT(*) FROM followers WHERE follower_id = ?) as following_count,
            (SELECT COUNT(*) FROM snippets WHERE user_id = ?) as snippets_count,
            (SELECT COUNT(*) FROM votes v 
             JOIN snippets s ON v.snippet_id = s.id 
             WHERE s.user_id = ? AND v.vote_type = 'up') as total_upvotes
    ''', (user[0], user[0], user[0], user[0])).fetchone()
    
    # Check if current user is following this user
    is_following = False
    if 'user_id' in session:
        is_following = c.execute('''
            SELECT EXISTS(
                SELECT 1 FROM followers 
                WHERE follower_id = ? AND followed_id = ?
            )
        ''', (session['user_id'], user[0])).fetchone()[0]
    
    # Get user's public snippets
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
        
        try:
            # Get form data with validation
            title = request.form.get('title')
            code = request.form.get('code')
            language = request.form.get('language')
            description = request.form.get('description', '')  # Default to empty string if missing
            
            # Validate required fields
            if not title:
                if is_ajax:
                    return jsonify({'success': False, 'message': 'Title is required.'}), 400
                flash('Title is required.', 'error')
                return render_template('new_snippet.html')
            
            if not code:
                if is_ajax:
                    return jsonify({'success': False, 'message': 'Code is required.'}), 400
                flash('Code is required.', 'error')
                return render_template('new_snippet.html')
            
            if not language:
                if is_ajax:
                    return jsonify({'success': False, 'message': 'Language is required.'}), 400
                flash('Language is required.', 'error')
                return render_template('new_snippet.html')

            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute('''
                INSERT INTO snippets (user_id, title, code, language, description)
                VALUES (?, ?, ?, ?, ?)
            ''', (session['user_id'], title, code.strip(), language, description))
            snippet_id = c.lastrowid  # Get the ID of the newly created snippet
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
            
        except sqlite3.Error as e:
            print(f"Database error: {str(e)}")  # Log the error
            if is_ajax:
                return jsonify({'success': False, 'message': f'Database error: {str(e)}'}), 500
            flash('An error occurred while saving your snippet.', 'error')
            return render_template('new_snippet.html')
        except Exception as e:
            print(f"Unexpected error: {str(e)}")  # Log the error
            if is_ajax:
                return jsonify({'success': False, 'message': 'An unexpected error occurred. Please try again.'}), 500
            flash('An unexpected error occurred. Please try again.', 'error')
            return render_template('new_snippet.html')
        
    return render_template('new_snippet.html')

@app.route('/search_users')
def search_users():
    query = request.args.get('query', '')
    # Removed redundant length check since frontend handles it
    
    try:
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        
        # Search for users with matching usernames
        search_query = f'%{query}%'
        users = c.execute('''
            SELECT u.username, 
                   (SELECT COUNT(*) FROM snippets WHERE user_id = u.id) as snippet_count
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
    except Exception as e:
        print(f"Unexpected error in search_users: {e}")
        return jsonify({'users': []}), 500

@app.route('/follow/<username>', methods=['POST'])
def follow_user(username):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please login first'}), 401

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Get target user
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
    
    snippet = c.execute('''
        SELECT snippets.id, snippets.title, snippets.code, snippets.language, 
               snippets.description, snippets.created_at, users.username,
               snippets.user_id
        FROM snippets 
        JOIN users ON snippets.user_id = users.id 
        WHERE snippets.id = ?
    ''', (id,)).fetchone()
    
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
    
    # Check if snippet exists and belongs to user
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
        return jsonify({'success': False, 'error': 'Not logged in'})
    
    data = request.get_json()
    rating = data.get('rating')
    
    if not rating or not (1 <= rating <= 5):
        return jsonify({'success': False, 'error': 'Invalid rating'})
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    try:
        # Try to update existing rating
        c.execute('''
            INSERT OR REPLACE INTO ratings (snippet_id, user_id, rating)
            VALUES (?, ?, ?)
        ''', (snippet_id, session['user_id'], rating))
        
        # Update snippet's rating counts
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
        
        # Get new rating average
        snippet = c.execute('''
            SELECT rating_total, rating_count 
            FROM snippets 
            WHERE id = ?
        ''', (snippet_id,)).fetchone()
        
        new_rating = round(snippet[0] / snippet[1], 1) if snippet[1] > 0 else 0
        
        return jsonify({
            'success': True, 
            'new_rating': new_rating,
            'rating_count': snippet[1]
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/upvote/<int:id>', methods=['POST'])
def upvote_snippet(id):
    if 'user_id' not in session:
        flash('Please login to vote.', 'error')
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Check if user has already voted
    existing_vote = c.execute('''
        SELECT vote_type FROM votes 
        WHERE user_id = ? AND snippet_id = ?
    ''', (session['user_id'], id)).fetchone()
    
    if existing_vote:
        if existing_vote[0] == 'up':
            # Remove vote if already upvoted
            c.execute('DELETE FROM votes WHERE user_id = ? AND snippet_id = ?',
                     (session['user_id'], id))
        else:
            # Change downvote to upvote
            c.execute('''
                UPDATE votes 
                SET vote_type = 'up' 
                WHERE user_id = ? AND snippet_id = ?
            ''', (session['user_id'], id))
    else:
        # Add new upvote
        c.execute('''
            INSERT INTO votes (user_id, snippet_id, vote_type)
            VALUES (?, ?, 'up')
        ''', (session['user_id'], id))
    
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('explore'))

@app.route('/downvote/<int:id>', methods=['POST'])
def downvote_snippet(id):
    if 'user_id' not in session:
        flash('Please login to vote.', 'error')
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Check if user has already voted
    existing_vote = c.execute('''
        SELECT vote_type FROM votes 
        WHERE user_id = ? AND snippet_id = ?
    ''', (session['user_id'], id)).fetchone()
    
    if existing_vote:
        if existing_vote[0] == 'down':
            # Remove vote if already downvoted
            c.execute('DELETE FROM votes WHERE user_id = ? AND snippet_id = ?',
                     (session['user_id'], id))
        else:
            # Change upvote to downvote
            c.execute('''
                UPDATE votes 
                SET vote_type = 'down' 
                WHERE user_id = ? AND snippet_id = ?
            ''', (session['user_id'], id))
    else:
        # Add new downvote
        c.execute('''
            INSERT INTO votes (user_id, snippet_id, vote_type)
            VALUES (?, ?, 'down')
        ''', (session['user_id'], id))
    
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('explore'))

if __name__ == '__main__':
    app.run(debug=True)