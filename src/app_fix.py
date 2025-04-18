from flask import Flask, request, redirect, url_for, session, render_template_string, flash
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user, current_user
from datetime import datetime, timedelta
import requests
import os
import json
from dotenv import load_dotenv
from supabase import create_client
from cryptography.fernet import Fernet
import base64
import uuid

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY')

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'index'

# Initialize Supabase client
supabase = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_KEY')
)

# Initialize Fernet encryption
fernet_key = os.getenv('FERNET_KEY')
if not fernet_key:
    # Generate a new key if not provided
    fernet_key = Fernet.generate_key().decode()
    print(f"Generated new Fernet key: {fernet_key}")
    print("Add this to your .env file as FERNET_KEY")
cipher_suite = Fernet(fernet_key.encode() if isinstance(fernet_key, str) else fernet_key)

# Oura OAuth2 configuration
OURA_CLIENT_ID = os.getenv('OURA_CLIENT_ID')
OURA_CLIENT_SECRET = os.getenv('OURA_CLIENT_SECRET')
OURA_REDIRECT_URI = os.getenv('OURA_REDIRECT_URI', 'http://localhost:5000/callback')
OURA_AUTH_URL = 'https://cloud.ouraring.com/oauth/authorize'
OURA_TOKEN_URL = 'https://api.ouraring.com/oauth/token'

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, profile_data=None):
        self.id = id
        self.profile_data = profile_data

@login_manager.user_loader
def load_user(user_id):
    try:
        profile = supabase.table('profiles').select('*').eq('id', user_id).execute()
        if profile.data:
            return User(user_id, profile.data[0])
        return None
    except Exception as e:
        print(f"Error loading user: {str(e)}")
        return None

def encrypt_token(token):
    """Encrypt token using Fernet."""
    return cipher_suite.encrypt(json.dumps(token).encode()).decode()

def decrypt_token(encrypted_token):
    """Decrypt token using Fernet."""
    try:
        return json.loads(cipher_suite.decrypt(encrypted_token.encode()).decode())
    except Exception as e:
        print(f"Error decrypting token: {str(e)}")
        return None

