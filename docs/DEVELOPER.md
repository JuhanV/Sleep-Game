# Oura Ring Data Comparison App - Developer Documentation

Version: 0.1 (Initial Design)

## Table of Contents

1. [Introduction](#introduction)
2. [Technology Stack](#technology-stack)
3. [Project Setup](#project-setup)
   - [Prerequisites](#prerequisites)
   - [Cloning the Repository](#cloning-the-repository)
   - [Python Environment Setup](#python-environment-setup)
   - [Supabase Setup](#supabase-setup)
   - [Oura Application Setup](#oura-application-setup)
   - [Environment Variables (.env)](#environment-variables-env)
   - [Running the Application](#running-the-application)
4. [Application Architecture](#application-architecture)
   - [Overview](#overview)
   - [Request Flow (Authentication & Data Fetching)](#request-flow-authentication--data-fetching)
5. [Key Components](#key-components)
   - [Backend (Flask)](#backend-flask)
   - [Database (Supabase)](#database-supabase)
   - [Authentication (Oura OAuth2 + Supabase)](#authentication-oura-oauth2--supabase)
   - [Token Management](#token-management)
   - [Oura API Interaction](#oura-api-interaction)
6. [Security Considerations](#security-considerations)
7. [Future Development / TODOs](#future-development--todos)

## Introduction

This application allows multiple users to connect their Oura Ring accounts via OAuth2. It stores their authentication tokens securely in a Supabase database and enables them to compare selected Oura data points with friends who have also connected their accounts to this application.

The primary goal is to provide a simple, shared view of comparative Oura metrics between consenting users, focusing on sleep quality and readiness scores.

## Technology Stack

- **Backend Framework**: Flask (Python)
- **Database & Backend Services**: Supabase (Managed PostgreSQL)
- **Database Interaction (Python)**: supabase-py
- **External API**: Oura Cloud API v2 (OAuth2 for Authentication, REST API for data)
- **Oura API Interaction (Python)**: requests library
- **Token Encryption**: cryptography library (Fernet)
- **Environment Variables**: python-dotenv
- **Authentication**: Flask-Login

## Project Setup

### Prerequisites

- Python 3.8+
- Pip (Python package installer)
- Git
- A Supabase Account (supabase.com)
- An Oura Ring Account and access to the Oura Cloud API Developer portal (https://cloud.ouraring.com/)

### Cloning the Repository

```bash
git clone <your-repository-url>
cd <repository-directory>
```

### Python Environment Setup

It is highly recommended to use a virtual environment.

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Linux/macOS:
source venv/bin/activate
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Windows (Command Prompt):
venv\Scripts\activate.bat

# Install dependencies
pip install -r requirements.txt
```

The required dependencies are specified in `requirements.txt`:

```
# Core dependencies
flask>=2.0.0
requests>=2.31.0
python-dotenv>=1.0.0
supabase>=1.0.0
flask-login>=0.6.0
cryptography>=41.0.0  # For Fernet encryption

# Development dependencies
pytest>=7.4.0
black>=23.7.0
flake8>=6.1.0 
```

### Supabase Setup

1. **Create a Supabase Project**: Go to your Supabase dashboard and create a new project. Choose a region close to you.

2. **Get API Credentials**: Navigate to Project Settings -> API. You will need the Project URL and the API key (keep this secret!).

3. **Create Database Tables**: Use the Supabase SQL Editor to create the necessary tables:

```sql
-- Create profiles table
CREATE TABLE profiles (
  id UUID PRIMARY KEY,
  oura_user_id TEXT UNIQUE NOT NULL,
  email TEXT,
  display_name TEXT,
  oura_tokens TEXT,
  avg_sleep_score NUMERIC,
  last_sleep_score NUMERIC,
  last_login TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Create friendships table
CREATE TABLE friendships (
  id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
  user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
  friend_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
  UNIQUE(user_id, friend_id)
);

-- Add RLS policies if needed
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE friendships ENABLE ROW LEVEL SECURITY;
```

4. **(CRITICAL) Configure Row Level Security (RLS)**: Go to Authentication -> Policies. Enable RLS for all tables (profiles, friendships). Define policies to restrict access appropriately. This is essential for security.

Example policies:
- Users should only be able to select/update their own profiles
- Users should only insert/delete friendships involving their own profile_id
- Access should be denied by default

### Oura Application Setup

1. Go to the Oura Cloud API developer portal: https://cloud.ouraring.com/
2. Register a new application.
3. Note down your Client ID and Client Secret.
4. Add your Redirect URI to the application settings. For local development, this will typically be `http://localhost:5000/callback`. It must match exactly what's configured in your `.env` file and used by Flask.
5. Enable the required Scopes for your application (e.g., personal, daily, sleep, email [optional]).

### Environment Variables (.env)

Create a `.env` file in the root directory of the project using the `.env.example` template and add the following variables:

```dotenv
# Flask configuration
FLASK_SECRET_KEY=your_strong_random_secret_key_for_sessions

# Supabase configuration
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_key

# Oura OAuth2 configuration
OURA_CLIENT_ID=your_oura_client_id
OURA_CLIENT_SECRET=your_oura_client_secret
OURA_REDIRECT_URI=http://localhost:5000/callback

# Encryption configuration
FERNET_KEY=your_fernet_key_for_token_encryption
```

You can generate a secure Fernet key using Python:

```python
from cryptography.fernet import Fernet
key = Fernet.generate_key()
print(key.decode())  # Add this to your .env file as FERNET_KEY
```

### Running the Application

Ensure your virtual environment is active and the `.env` file is populated.

```bash
# Run directly with Python
python src/app.py

# Or run with Flask
export FLASK_APP=src/app.py
flask run
```

The application should be accessible at http://localhost:5000.

## Application Architecture

### Overview

This is a web application with a Python Flask backend and a Supabase database:

- **User Interaction**: Users access the app via their web browser.
- **Authentication**: Authentication is handled via Oura's OAuth2 Authorization Code flow.
- **Backend (Flask)**: Handles HTTP requests, manages the OAuth2 flow, interacts with the Oura API, performs database operations (via Supabase client), manages user sessions (using Flask-Login).
- **Database (Supabase)**: Persistently stores user profile information (linked to Oura IDs) and encrypted Oura API tokens.
- **External Service (Oura API)**: The source of user health data.

### Request Flow (Authentication & Data Fetching)

1. **Login Initiation (/)**: User visits the site and clicks the "Connect Oura Ring" button -> Flask redirects user to Oura's authorization URL.

2. **Oura Authorization**: User logs into Oura -> Authorizes the application's requested scopes.

3. **Callback (/callback)**: Oura redirects user back to Flask's `/callback` endpoint with an authorization code.

4. **Token Exchange**: Flask backend exchanges the code with Oura's token endpoint for `access_token` and `refresh_token` (server-to-server).

5. **User Identification**: Flask uses the new `access_token` to call Oura's `/personal_info` endpoint to get the user's unique Oura user ID and email.

6. **Database Interaction**: Flask searches the Supabase profiles table for the Oura user ID. Creates a new profile if not found.

7. **Token Storage**: Flask encrypts the tokens using Fernet and stores them in the Supabase profiles table, linked to the user's profile_id.

8. **Session Management**: Flask-Login stores the user's authentication state based on their profile_id.

9. **Dashboard Access (/dashboard)**: User is redirected to the dashboard.

10. **Authorization Check**: Flask-Login checks if the user is authenticated.

11. **Token Retrieval**: Flask uses the profile_id to fetch the user's encrypted tokens from Supabase.

12. **Token Handling**: Flask decrypts the `access_token`.

13. **Oura Data Fetching**: Flask uses the valid `access_token` to fetch sleep and readiness data from the Oura API.

14. **Render Page**: Flask renders the dashboard, displaying the fetched data and the global leaderboard.

## Key Components

### Backend (Flask)

The main application file is `src/app.py`, which contains:

- Flask app initialization
- LoginManager setup
- Supabase client configuration
- Fernet encryption setup
- Oura API constants
- Route definitions:
  - `/`: Home page / Login prompt
  - `/callback`: OAuth2 callback handler
  - `/dashboard`: Main user dashboard
  - `/add_friend`: Handles adding friends by email
  - `/remove_friend`: Handles removing friends
  - `/logout`: Logs out the user

### Database (Supabase)

The database contains two main tables:

1. **profiles**: Stores user information and encrypted Oura tokens
   - `id`: UUID primary key
   - `oura_user_id`: Unique identifier from Oura
   - `email`: User's email address
   - `display_name`: Generated from email address
   - `oura_tokens`: Encrypted Oura API tokens
   - `avg_sleep_score`: User's average sleep score
   - `last_sleep_score`: User's most recent sleep score
   - `last_login`: Timestamp of last login
   - `created_at`: Timestamp of profile creation

2. **friendships**: Tracks relationships between users
   - `id`: UUID primary key
   - `user_id`: UUID of the user (references profiles.id)
   - `friend_id`: UUID of the friend (references profiles.id)
   - `created_at`: Timestamp of when the friendship was created

### Authentication (Oura OAuth2 + Supabase)

The application uses Oura's OAuth2 for authentication:

1. **User Authentication**: Handled through Oura's OAuth2 flow
2. **Session Management**: Managed by Flask-Login
3. **User Class**: Implements UserMixin with the user's profile ID as the identifier
4. **Login Required**: Protected routes use the @login_required decorator

### Token Management

1. **Storage**: OAuth tokens are stored encrypted in the `oura_tokens` field of the profiles table
2. **Encryption**: Uses Fernet symmetric encryption with a key stored in environment variables
3. **Functions**:
   - `encrypt_token(token)`: Encrypts token data
   - `decrypt_token(encrypted_token)`: Decrypts token data

### Oura API Interaction

The application interacts with the Oura API using the requests library:

1. **Personal Info**: `/v2/usercollection/personal_info`
2. **Sleep Data**: `/v2/usercollection/daily_sleep`
3. **Readiness Data**: `/v2/usercollection/daily_readiness`

All requests include the `Authorization: Bearer <access_token>` header.

## Security Considerations

1. **Secret Management**: All sensitive information (API keys, tokens) is stored in environment variables using `.env`
2. **Token Encryption**: Oura tokens are encrypted using Fernet before storage
3. **Supabase RLS**: Row Level Security policies should be configured to prevent unauthorized access
4. **HTTPS**: Should be enabled in production
5. **Session Security**: Flask sessions are secured by the secret key
6. **Login Protection**: Routes like `/dashboard` are protected with `@login_required`

## Future Development / TODOs

1. **Implement Token Refresh Logic**: Automatically refresh expired access tokens

2. **Improve Friend Management**:
   - Add friend request system (pending/accepted states)
   - Implement notifications for friend requests

3. **Enhanced Comparison Features**:
   - Side-by-side comparisons of sleep metrics
   - Historical trend comparisons

4. **Data Visualization Improvements**:
   - Charts for sleep quality over time
   - Correlation analysis between different metrics

5. **User Interface Enhancements**:
   - Mobile-responsive design
   - Dark/light theme options
   - Custom dashboards

6. **Performance Optimization**:
   - Database query optimization
   - Caching frequently accessed data

7. **Additional Metrics**:
   - Activity data
   - Heart rate variability
   - Stress levels

8. **Advanced Security**:
   - Implement key rotation for encryption keys
   - Add two-factor authentication options 