# Setup Guide

This document provides detailed instructions on setting up the Oura Ring Data Comparison application for both development and production environments.

## Development Environment Setup

### Prerequisites

1. **Python Environment**
   - Python 3.8 or higher installed
   - pip and virtualenv or venv

2. **Oura Developer Account**
   - Create an account at [Oura Developer Portal](https://cloud.ouraring.com/oauth/applications)
   - Register a new application with the following settings:
     - Name: Oura Data Comparison (or your preferred name)
     - Redirect URI: http://localhost:5000/callback
     - Scopes: personal, daily

3. **Supabase Account**
   - Create a new project at [Supabase](https://supabase.com)
   - Get your project URL and API key from the project settings

### Database Setup

Execute the following SQL statements in your Supabase SQL Editor:

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

### Application Setup

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd oura-data-comparison
   ```

2. **Create and activate a virtual environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Environment variables setup**

   ```bash
   cp .env.example .env
   ```

   Edit the `.env` file and add your:
   - Flask secret key (generate a random one)
   - Supabase URL and API key
   - Oura client ID and secret
   - Generate a Fernet key:
     ```python
     from cryptography.fernet import Fernet
     key = Fernet.generate_key()
     print(key.decode())
     ```

5. **Run the application**

   ```bash
   python src/app.py
   ```

6. **Access the application**

   Open your browser and go to http://localhost:5000

## Production Deployment

### Deploying to a Server

1. **Server Requirements**
   - Ubuntu 20.04 or similar Linux distribution
   - Python 3.8+
   - Nginx for reverse proxy
   - Supervisor for process management

2. **Setup Steps**

   ```bash
   # Clone the repository
   git clone <repository-url>
   cd oura-data-comparison
   
   # Create and activate virtual environment
   python3 -m venv venv
   source venv/bin/activate
   
   # Install dependencies
   pip install -r requirements.txt
   
   # Set up environment variables
   cp .env.example .env
   # Edit .env with your production values
   
   # Create a systemd service
   sudo nano /etc/systemd/system/oura-comparison.service
   ```

3. **Create a systemd service file**

   ```
   [Unit]
   Description=Oura Ring Data Comparison
   After=network.target
   
   [Service]
   User=<your-user>
   WorkingDirectory=/path/to/oura-data-comparison
   ExecStart=/path/to/oura-data-comparison/venv/bin/python src/app.py
   Restart=always
   
   [Install]
   WantedBy=multi-user.target
   ```

4. **Configure Nginx as a reverse proxy**

   ```
   server {
       listen 80;
       server_name yourdomain.com;
       
       location / {
           proxy_pass http://localhost:5000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

5. **Start the service**

   ```bash
   sudo systemctl enable oura-comparison
   sudo systemctl start oura-comparison
   ```

6. **Set up SSL with Let's Encrypt**

   ```bash
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d yourdomain.com
   ```

### Deploying to Heroku

1. **Create a Procfile**

   ```
   web: gunicorn src.app:app
   ```

2. **Add gunicorn to requirements**

   ```bash
   pip install gunicorn
   pip freeze > requirements.txt
   ```

3. **Create a runtime.txt file**

   ```
   python-3.9.10
   ```

4. **Deploy to Heroku**

   ```bash
   heroku create oura-data-comparison
   heroku config:set FLASK_SECRET_KEY=<your-secret-key>
   heroku config:set SUPABASE_URL=<your-supabase-url>
   heroku config:set SUPABASE_KEY=<your-supabase-key>
   heroku config:set OURA_CLIENT_ID=<your-oura-client-id>
   heroku config:set OURA_CLIENT_SECRET=<your-oura-client-secret>
   heroku config:set OURA_REDIRECT_URI=https://your-app.herokuapp.com/callback
   heroku config:set FERNET_KEY=<your-fernet-key>
   
   git push heroku main
   ```

5. **Update your Oura application redirect URI**
   
   In the Oura Developer Portal, update your application's redirect URI to match your Heroku app's callback URL.

## Troubleshooting

### Common Issues

1. **OAuth2 Redirect URI Mismatch**
   
   Ensure the redirect URI in your Oura Developer Portal exactly matches the one specified in your application.

2. **Database Connection Issues**
   
   Check your Supabase URL and API key. Verify the RLS policies are correctly set.

3. **Token Encryption Errors**
   
   If you change your `FERNET_KEY`, existing stored tokens will no longer be decryptable. You'll need to have users re-authenticate.

For more help, check the project's issue tracker or contact the maintainers. 