@app.route('/')
def index():
    """Redirect to Oura OAuth2 login."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    auth_url = f"{OURA_AUTH_URL}?client_id={OURA_CLIENT_ID}&redirect_uri={OURA_REDIRECT_URI}&response_type=code&scope=daily"
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Oura Ring Data Comparison</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 0;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                background-color: #f5f5f5;
            }
            .login-container {
                background: white;
                border-radius: 8px;
                padding: 40px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                text-align: center;
                max-width: 500px;
            }
            h1 {
                margin-top: 0;
                color: #333;
            }
            p {
                color: #666;
                margin-bottom: 30px;
            }
            .login-button {
                background-color: #6200EA;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 4px;
                font-size: 16px;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
                transition: background-color 0.3s;
            }
            .login-button:hover {
                background-color: #5000D6;
            }
        </style>
    </head>
    <body>
        <div class="login-container">
            <h1>Oura Ring Data Comparison</h1>
            <p>Compare your sleep and readiness metrics with other users. Connect your Oura Ring to get started.</p>
            <a href="{{ auth_url }}" class="login-button">Connect Oura Ring</a>
        </div>
    </body>
    </html>
    ''', auth_url=auth_url)

@app.route('/callback')
def callback():
    """Handle Oura OAuth2 callback."""
    code = request.args.get('code')
    if not code:
        return "Authorization failed", 400

    # Exchange code for access token
    token_response = requests.post(
        OURA_TOKEN_URL,
        data={
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': OURA_REDIRECT_URI,
            'client_id': OURA_CLIENT_ID,
            'client_secret': OURA_CLIENT_SECRET
        }
    )
    
    if token_response.status_code != 200:
        return f"Token exchange failed: {token_response.text}", 400

    tokens = token_response.json()
    
    # Get user info from Oura
    user_info_response = requests.get(
        'https://api.ouraring.com/v2/usercollection/personal_info',
        headers={'Authorization': f"Bearer {tokens['access_token']}"}
    )
    
    if user_info_response.status_code != 200:
        return f"Failed to get user info: {user_info_response.text}", 400

    user_info = user_info_response.json()

    # Generate display name from email
    email = user_info.get('email')
    display_name = email.split('@')[0] if email else f"User_{datetime.now().strftime('%y%m%d%H%M%S')}"

    # Check if profile exists
    try:
        existing_profile = supabase.table('profiles').select('*').eq('oura_user_id', user_info.get('id')).execute()

        # Encrypt tokens for storage
        encrypted_tokens = encrypt_token(tokens)
        profile_id = None

        if existing_profile.data:
            # Update existing profile
            profile_id = existing_profile.data[0]['id']
            try:
                supabase.table('profiles').update({
                    'email': email,
                    'display_name': display_name,
                    'oura_tokens': encrypted_tokens,
                    'last_login': datetime.now().isoformat()
                }).eq('id', profile_id).execute()
            except Exception as e:
                print(f"Error updating profile: {str(e)}")
                # Try updating without last_login if it causes issues
                supabase.table('profiles').update({
                    'email': email,
                    'display_name': display_name,
                    'oura_tokens': encrypted_tokens
                }).eq('id', profile_id).execute()
        else:
            # Create new profile
            new_profile_id = str(uuid.uuid4())
            try:
                profile_result = supabase.table('profiles').insert({
                    'id': new_profile_id,
                    'oura_user_id': user_info.get('id'),
                    'email': email,
                    'display_name': display_name,
                    'oura_tokens': encrypted_tokens,
                    'last_login': datetime.now().isoformat()
                }).execute()
                profile_id = profile_result.data[0]['id']
            except Exception as e:
                print(f"Error creating profile with last_login: {str(e)}")
                # Try creating without last_login if it causes issues
                profile_result = supabase.table('profiles').insert({
                    'id': new_profile_id,
                    'oura_user_id': user_info.get('id'),
                    'email': email,
                    'display_name': display_name,
                    'oura_tokens': encrypted_tokens
                }).execute()
                profile_id = profile_result.data[0]['id']

        # Login user
        if profile_id:
            profile_data = supabase.table('profiles').select('*').eq('id', profile_id).execute().data[0]
            user = User(profile_id, profile_data)
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            return "Failed to create or update profile", 500

    except Exception as e:
        print(f"Error in callback: {str(e)}")
        return f"An error occurred: {str(e)}", 500

@app.route('/dashboard')
@login_required
def dashboard():
    """Display user's Oura Ring data and global leaderboard."""
    try:
        # Get user's profile
        profile = supabase.table('profiles').select('*').eq('id', current_user.id).execute()
        if not profile.data:
            logout_user()
            return redirect(url_for('index'))
        
        # Decrypt tokens
        tokens = decrypt_token(profile.data[0]['oura_tokens'])
        if not tokens:
            logout_user()
            return redirect(url_for('index'))
        
        # Get personal info from Oura
        personal_info_response = requests.get(
            'https://api.ouraring.com/v2/usercollection/personal_info',
            headers={'Authorization': f"Bearer {tokens['access_token']}"}
        )
        personal_info = personal_info_response.json()

        # Get sleep data from Oura (last 7 days)
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        sleep_response = requests.get(
            'https://api.ouraring.com/v2/usercollection/daily_sleep',
            headers={'Authorization': f"Bearer {tokens['access_token']}"},
            params={'start_date': start_date}
        )
        sleep_data = sleep_response.json()
        
        # Get readiness data from Oura (last 7 days)
        readiness_response = requests.get(
            'https://api.ouraring.com/v2/usercollection/daily_readiness',
            headers={'Authorization': f"Bearer {tokens['access_token']}"},
            params={'start_date': start_date}
        )
        readiness_data = readiness_response.json()
        
        # Process sleep data to calculate average
        sleep_scores = [day.get('sleep_score') for day in sleep_data.get('data', []) if day.get('sleep_score')]
        avg_sleep_score = sum(sleep_scores) / len(sleep_scores) if sleep_scores else 0
        
        # Update profile with average sleep score (try without last_login)
        try:
            supabase.table('profiles').update({
                'avg_sleep_score': avg_sleep_score,
                'last_sleep_score': sleep_scores[0] if sleep_scores else None
            }).eq('id', current_user.id).execute()
        except Exception as e:
            print(f"Error updating sleep scores: {str(e)}")
        
        # Get all users for the leaderboard
        all_users = supabase.table('profiles').select('*').execute()
        
        # Sort users by average sleep score
        leaderboard = sorted(
            all_users.data, 
            key=lambda x: x.get('avg_sleep_score', 0) or 0, 
            reverse=True
        )
        
        # Get user's friends (if available)
        try:
            friends = supabase.table('friendships')\
                .select('*, friend:profiles!friendships_friend_id_fkey(*)')\
                .eq('user_id', current_user.id)\
                .execute()
        except Exception as e:
            print(f"Error fetching friends: {str(e)}")
            friends = {"data": []}

        return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Oura Ring Dashboard</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .data-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .score {
            font-size: 24px;
            font-weight: bold;
        }
        .sleep-score {
            color: #4CAF50;
        }
        .readiness-score {
            color: #2196F3;
        }
        .progress-bar {
            background: #e0e0e0;
            height: 10px;
            border-radius: 5px;
            margin-top: 10px;
        }
        .progress {
            height: 100%;
            border-radius: 5px;
            width: 0%;
            transition: width 0.3s ease;
        }
        .sleep-progress {
            background: #4CAF50;
        }
        .readiness-progress {
            background: #2196F3;
        }
        .leaderboard {
            margin-top: 30px;
        }
        .leaderboard-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        .leaderboard-table th,
        .leaderboard-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        .leaderboard-table th {
            background-color: #f8f9fa;
        }
        .current-user {
            background-color: #e3f2fd;
        }
        .logout {
            float: right;
            color: #666;
            text-decoration: none;
        }
        .logout:hover {
            color: #333;
        }
        .tab-container {
            margin-bottom: 20px;
        }
        .tab {
            display: inline-block;
            padding: 10px 20px;
            cursor: pointer;
            background-color: #ddd;
            border-radius: 5px 5px 0 0;
            margin-right: 5px;
        }
        .tab.active {
            background-color: white;
            border-bottom: 2px solid #6200EA;
        }
        .tab-content {
            display: none;
        }
        .tab-content.active {
            display: block;
        }
        .friend-form {
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid #eee;
        }
        .btn {
            background-color: #6200EA;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
        }
        .btn:hover {
            background-color: #5000D6;
        }
    </style>
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            // Initialize progress bars
            document.querySelectorAll('.progress').forEach(function(el) {
                setTimeout(function() {
                    el.style.width = el.getAttribute('data-width') + '%';
                }, 100);
            });
            
            // Tab functionality
            document.querySelectorAll('.tab').forEach(function(tab) {
                tab.addEventListener('click', function() {
                    // Remove active class from all tabs
                    document.querySelectorAll('.tab').forEach(function(t) {
                        t.classList.remove('active');
                    });
                    // Add active class to clicked tab
                    this.classList.add('active');
                    
                    // Hide all tab content
                    document.querySelectorAll('.tab-content').forEach(function(content) {
                        content.classList.remove('active');
                    });
                    // Show corresponding content
                    document.getElementById(this.getAttribute('data-tab')).classList.add('active');
                });
            });
        });
    </script>
