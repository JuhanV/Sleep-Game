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

# Define possible redirect URIs
LOCAL_URI = 'http://localhost:5000/callback'
PRODUCTION_URI = 'https://oura-oauth2-integration.onrender.com/callback'

# Get the environment-specific redirect URI or use local as default
ENVIRONMENT = os.getenv('FLASK_ENV', 'development')
OURA_REDIRECT_URI = os.getenv('OURA_REDIRECT_URI', PRODUCTION_URI if ENVIRONMENT == 'production' else LOCAL_URI)

OURA_AUTH_URL = 'https://cloud.ouraring.com/oauth/authorize'
OURA_TOKEN_URL = 'https://api.ouraring.com/oauth/token'

# User class for Flask-Login
class User(UserMixin):
    """User class for Flask-Login."""
    def __init__(self, id, email, display_name, oura_tokens, is_admin=False):
        self.id = id
        self.email = email
        self.display_name = display_name
        self._profile_data = None
        self.oura_tokens = oura_tokens
        self.is_admin = is_admin

    @property
    def profile_data(self):
        """Get user's profile data from DB."""
        if self._profile_data is None:
            # Fetch from Supabase
            response = supabase.table('profiles').select('*').eq('id', self.id).execute()
            if response.data:
                self._profile_data = response.data[0]
            else:
                self._profile_data = {}
        return self._profile_data

@login_manager.user_loader
def load_user(user_id):
    """Load user from DB."""
    response = supabase.table('profiles').select('*').eq('id', user_id).execute()
    if not response.data:
        return None

    user_data = response.data[0]
    is_admin_user = user_data.get('is_admin', False)

    user_obj = User(
        id=user_data['id'],
        email=user_data['email'],
        display_name=user_data['display_name'],
        oura_tokens=user_data.get('oura_tokens'),
        is_admin=is_admin_user
    )
    return user_obj

def encrypt_token(token):
    """Encrypt token using Fernet."""
    return cipher_suite.encrypt(json.dumps(token).encode()).decode()

def decrypt_token(encrypted_token_str):
    """Decrypt an encrypted token string."""
    try:
        print(f"decrypt_token: Starting decryption of token (length: {len(encrypted_token_str) if encrypted_token_str else 0})")
        
        if not encrypted_token_str:
            print("decrypt_token: Empty token string provided")
            return None
            
        # Convert to bytes if it's a string
        if isinstance(encrypted_token_str, str):
            print("decrypt_token: Converting string token to bytes")
            try:
                # First try UTF-8 encoding
                token_bytes = encrypted_token_str.encode('utf-8')
            except UnicodeEncodeError:
                print("decrypt_token: UTF-8 encoding failed, trying latin-1")
                token_bytes = encrypted_token_str.encode('latin-1')
        else:
            token_bytes = encrypted_token_str
            
        print(f"decrypt_token: Token bytes length: {len(token_bytes)}")
        
        # Initialize Fernet with the key
        f = Fernet(fernet_key)
        
        # Decrypt the token
        print("decrypt_token: Attempting decryption")
        decrypted_token = f.decrypt(token_bytes)
        print("decrypt_token: Decryption successful")
        
        # Parse the JSON
        print("decrypt_token: Parsing JSON")
        tokens = json.loads(decrypted_token)
        print("decrypt_token: JSON parsing successful")
        
        return tokens
    except Exception as e:
        print(f"decrypt_token: Error during decryption: {str(e)}")
        print(f"decrypt_token: Error type: {type(e).__name__}")
        import traceback
        print(f"decrypt_token: Traceback: {traceback.format_exc()}")
        return None

