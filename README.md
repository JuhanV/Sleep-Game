# Oura Ring Data Comparison

A web application that allows users to connect their Oura Ring accounts, view their sleep and readiness metrics, and compare their data with other users on a global leaderboard.

## Features

- **OAuth2 Integration**: Securely authenticate with Oura Ring API
- **Sleep Data Visualization**: View your sleep scores for the last 7 days
- **Readiness Metrics**: Monitor your body's recovery status
- **Global Leaderboard**: Compare your sleep performance with others
- **Friend Connections**: Connect with friends to track each other's progress
- **Secure Token Storage**: All OAuth tokens are encrypted using Fernet

## Project Structure

- `src/` - Source code directory
  - `app.py` - Main Flask application with routes and core functionality
- `tests/` - Test files
- `docs/` - Documentation
- `requirements.txt` - Python dependencies
- `.env.example` - Template for environment variables

## Technical Components

- **Backend**: Flask web framework
- **Database**: Supabase PostgreSQL database
- **Authentication**: OAuth2 with Oura API
- **Encryption**: Fernet symmetric encryption for token storage
- **UI**: Server-rendered HTML with modern CSS and JavaScript

## Prerequisites

- Python 3.8 or higher
- Oura Ring API Developer Account
- Supabase Account
- Oura Ring (to generate data)

## Database Schema

The application uses the following tables in Supabase:

1. **profiles**
   ```sql
   create table profiles (
     id uuid primary key,
     oura_user_id text unique not null,
     email text,
     display_name text,
     oura_tokens text,  -- encrypted tokens
     avg_sleep_score numeric,
     last_sleep_score numeric,
     last_login timestamp with time zone,
     created_at timestamp with time zone default timezone('utc'::text, now()) not null
   );
   ```

2. **friendships**
   ```sql
   create table friendships (
     id uuid default uuid_generate_v4() primary key,
     user_id uuid references profiles(id) on delete cascade,
     friend_id uuid references profiles(id) on delete cascade,
     created_at timestamp with time zone default timezone('utc'::text, now()) not null,
     unique(user_id, friend_id)
   );
   ```

## Getting Started

1. Clone the repository
2. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set up your Supabase project and create the required tables
5. Create an Oura Developer account and register an application
6. Copy `.env.example` to `.env` and fill in your credentials:
   ```bash
   cp .env.example .env
   ```
7. Generate a Fernet key (or let the application generate one on first run):
   ```python
   from cryptography.fernet import Fernet
   key = Fernet.generate_key()
   print(key.decode())  # Add this to your .env file
   ```
8. Run the application:
   ```bash
   python src/app.py
   ```
9. Visit http://localhost:5000 in your browser

## Environment Variables

- `FLASK_SECRET_KEY`: Secret key for Flask session management
- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_KEY`: Your Supabase project API key
- `OURA_CLIENT_ID`: Your Oura Ring API client ID
- `OURA_CLIENT_SECRET`: Your Oura Ring API client secret
- `OURA_REDIRECT_URI`: OAuth2 callback URL (default: http://localhost:5000/callback)
- `FERNET_KEY`: Encryption key for securing OAuth tokens

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- Oura Ring API for providing access to health data
- Supabase for the database infrastructure 