</head>
<body>
    <div class="card">
        <a href="{{ url_for('logout') }}" class="logout">Logout</a>
        <h1>Your Oura Ring Dashboard</h1>
        <p>Welcome, {{ profile.data[0].display_name }}!</p>
    </div>
    
    <div class="tab-container">
        <div class="tab active" data-tab="sleep-tab">Sleep Data</div>
        <div class="tab" data-tab="readiness-tab">Readiness Data</div>
        <div class="tab" data-tab="leaderboard-tab">Leaderboard</div>
        <div class="tab" data-tab="friends-tab">Friends</div>
    </div>
    
    <div id="sleep-tab" class="tab-content active">
        <div class="card">
            <h2>Your Sleep Scores (Last 7 Days)</h2>
            <p>Average Sleep Score: <span class="score sleep-score">{{ "%.1f"|format(profile.data[0].get('avg_sleep_score', 0) or 0) }}</span></p>
            <div class="data-grid">
                {% for day in sleep_data.get('data', []) %}
                <div class="card">
                    <h3>{{ day.get('day', 'Unknown Date') }}</h3>
                    <div class="score sleep-score">{{ day.get('sleep_score', 'N/A') }}</div>
                    <div class="progress-bar">
                        <div class="progress sleep-progress" data-width="{{ day.get('sleep_score', 0) }}" style="width: 0%"></div>
                    </div>
                    <p>Total Sleep: {{ day.get('total_sleep_duration', 0) // 60 }} hours {{ day.get('total_sleep_duration', 0) % 60 }} minutes</p>
                </div>
                {% endfor %}
            </div>
        </div>
    </div>
    
    <div id="readiness-tab" class="tab-content">
        <div class="card">
            <h2>Your Readiness Scores (Last 7 Days)</h2>
            <div class="data-grid">
                {% for day in readiness_data.get('data', []) %}
                <div class="card">
                    <h3>{{ day.get('day', 'Unknown Date') }}</h3>
                    <div class="score readiness-score">{{ day.get('score', 'N/A') }}</div>
                    <div class="progress-bar">
                        <div class="progress readiness-progress" data-width="{{ day.get('score', 0) }}" style="width: 0%"></div>
                    </div>
                    <p>Recovery Index: {{ day.get('recovery_index', 'N/A') }}</p>
                </div>
                {% endfor %}
            </div>
        </div>
    </div>
    
    <div id="leaderboard-tab" class="tab-content">
        <div class="card">
            <h2>Global Leaderboard</h2>
            <p>See how your sleep compares with others!</p>
            <table class="leaderboard-table">
                <thead>
                    <tr>
                        <th>Rank</th>
                        <th>User</th>
                        <th>Average Sleep Score (7 days)</th>
                        <th>Latest Sleep Score</th>
                    </tr>
                </thead>
                <tbody>
                    {% for user in leaderboard %}
                    <tr {% if user.id == profile.data[0].id %}class="current-user"{% endif %}>
                        <td>{{ loop.index }}</td>
                        <td>{{ user.display_name }}</td>
                        <td>{{ "%.1f"|format(user.get('avg_sleep_score', 0) or 0) }}</td>
                        <td>{{ user.get('last_sleep_score', 'N/A') }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    
    <div id="friends-tab" class="tab-content">
        <div class="card">
            <h2>Your Friends</h2>
            {% if friends.data %}
            <div class="data-grid">
                {% for friendship in friends.data %}
                <div class="card">
                    <h3>{{ friendship.friend.display_name }}</h3>
                    <p>Average Sleep Score: {{ "%.1f"|format(friendship.friend.get('avg_sleep_score', 0) or 0) }}</p>
                    <p>Latest Sleep Score: {{ friendship.friend.get('last_sleep_score', 'N/A') }}</p>
                    <p>Connected since: {{ friendship.created_at[:10] }}</p>
                    <form action="{{ url_for('remove_friend') }}" method="post">
                        <input type="hidden" name="friend_id" value="{{ friendship.friend.id }}">
                        <button type="submit" class="btn">Remove Friend</button>
                    </form>
                </div>
                {% endfor %}
            </div>
            {% else %}
            <p>No friends connected yet. Add friends to compare sleep data!</p>
            {% endif %}
            
            <div class="friend-form">
                <h3>Add a Friend</h3>
                <form action="{{ url_for('add_friend') }}" method="post">
                    <input type="email" name="friend_email" placeholder="Friend's email" required>
                    <button type="submit" class="btn">Add Friend</button>
                </form>
            </div>
        </div>
    </div>
</body>
</html>
        ''', profile=profile, personal_info=personal_info, sleep_data=sleep_data, 
             readiness_data=readiness_data, leaderboard=leaderboard, friends=friends)

    except Exception as e:
        print(f"Error in dashboard: {str(e)}")
        return f"An error occurred: {str(e)}", 500

@app.route('/add_friend', methods=['POST'])
@login_required
def add_friend():
    """Add a friend by email."""
    friend_email = request.form.get('friend_email')
    if not friend_email:
        flash('Friend email is required')
        return redirect(url_for('dashboard'))
    
    try:
        # Find friend by email
        friend = supabase.table('profiles').select('*').eq('email', friend_email).execute()
        if not friend.data:
            flash(f'No user found with email {friend_email}')
            return redirect(url_for('dashboard'))
        
        friend_id = friend.data[0]['id']
        
        # Check if friendship already exists
        existing = supabase.table('friendships').select('*')\
            .eq('user_id', current_user.id)\
            .eq('friend_id', friend_id)\
            .execute()
        
        if existing.data:
            flash(f'You are already friends with {friend_email}')
            return redirect(url_for('dashboard'))
        
        # Create friendship
        supabase.table('friendships').insert({
            'user_id': current_user.id,
            'friend_id': friend_id
        }).execute()
        
        flash(f'Friend {friend_email} added successfully')
    except Exception as e:
        flash(f'Error adding friend: {str(e)}')
    
    return redirect(url_for('dashboard'))

@app.route('/remove_friend', methods=['POST'])
@login_required
def remove_friend():
    """Remove a friend."""
    friend_id = request.form.get('friend_id')
    if not friend_id:
        flash('Friend ID is required')
        return redirect(url_for('dashboard'))
    
    try:
        # Delete friendship
        supabase.table('friendships').delete()\
            .eq('user_id', current_user.id)\
            .eq('friend_id', friend_id)\
            .execute()
        
        flash('Friend removed successfully')
    except Exception as e:
        flash(f'Error removing friend: {str(e)}')
    
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    """Handle user logout."""
    logout_user()
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True) 