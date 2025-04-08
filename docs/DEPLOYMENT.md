# Deployment Guide

This guide provides instructions for deploying the Oura Ring Data Comparison application in various environments.

## Local Development Deployment

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration values
   ```

5. Generate a Fernet key (if not already done):
   ```bash
   python src/generate_key.py
   # Add the generated key to your .env file
   ```

6. Run the application:
   ```bash
   python src/app.py
   ```

## Production Deployment on Linux Server

### Prerequisites
- Ubuntu 20.04 or similar Linux distribution
- Python 3.8+
- Nginx
- Supervisor or systemd
- Let's Encrypt (for SSL)

### Steps

1. Deploy code:
   ```bash
   git clone <repository-url> /var/www/oura-app
   cd /var/www/oura-app
   ```

2. Set up virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with production values
   # Make sure to use secure keys and change OURA_REDIRECT_URI to your domain
   ```

4. Set up Gunicorn:
   ```bash
   pip install gunicorn
   ```

5. Create systemd service file at `/etc/systemd/system/oura-app.service`:
   ```
   [Unit]
   Description=Oura Ring Data Comparison App
   After=network.target
   
   [Service]
   User=www-data
   Group=www-data
   WorkingDirectory=/var/www/oura-app
   Environment="PATH=/var/www/oura-app/venv/bin"
   ExecStart=/var/www/oura-app/venv/bin/gunicorn --workers 3 --bind unix:oura-app.sock -m 007 src.app:app
   
   [Install]
   WantedBy=multi-user.target
   ```

6. Start and enable the service:
   ```bash
   sudo systemctl start oura-app
   sudo systemctl enable oura-app
   ```

7. Configure Nginx by creating `/etc/nginx/sites-available/oura-app`:
   ```
   server {
       listen 80;
       server_name yourdomain.com;
   
       location / {
           include proxy_params;
           proxy_pass http://unix:/var/www/oura-app/oura-app.sock;
       }
   }
   ```

8. Enable the Nginx site:
   ```bash
   sudo ln -s /etc/nginx/sites-available/oura-app /etc/nginx/sites-enabled
   sudo nginx -t
   sudo systemctl restart nginx
   ```

9. Set up SSL with Let's Encrypt:
   ```bash
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d yourdomain.com
   ```

## Deployment on Heroku

1. Create a `Procfile` in the project root:
   ```
   web: gunicorn src.app:app
   ```

2. Add `gunicorn` to requirements.txt:
   ```bash
   echo "gunicorn>=20.1.0" >> requirements.txt
   ```

3. Create a `runtime.txt` file:
   ```
   python-3.9.16
   ```

4. Login to Heroku and create a new app:
   ```bash
   heroku login
   heroku create oura-data-comparison
   ```

5. Configure environment variables:
   ```bash
   heroku config:set FLASK_SECRET_KEY=<your-secret-key>
   heroku config:set SUPABASE_URL=<your-supabase-url>
   heroku config:set SUPABASE_KEY=<your-supabase-key>
   heroku config:set OURA_CLIENT_ID=<your-oura-client-id>
   heroku config:set OURA_CLIENT_SECRET=<your-oura-client-secret>
   heroku config:set OURA_REDIRECT_URI=https://<your-app-name>.herokuapp.com/callback
   heroku config:set FERNET_KEY=<your-fernet-key>
   ```

6. Deploy to Heroku:
   ```bash
   git push heroku main
   ```

7. Update your Oura application redirect URI in the Oura Developer Portal to match your Heroku app URL.

## Important Notes

1. Always use HTTPS in production to protect sensitive data.

2. Keep your `.env` file and especially the `FERNET_KEY` secure. If you change the `FERNET_KEY`, existing tokens will no longer be decryptable.

3. Regularly backup your Supabase database.

4. For high-traffic applications, consider horizontal scaling and load balancing.

5. Monitor server resources and application performance.

6. In the Oura Developer Portal, make sure to update the redirect URI to match your production domain. 