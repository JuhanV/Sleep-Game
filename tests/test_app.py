import unittest
import os
import sys
from unittest.mock import patch, MagicMock

# Add the src directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.app import app

class OuraAppTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        # Mock environment variables
        self.env_patcher = patch.dict('os.environ', {
            'FLASK_SECRET_KEY': 'test_secret_key',
            'SUPABASE_URL': 'https://example.supabase.co',
            'SUPABASE_KEY': 'test_supabase_key',
            'OURA_CLIENT_ID': 'test_client_id',
            'OURA_CLIENT_SECRET': 'test_client_secret',
            'OURA_REDIRECT_URI': 'http://localhost:5000/callback',
            'FERNET_KEY': 'dGVzdF9mZXJuZXRfa2V5X3RoYXRfaXNfMzJfYnl0ZXNfbG9uZ18='
        })
        self.env_patcher.start()
        
    def tearDown(self):
        self.env_patcher.stop()
    
    @patch('src.app.supabase')
    def test_index_route(self, mock_supabase):
        """Test that the index route returns the login page."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Connect Oura Ring', response.data)
    
    @patch('src.app.requests.post')
    def test_callback_with_no_code(self, mock_post):
        """Test that callback fails without an authorization code."""
        response = self.client.get('/callback')
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Authorization failed', response.data)
    
    @patch('src.app.requests.post')
    @patch('src.app.requests.get')
    @patch('src.app.supabase')
    @patch('src.app.login_user')
    def test_callback_successful(self, mock_login, mock_supabase, mock_get, mock_post):
        """Test a successful OAuth callback."""
        # Mock token response
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'access_token': 'test_access_token',
            'refresh_token': 'test_refresh_token'
        }
        
        # Mock user info response
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            'id': 'test_user_id',
            'email': 'test@example.com'
        }
        
        # Mock Supabase response for profile check
        mock_supabase.table().select().eq().execute.return_value.data = []
        
        # Mock Supabase response for profile creation
        profile_result = MagicMock()
        profile_result.data = [{'id': 'test_profile_id'}]
        mock_supabase.table().insert().execute.return_value = profile_result
        
        # Make request with code
        response = self.client.get('/callback?code=test_auth_code')
        
        # Redirects to dashboard on success
        self.assertEqual(response.status_code, 302)
        
        # Verify login was called
        mock_login.assert_called_once()
    
    @patch('src.app.current_user')
    def test_logout(self, mock_current_user):
        """Test logout functionality."""
        response = self.client.get('/logout')
        self.assertEqual(response.status_code, 302)  # Redirect to index

if __name__ == '__main__':
    unittest.main() 