@app.route('/')
def index():
    """Redirect to Oura OAuth2 login."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    # Add email scope to ensure we can retrieve user information
    scope = "daily+personal+heartrate+workout+session+tag+email"
    auth_url = f"{OURA_AUTH_URL}?client_id={OURA_CLIENT_ID}&redirect_uri={OURA_REDIRECT_URI}&response_type=code&scope={scope}"
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
            user = User(profile_id, profile_data['email'], profile_data['display_name'], profile_data.get('oura_tokens'), profile_data.get('is_admin', False))
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
    """Display user's Oura data and comparison with others."""
    try:
        # Get user's profile data
        profile = current_user.profile_data
        
        # Get all profiles for leaderboard
        try:
            leaderboard_response = supabase.table('profiles').select('*').order('avg_sleep_score', desc=True).execute()
            leaderboard = leaderboard_response.data if leaderboard_response.data else []
        except Exception as e:
            print(f"Error fetching leaderboard: {str(e)}")
            flash("Error fetching leaderboard data.", "error")
            leaderboard = []
        
        # Decrypt tokens
        tokens = decrypt_token(profile['oura_tokens'])
        if not tokens:
            logout_user()
            flash("Session invalid or token decryption failed. Please log in again.", "error")
            return redirect(url_for('index'))
        
        access_token = tokens.get('access_token')
        if not access_token:
            # Handle missing access token specifically
            logout_user()
            flash("Access token missing. Please log in again.", "error")
            return redirect(url_for('index'))
        
        # --- Define Date Range ---
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        end_date = datetime.now().strftime('%Y-%m-%d')
        
        headers = {'Authorization': f"Bearer {access_token}"}
        
        # --- CORRECTED: Fetch V2 Daily Sleep Data ---
        sleep_data = {"data": []}  # Default empty structure
        sleep_url = 'https://api.ouraring.com/v2/usercollection/daily_sleep'
        sleep_params = {'start_date': start_date, 'end_date': end_date}
        print(f"Fetching V2 Daily Sleep from: {sleep_url} with params: {sleep_params}")
        
        try:
            sleep_response = requests.get(sleep_url, headers=headers, params=sleep_params)
            print(f"V2 Daily Sleep Response Status: {sleep_response.status_code}")
            
            if sleep_response.status_code == 200:
                sleep_data = sleep_response.json()
                print("V2 Daily Sleep Response JSON:", json.dumps(sleep_data, indent=2))
                if not sleep_data.get("data"):
                    print("V2 Daily Sleep data array is empty.")
                    # Generate placeholder data
                    sleep_data = {"data": []}
                    for i in range(7):
                        day_date = (datetime.now() - timedelta(days=6-i)).strftime('%Y-%m-%d')
                        sleep_data["data"].append({
                            "day": day_date,
                            "score": 0,
                            "total_sleep_duration": 0,
                            "deep_sleep_duration": 0,
                            "rem_sleep_duration": 0,
                            "light_sleep_duration": 0
                        })
            elif sleep_response.status_code in [401, 403]:
                print("V2 Daily Sleep request failed with Auth error (401/403). Token might be expired or lack scope.")
                flash("Authentication error fetching sleep data. Your session might have expired.", "error")
            else:
                # Handle other errors (404, 5xx, etc.)
                print(f"V2 Daily Sleep request failed. Status: {sleep_response.status_code}, Response: {sleep_response.text}")
                flash(f"Failed to fetch sleep data (Error {sleep_response.status_code}).", "error")
                # Generate placeholder data
                sleep_data = {"data": []}
                for i in range(7):
                    day_date = (datetime.now() - timedelta(days=6-i)).strftime('%Y-%m-%d')
                    sleep_data["data"].append({
                        "day": day_date,
                        "score": 0,
                        "total_sleep_duration": 0,
                        "deep_sleep_duration": 0,
                        "rem_sleep_duration": 0,
                        "light_sleep_duration": 0
                    })
        
        except requests.exceptions.RequestException as e:
            print(f"Network error fetching V2 Daily Sleep: {str(e)}")
            flash("Network error connecting to Oura API for sleep data.", "error")
        except json.JSONDecodeError:
            print(f"Failed to decode V2 Daily Sleep JSON response. Content: {sleep_response.text}")
            flash("Invalid response received from Oura API for sleep data.", "error")
        except Exception as e:  # Catch unexpected errors
            print(f"Unexpected error fetching V2 Daily Sleep: {str(e)}")
            flash("An unexpected error occurred while fetching sleep data.", "error")
        
        # --- Process Sleep Data (Calculate Average) ---
        sleep_scores = []
        # Use the V2 structure directly: data is a list of daily summaries
        if sleep_data and 'data' in sleep_data:
            for day in sleep_data['data']:
                # V2 uses 'score', not 'sleep_score' directly in the summary object
                if day.get('score') is not None:
                    sleep_scores.append(day.get('score'))
        else:
            print("Sleep data structure missing 'data' key or is empty after fetch attempt.")
        
        # Sort sleep_data['data'] by day if needed for display
        if sleep_data.get('data'):
            sleep_data['data'].sort(key=lambda x: x.get('day', ''))
        
        avg_sleep_score = sum(sleep_scores) / len(sleep_scores) if sleep_scores else 0
        last_sleep_score = sleep_scores[-1] if sleep_scores else None  # Get last score if sorted/relevant
        
        # Update profile with average sleep score
        try:
            supabase.table('profiles').update({
                'avg_sleep_score': avg_sleep_score,
                'last_sleep_score': last_sleep_score
            }).eq('id', current_user.id).execute()
        except Exception as e:
            print(f"Error updating sleep scores in Supabase: {str(e)}")
        
        # --- Fetch Readiness Data ---
        readiness_data = {"data": []}
        readiness_url = 'https://api.ouraring.com/v2/usercollection/daily_readiness'
        readiness_params = {'start_date': start_date, 'end_date': end_date}
        
        try:
            readiness_response = requests.get(readiness_url, headers=headers, params=readiness_params)
            print(f"Readiness API Response Status: {readiness_response.status_code}")
            
            if readiness_response.status_code == 200:
                readiness_data = readiness_response.json()
                print("Readiness API Response:", json.dumps(readiness_data, indent=2))
            else:
                print(f"Readiness API request failed. Status: {readiness_response.status_code}")
                flash("Error fetching readiness data.", "error")
        except Exception as e:
            print(f"Error fetching Readiness data: {str(e)}")
            flash("Error fetching readiness data.", "error")
        
        # --- Fetch Activity Data ---
        activity_data = {"data": []}
        activity_url = 'https://api.ouraring.com/v2/usercollection/daily_activity'
        activity_params = {'start_date': start_date, 'end_date': end_date}
        
        try:
            activity_response = requests.get(activity_url, headers=headers, params=activity_params)
            print(f"Activity API Response Status: {activity_response.status_code}")
            
            if activity_response.status_code == 200:
                activity_data = activity_response.json()
                print("Activity API Response:", json.dumps(activity_data, indent=2))
            else:
                print(f"Activity API request failed. Status: {activity_response.status_code}")
                flash("Error fetching activity data.", "error")
        except Exception as e:
            print(f"Error fetching Activity data: {str(e)}")
            flash("Error fetching activity data.", "error")

        # Update the template to use the correct field names from V2 API
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
        .activity-score {
            color: #FF9800;
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
        .activity-progress {
            background: #FF9800;
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
            function initProgressBar(id) {
                document.querySelectorAll('.' + id).forEach(function(el) {
                    setTimeout(function() {
                        el.style.width = el.getAttribute('data-width') + '%';
                    }, 100);
                });
            }
            
            initProgressBar('sleep-progress');
            initProgressBar('readiness-progress');
            initProgressBar('activity-progress');
            
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
        <p>Welcome, {{ profile.display_name }}!</p>
    </div>
    
    <div class="tab-container">
        <div class="tab active" data-tab="sleep-tab">Sleep Data</div>
        <div class="tab" data-tab="readiness-tab">Readiness Data</div>
        <div class="tab" data-tab="activity-tab">Activity Data</div>
        <div class="tab" data-tab="leaderboard-tab">Leaderboard</div>
    </div>
    
    <div id="sleep-tab" class="tab-content active">
        <div class="card">
            <h2>Your Sleep Scores (Last 7 Days)</h2>
            <p>Average Sleep Score: <span class="score sleep-score">{{ "%.1f"|format(profile.avg_sleep_score or 0) }}</span></p>
            <div class="data-grid">
                {% for day in sleep_data.get('data', []) %}
                <div class="card">
                    <h3>{{ day.get('day', 'Unknown Date') }}</h3>
                    <div class="score sleep-score">{{ day.get('score', 'N/A') }}</div>
                    <div class="progress-bar">
                        <div class="progress sleep-progress" data-width="{{ day.get('score', 0) or 0 }}" style="width: 0%"></div>
                    </div>
                    
                    <div style="margin-top: 15px; border-top: 1px solid #eee; padding-top: 10px;">
                        <h4>Sleep Details</h4>
                        <ul style="padding-left: 0; list-style-type: none;">
                            <li style="margin-bottom: 5px;"><strong>Score:</strong> {{ day.get('score', 'N/A') }}</li>
                            {% if day.get('efficiency') is not none %}
                            <li style="margin-bottom: 5px;"><strong>Efficiency:</strong> {{ day.get('efficiency') }}%</li>
                            {% endif %}
                            {% if day.get('total_sleep_duration') is not none %}
                            <li style="margin-bottom: 5px;"><strong>Total Sleep:</strong> {% if day.get('total_sleep_duration') > 0 %}{{ day.get('total_sleep_duration') // 60 }} hours {{ day.get('total_sleep_duration') % 60 }} minutes{% else %}<span style="color: #999;">No data available</span>{% endif %}</li>
                            {% endif %}
                            {% if day.get('sleep_phase_durations') is not none and day.get('sleep_phase_durations').get('awake') is not none %}
                            <li style="margin-bottom: 5px;"><strong>Awake Time:</strong> {{ day.get('sleep_phase_durations', {}).get('awake', 0) // 60 }} min {{ day.get('sleep_phase_durations', {}).get('awake', 0) % 60 }} sec</li>
                            {% endif %}
                            {% if day.get('latency') is not none %}
                            <li style="margin-bottom: 5px;"><strong>Sleep Latency:</strong> {% if day.get('latency') > 0 %}{{ day.get('latency') // 60 }} min {{ day.get('latency') % 60 }} sec{% else %}<span style="color: #999;">No data available</span>{% endif %}</li>
                            {% endif %}
                            {% if day.get('sleep_phase_count') is not none %}
                            <li style="margin-bottom: 5px;"><strong>Sleep Cycles:</strong> {{ day.get('sleep_phase_count') }}</li>
                            {% endif %}
                            {% if day.get('restless_periods') is not none %}
                            <li style="margin-bottom: 5px;"><strong>Restless Periods:</strong> {{ day.get('restless_periods') }}</li>
                            {% endif %}
                            {% if day.get('sleep_score_delta') is not none %}
                            <li style="margin-bottom: 5px;"><strong>Score Change:</strong> {{ day.get('sleep_score_delta') }}</li>
                            {% endif %}
                        </ul>
                    </div>
                    
                    {% if day.get('deep_sleep_duration') or day.get('rem_sleep_duration') or day.get('light_sleep_duration') or day.get('sleep_phase_durations') %}
                    <div style="margin-top: 15px; border-top: 1px solid #eee; padding-top: 10px;">
                        <h4>Sleep Stages</h4>
                        <ul style="padding-left: 0; list-style-type: none;">
                            {% if day.get('deep_sleep_duration') %}
                            <li style="margin-bottom: 5px;"><strong>Deep Sleep:</strong> {{ day.get('deep_sleep_duration') // 60 }} hours {{ day.get('deep_sleep_duration') % 60 }} minutes</li>
                            {% elif day.get('sleep_phase_durations', {}).get('deep') %}
                            <li style="margin-bottom: 5px;"><strong>Deep Sleep:</strong> {{ day.get('sleep_phase_durations', {}).get('deep', 0) // 60 }} min {{ day.get('sleep_phase_durations', {}).get('deep', 0) % 60 }} sec</li>
                            {% endif %}
                            
                            {% if day.get('rem_sleep_duration') %}
                            <li style="margin-bottom: 5px;"><strong>REM Sleep:</strong> {{ day.get('rem_sleep_duration') // 60 }} hours {{ day.get('rem_sleep_duration') % 60 }} minutes</li>
                            {% elif day.get('sleep_phase_durations', {}).get('rem') %}
                            <li style="margin-bottom: 5px;"><strong>REM Sleep:</strong> {{ day.get('sleep_phase_durations', {}).get('rem', 0) // 60 }} min {{ day.get('sleep_phase_durations', {}).get('rem', 0) % 60 }} sec</li>
                            {% endif %}
                            
                            {% if day.get('light_sleep_duration') %}
                            <li style="margin-bottom: 5px;"><strong>Light Sleep:</strong> {{ day.get('light_sleep_duration') // 60 }} hours {{ day.get('light_sleep_duration') % 60 }} minutes</li>
                            {% elif day.get('sleep_phase_durations', {}).get('light') %}
                            <li style="margin-bottom: 5px;"><strong>Light Sleep:</strong> {{ day.get('sleep_phase_durations', {}).get('light', 0) // 60 }} min {{ day.get('sleep_phase_durations', {}).get('light', 0) % 60 }} sec</li>
                            {% endif %}
                            
                            {% if day.get('awake_duration') %}
                            <li style="margin-bottom: 5px;"><strong>Time Awake:</strong> {{ day.get('awake_duration') // 60 }} hours {{ day.get('awake_duration') % 60 }} minutes</li>
                            {% endif %}
                            
                            {% if day.get('sleep_phase_durations', {}).get('out') is not none %}
                            <li style="margin-bottom: 5px;"><strong>Out of Bed:</strong> {{ day.get('sleep_phase_durations', {}).get('out', 0) // 60 }} min {{ day.get('sleep_phase_durations', {}).get('out', 0) % 60 }} sec</li>
                            {% endif %}
                        </ul>

                        {% if day.get('sleep_phase_percentage') %}
                        <div style="margin-top: 10px;">
                            <h5>Sleep Composition</h5>
                            <div style="display: flex; height: 20px; border-radius: 3px; overflow: hidden;">
                                {% if day.get('sleep_phase_percentage', {}).get('deep') %}
                                <div style="background: #1E88E5; width: {{ day.get('sleep_phase_percentage', {}).get('deep', 0) }}%; display: flex; justify-content: center; align-items: center; color: white; font-size: 10px;">{{ day.get('sleep_phase_percentage', {}).get('deep', 0) }}%</div>
                                {% endif %}
                                {% if day.get('sleep_phase_percentage', {}).get('rem') %}
                                <div style="background: #43A047; width: {{ day.get('sleep_phase_percentage', {}).get('rem', 0) }}%; display: flex; justify-content: center; align-items: center; color: white; font-size: 10px;">{{ day.get('sleep_phase_percentage', {}).get('rem', 0) }}%</div>
                                {% endif %}
                                {% if day.get('sleep_phase_percentage', {}).get('light') %}
                                <div style="background: #7CB342; width: {{ day.get('sleep_phase_percentage', {}).get('light', 0) }}%; display: flex; justify-content: center; align-items: center; color: white; font-size: 10px;">{{ day.get('sleep_phase_percentage', {}).get('light', 0) }}%</div>
                                {% endif %}
                                {% if day.get('sleep_phase_percentage', {}).get('awake') %}
                                <div style="background: #FFB300; width: {{ day.get('sleep_phase_percentage', {}).get('awake', 0) }}%; display: flex; justify-content: center; align-items: center; color: white; font-size: 10px;">{{ day.get('sleep_phase_percentage', {}).get('awake', 0) }}%</div>
                                {% endif %}
                            </div>
                            <div style="display: flex; justify-content: space-between; font-size: 10px; margin-top: 3px;">
                                <span style="color: #1E88E5;">Deep</span>
                                <span style="color: #43A047;">REM</span>
                                <span style="color: #7CB342;">Light</span>
                                <span style="color: #FFB300;">Awake</span>
                            </div>
                        </div>
                        {% endif %}
                    </div>
                    {% endif %}
                    
                    {% if day.get('average_heart_rate') or day.get('lowest_heart_rate') or day.get('average_hrv') or day.get('temperature_delta') or day.get('breathing_variations') %}
                    <div style="margin-top: 15px; border-top: 1px solid #eee; padding-top: 10px;">
                        <h4>Biometrics</h4>
                        <ul style="padding-left: 0; list-style-type: none;">
                            {% if day.get('average_heart_rate') %}
                            <li style="margin-bottom: 5px;"><strong>Average HR:</strong> {{ day.get('average_heart_rate') }} bpm</li>
                            {% endif %}
                            
                            {% if day.get('lowest_heart_rate') %}
                            <li style="margin-bottom: 5px;"><strong>Lowest HR:</strong> {{ day.get('lowest_heart_rate') }} bpm</li>
                            {% endif %}
                            
                            {% if day.get('average_hrv') %}
                            <li style="margin-bottom: 5px;"><strong>Average HRV:</strong> {{ day.get('average_hrv') }} ms</li>
                            {% endif %}
                            
                            {% if day.get('average_breath') %}
                            <li style="margin-bottom: 5px;"><strong>Respiratory Rate:</strong> {{ day.get('average_breath') }} breaths/min</li>
                            {% endif %}
                            
                            {% if day.get('temperature_delta') %}
                            <li style="margin-bottom: 5px;"><strong>Temperature Deviation:</strong> {{ "%.2f"|format(day.get('temperature_delta')) }} °C</li>
                            {% endif %}
                            
                            {% if day.get('breathing_variations') %}
                            <li style="margin-bottom: 5px;"><strong>Breathing Variations:</strong> {{ day.get('breathing_variations') }}</li>
                            {% endif %}
                            
                            {% if day.get('heart_rate_variability') %}
                            <li style="margin-bottom: 5px;"><strong>HRV Trend:</strong> {{ day.get('heart_rate_variability') }}</li>
                            {% endif %}
                        </ul>
                    </div>
                    {% endif %}
                    
                    {% if day.get('bedtime_start') or day.get('bedtime_end') %}
                    <div style="margin-top: 15px; border-top: 1px solid #eee; padding-top: 10px;">
                        <h4>Sleep Timing</h4>
                        <ul style="padding-left: 0; list-style-type: none;">
                            {% if day.get('bedtime_start') %}
                            <li style="margin-bottom: 5px;"><strong>Bedtime:</strong> {{ day.get('bedtime_start').split('T')[1][:5] }}</li>
                            {% endif %}
                            
                            {% if day.get('bedtime_end') %}
                            <li style="margin-bottom: 5px;"><strong>Wake-up:</strong> {{ day.get('bedtime_end').split('T')[1][:5] }}</li>
                            {% endif %}
                            
                            {% if day.get('bedtime_start') and day.get('bedtime_end') %}
                                {% set start = day.get('bedtime_start').split('T')[1][:5] %}
                                {% set end = day.get('bedtime_end').split('T')[1][:5] %}
                                <li style="margin-bottom: 5px;"><strong>Time in Bed:</strong> {{ ((day.get('total_sleep_duration', 0) + day.get('awake_duration', 0))) // 60 }} hours {{ ((day.get('total_sleep_duration', 0) + day.get('awake_duration', 0))) % 60 }} minutes</li>
                            {% endif %}
                            
                            {% if day.get('midpoint_time') %}
                            <li style="margin-bottom: 5px;"><strong>Midpoint of Sleep:</strong> {{ day.get('midpoint_time').split('T')[1][:5] }}</li>
                            {% endif %}
                            
                            {% if day.get('onset_latency') %}
                            <li style="margin-bottom: 5px;"><strong>Time to Fall Asleep:</strong> {{ day.get('onset_latency') // 60 }} min {{ day.get('onset_latency') % 60 }} sec</li>
                            {% endif %}
                        </ul>
                    </div>
                    {% endif %}
                    
                    {% if day.get('tags') or day.get('contributors') %}
                    <div style="margin-top: 15px; border-top: 1px solid #eee; padding-top: 10px;">
                        <h4>Analysis</h4>
                        <ul style="padding-left: 0; list-style-type: none;">
                            {% if day.get('contributors', {}).get('deep_sleep') %}
                            <li style="margin-bottom: 5px;"><strong>Deep Sleep Quality:</strong> {{ day.get('contributors', {}).get('deep_sleep') }}/100</li>
                            {% endif %}
                            
                            {% if day.get('contributors', {}).get('rem_sleep') %}
                            <li style="margin-bottom: 5px;"><strong>REM Sleep Quality:</strong> {{ day.get('contributors', {}).get('rem_sleep') }}/100</li>
                            {% endif %}
                            
                            {% if day.get('contributors', {}).get('efficiency') %}
                            <li style="margin-bottom: 5px;"><strong>Sleep Efficiency:</strong> {{ day.get('contributors', {}).get('efficiency') }}/100</li>
                            {% endif %}
                            
                            {% if day.get('contributors', {}).get('latency') %}
                            <li style="margin-bottom: 5px;"><strong>Sleep Onset:</strong> {{ day.get('contributors', {}).get('latency') }}/100</li>
                            {% endif %}
                            
                            {% if day.get('contributors', {}).get('timing') %}
                            <li style="margin-bottom: 5px;"><strong>Sleep Timing:</strong> {{ day.get('contributors', {}).get('timing') }}/100</li>
                            {% endif %}
                            
                            {% if day.get('sleep_algorithm_version') %}
                            <li style="margin-bottom: 5px;"><strong>Algorithm Version:</strong> {{ day.get('sleep_algorithm_version') }}</li>
                            {% endif %}
                        </ul>
                    </div>
                    {% endif %}
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
                        <div class="progress readiness-progress" data-width="{{ day.get('score', 0) or 0 }}" style="width: 0%"></div>
                    </div>
                    
                    {% if day.get('contributors') %}
                    <div style="margin-top: 15px; border-top: 1px solid #eee; padding-top: 10px;">
                        <h4>Contributors</h4>
                        <ul style="padding-left: 0; list-style-type: none;">
                            {% if day.get('contributors', {}).get('sleep_balance') %}
                            <li style="margin-bottom: 5px;">Sleep Balance: {{ day.get('contributors', {}).get('sleep_balance') }}</li>
                            {% endif %}
                            
                            {% if day.get('contributors', {}).get('hrv_balance') %}
                            <li style="margin-bottom: 5px;">HRV Balance: {{ day.get('contributors', {}).get('hrv_balance') }}</li>
                            {% endif %}
                            
                            {% if day.get('contributors', {}).get('activity_balance') %}
                            <li style="margin-bottom: 5px;">Activity Balance: {{ day.get('contributors', {}).get('activity_balance') }}</li>
                            {% endif %}
                            
                            {% if day.get('contributors', {}).get('recovery_index') %}
                            <li style="margin-bottom: 5px;">Recovery Index: {{ day.get('contributors', {}).get('recovery_index') }}</li>
                            {% endif %}
                            
                            {% if day.get('contributors', {}).get('body_temperature') %}
                            <li style="margin-bottom: 5px;">Body Temperature: {{ day.get('contributors', {}).get('body_temperature') }}</li>
                            {% endif %}
                            
                            {% if day.get('contributors', {}).get('resting_heart_rate') %}
                            <li style="margin-bottom: 5px;">Resting Heart Rate: {{ day.get('contributors', {}).get('resting_heart_rate') }}</li>
                            {% endif %}
                            
                            {% if day.get('contributors', {}).get('previous_day_activity') %}
                            <li style="margin-bottom: 5px;">Previous Day Activity: {{ day.get('contributors', {}).get('previous_day_activity') }}</li>
                            {% endif %}
                            
                            {% if day.get('contributors', {}).get('previous_night') %}
                            <li style="margin-bottom: 5px;">Previous Night: {{ day.get('contributors', {}).get('previous_night') }}</li>
                            {% endif %}
                        </ul>
                    </div>
                    {% endif %}
                </div>
                {% endfor %}
            </div>
        </div>
    </div>
    
    <div id="activity-tab" class="tab-content">
        <div class="card">
            <h2>Your Activity Scores (Last 7 Days)</h2>
            <div class="data-grid">
                {% for day in activity_data.get('data', []) %}
                <div class="card">
                    <h3>{{ day.get('day', 'Unknown Date') }}</h3>
                    <div class="score activity-score">{{ day.get('score', 'N/A') }}</div>
                    <div class="progress-bar">
                        <div class="progress activity-progress" data-width="{{ day.get('score', 0) or 0 }}" style="width: 0%"></div>
                    </div>
                    <p>Steps: {{ day.get('steps', 'N/A') }}</p>
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
                    <tr {% if user.id == profile.id %}class="current-user"{% endif %}>
                        <td>{{ loop.index }}</td>
                        <td>{{ user.display_name }}</td>
                        <td>{{ "%.1f"|format(user.avg_sleep_score or 0) }}</td>
                        <td>{{ user.last_sleep_score or 'N/A' }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
        ''', profile=profile, sleep_data=sleep_data, readiness_data=readiness_data, activity_data=activity_data, leaderboard=leaderboard)

    except Exception as e:
        print(f"Unhandled Error in dashboard route: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f"An unexpected error occurred in the dashboard: {str(e)}", "error")
        return redirect(url_for('index'))

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

@app.route('/debug_data')
@login_required
def debug_data():
    """Debug endpoint to check raw Oura API responses."""
    try:
        # Get user's profile data
        profile = current_user.profile_data
        
        # Decrypt tokens
        tokens = decrypt_token(profile['oura_tokens'])
        if not tokens:
            return "Failed to decrypt tokens", 500
            
        # Check token status
        token_info = {
            "access_token_exists": bool(tokens.get('access_token')),
            "refresh_token_exists": bool(tokens.get('refresh_token')),
            "token_type": tokens.get('token_type'),
            "expires_in": tokens.get('expires_in')
        }
        
        # Get dates for testing
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        end_date = datetime.now().strftime('%Y-%m-%d')
        
        # Test all endpoints
        endpoints = [
            # v1 endpoints
            {'name': 'v1_sleep', 'url': 'https://api.ouraring.com/v1/sleep', 'params': {'start': start_date, 'end': end_date}},
            
            # v2 endpoints
            {'name': 'v2_daily_sleep', 'url': 'https://api.ouraring.com/v2/usercollection/daily_sleep', 'params': {'start_date': start_date, 'end_date': end_date}},
            {'name': 'v2_daily_readiness', 'url': 'https://api.ouraring.com/v2/usercollection/daily_readiness', 'params': {'start_date': start_date, 'end_date': end_date}},
        ]
        
        results = {}
        for endpoint in endpoints:
            try:
                response = requests.get(
                    endpoint['url'],
                    headers={'Authorization': f"Bearer {tokens['access_token']}"},
                    params=endpoint['params']
                )
                results[endpoint['name']] = {
                    'status_code': response.status_code,
                    'url': response.url
                }
                if response.status_code == 200:
                    data = response.json()
                    results[endpoint['name']]['response'] = data
                else:
                    results[endpoint['name']]['response'] = response.text
            except Exception as e:
                results[endpoint['name']]['error'] = str(e)
        
        return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Oura API Debug</title>
            <style>
                body { font-family: monospace; margin: 20px; }
                .endpoint { margin-bottom: 30px; border: 1px solid #ddd; padding: 15px; border-radius: 5px; }
                h2 { margin-top: 0; }
                pre { background: #f5f5f5; padding: 10px; overflow-x: auto; max-height: 500px; }
                .success { color: green; }
                .error { color: red; }
            </style>
        </head>
        <body>
            <h1>Oura API Debug</h1>
            
            <div class="endpoint">
                <h2>Token Status</h2>
                <pre>{{ token_info | tojson(indent=2) }}</pre>
            </div>
            
            {% for name, result in results.items() %}
            <div class="endpoint">
                <h2>{{ name }}</h2>
                <p>URL: {{ result.url }}</p>
                <p class="{{ 'success' if result.status_code == 200 else 'error' }}">
                    Status: {{ result.status_code }}
                </p>
                {% if result.get('error') %}
                <p class="error">Error: {{ result.error }}</p>
                {% else %}
                <pre>{{ result.response | tojson(indent=2) }}</pre>
                {% endif %}
            </div>
            {% endfor %}
            
            <div style="margin-top: 30px;">
                <a href="{{ url_for('dashboard') }}">Return to Dashboard</a>
            </div>
        </body>
        </html>
        ''', token_info=token_info, results=results)
        
    except Exception as e:
        return f"An error occurred: {str(e)}", 500

# Add admin check function
def is_admin():
    """Check if current user is an admin based SOLELY on the loaded user object."""
    print("--- Entering is_admin() check ---")
    if not current_user.is_authenticated:
        print("is_admin(): User not authenticated, returning False")
        return False
    # Use getattr for safety in case the attribute doesn't exist for some reason
    admin_status = getattr(current_user, 'is_admin', False)
    print(f"is_admin(): getattr(current_user, 'is_admin', False) resolved to: {admin_status}")
    print("--- Exiting is_admin() check ---")
    return admin_status

# Add an admin dashboard route
@app.route('/admin')
@login_required
def admin_dashboard():
    """Admin dashboard to view all users' data."""
    # Direct check
    is_user_admin = getattr(current_user, 'is_admin', False)
    if not is_user_admin:
        flash("You don't have permission to access the admin dashboard.", "error")
        return redirect(url_for('dashboard'))

    try:
        # Get all profiles
        all_profiles = supabase.table('profiles').select('*').execute()
        
        if not all_profiles.data:
            flash("No users found in the database.", "error")
            return redirect(url_for('dashboard'))
        
        return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Admin Dashboard</title>
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
        .user-list {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
        }
        .user-card {
            background: white;
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }
        .user-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        .button {
            display: inline-block;
            padding: 8px 16px;
            background-color: #6200EA;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            transition: background-color 0.2s;
        }
        .button:hover {
            background-color: #5000D6;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header a {
            color: #666;
            text-decoration: none;
            margin-left: 15px;
        }
        .header a:hover {
            color: #333;
        }
        .score {
            font-size: 24px;
            font-weight: bold;
            color: #4CAF50;
        }
    </style>
</head>
<body>
    <div class="card">
        <div class="header">
            <h1>Admin Dashboard</h1>
            <div>
                <a href="{{ url_for('dashboard') }}">My Dashboard</a>
                <a href="{{ url_for('logout') }}">Logout</a>
            </div>
        </div>
        
        <h2>All Users</h2>
        <div class="user-list">
            {% for profile in profiles %}
            <div class="user-card">
                <h3>{{ profile.display_name }}</h3>
                <p>Email: {{ profile.email }}</p>
                <p>Average Sleep Score: <span class="score">{{ "%.1f"|format(profile.avg_sleep_score or 0) }}</span></p>
                <p>Last Sleep Score: {{ profile.last_sleep_score or 'N/A' }}</p>
                <p>Last Login: {{ profile.updated_at[:10] if profile.updated_at else 'Never' }}</p>
                
                <a href="{{ url_for('view_user_data', user_id=profile.id) }}" class="button">View Data</a>
            </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
        ''', profiles=all_profiles.data)

    except Exception as e:
        print(f"Error in admin dashboard logic: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f"An error occurred loading the admin dashboard: {str(e)}", "error")
        return redirect(url_for('dashboard'))

# Add a route to view individual user data as admin
@app.route('/admin/user/<user_id>')
@login_required
def view_user_data(user_id):
    print(f"\n--- Entering view_user_data for target user_id: {user_id} ---")
    # Check 1: Is the current user admin?
    is_requesting_user_admin = getattr(current_user, 'is_admin', False)
    print(f"view_user_data: Admin check result: {is_requesting_user_admin}")
    if not is_requesting_user_admin:
        flash("You don't have permission to access other users' data.", "error")
        return redirect(url_for('dashboard'))

    try:
        # Check 2: Does the target user exist?
        print(f"view_user_data: Fetching profile for {user_id}")
        profile_response = supabase.table('profiles').select('*').eq('id', user_id).execute()
        if not profile_response.data:
            print(f"view_user_data: Profile not found for {user_id}. Redirecting.")
            flash("User not found.", "error")
            return redirect(url_for('admin_dashboard'))

        profile = profile_response.data[0]
        print(f"view_user_data: Found profile for {profile.get('display_name')}")
        all_profiles = supabase.table('profiles').select('id, display_name').execute().data

        # Check 3: Can tokens be decrypted?
        print(f"view_user_data: Decrypting tokens for {profile.get('display_name')}")
        encrypted_token_str = profile.get('oura_tokens')
        print(f"view_user_data: Raw token from DB: {encrypted_token_str[:30]}... (length: {len(encrypted_token_str) if encrypted_token_str else 0})")
        
        if not encrypted_token_str:
            print("view_user_data: Encrypted token string is missing/null in DB. Redirecting.")
            flash("User profile is missing Oura token data.", "error")
            return redirect(url_for('admin_dashboard'))

        # Try to decrypt the token directly first
        try:
            tokens = decrypt_token(encrypted_token_str)
            if tokens:
                print("view_user_data: Successfully decrypted token directly")
                return render_template('admin/user_data.html', 
                                    user=profile,
                                    sleep_data=sleep_data,
                                    readiness_data=readiness_data,
                                    activity_data=activity_data)
        except Exception as e:
            print(f"view_user_data: Direct decryption failed: {str(e)}")
            print(f"view_user_data: Error type: {type(e).__name__}")
            import traceback
            print(f"view_user_data: Traceback: {traceback.format_exc()}")

        # If direct decryption fails, try to handle the token format
        try:
            # Remove any potential padding or extra characters
            clean_token = encrypted_token_str.strip()
            print(f"view_user_data: Cleaned token: {clean_token[:30]}...")
            
            # Try to decrypt the cleaned token
            tokens = decrypt_token(clean_token)
            if tokens:
                print("view_user_data: Successfully decrypted cleaned token")
                return render_template('admin/user_data.html', 
                                    user=profile,
                                    sleep_data=sleep_data,
                                    readiness_data=readiness_data,
                                    activity_data=activity_data)
        except Exception as e:
            print(f"view_user_data: Cleaned token decryption failed: {str(e)}")
            print(f"view_user_data: Error type: {type(e).__name__}")
            print(f"view_user_data: Traceback: {traceback.format_exc()}")

        print(f"view_user_data: All decryption attempts failed for {profile.get('display_name')}. Redirecting.")
        flash("Unable to decrypt user's Oura tokens.", "error")
        return redirect(url_for('admin_dashboard'))

    except Exception as e:
        print(f"Error in view_user_data for user {user_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f"An error occurred viewing user {profile.get('display_name', user_id)}: {str(e)}", "error")
        return redirect(url_for('admin_dashboard'))

@app.route('/debug_admin')
def debug_admin():
    """Debug route to check admin status."""
    if not current_user.is_authenticated:
        return "Not logged in"
    
    # Check if user is admin
    admin_status = current_user.is_admin if hasattr(current_user, 'is_admin') else False
    
    # Get current user's profile from Supabase
    response = supabase.table('profiles').select('*').eq('id', current_user.id).execute()
    db_is_admin = False
    if response.data:
        db_is_admin = response.data[0].get('is_admin', False)
    
    return f"""
    <h1>Admin Debug</h1>
    <p>User ID: {current_user.id}</p>
    <p>Email: {current_user.email}</p>
    <p>current_user.is_admin: {admin_status}</p>
    <p>Database is_admin: {db_is_admin}</p>
    <p>User Class: {type(current_user).__name__}</p>
    <p><a href="/dashboard">Go to Dashboard</a></p>
    """

@app.route('/make_admin/<user_id>')
@login_required
def make_admin(user_id):
    """Make a user an admin (only accessible by existing admins)."""
    # Only allow existing admins to make others admin
    if not is_admin():
        flash("You don't have permission to perform this action.", "error")
        return redirect(url_for('dashboard'))
    
    try:
        # Update the user's profile in Supabase
        supabase.table('profiles').update({'is_admin': True}).eq('id', user_id).execute()
        flash("User has been granted admin privileges.", "success")
    except Exception as e:
        flash(f"Error making user admin: {str(e)}", "error")
    
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True) 