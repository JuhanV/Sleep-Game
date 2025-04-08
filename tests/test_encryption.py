"""Tests for token encryption functionality."""
import unittest
import os
import sys
import json
from unittest.mock import patch

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.app import encrypt_token, decrypt_token
from cryptography.fernet import Fernet

class TokenEncryptionTests(unittest.TestCase):
    """Test suite for token encryption functionality."""
    
    def setUp(self):
        """Set up test environment."""
        # Generate a test key
        self.test_key = Fernet.generate_key()
        # Create patch for env variable
        self.patcher = patch.dict('os.environ', {'FERNET_KEY': self.test_key.decode()})
        self.patcher.start()
        
    def tearDown(self):
        """Clean up after tests."""
        self.patcher.stop()
    
    def test_encrypt_decrypt_token(self):
        """Test that a token can be encrypted and then decrypted correctly."""
        # Sample token
        token = {
            'access_token': 'test_access_token',
            'refresh_token': 'test_refresh_token',
            'expires_in': 3600,
            'token_type': 'Bearer'
        }
        
        # Encrypt the token
        encrypted = encrypt_token(token)
        
        # Verify it's encrypted (should be different from original and in base64 format)
        self.assertNotEqual(encrypted, json.dumps(token))
        
        # Decrypt the token
        decrypted = decrypt_token(encrypted)
        
        # Verify the decrypted token matches the original
        self.assertEqual(decrypted, token)
    
    def test_decrypt_invalid_token(self):
        """Test that decrypting an invalid token returns None."""
        # Try to decrypt an invalid token
        result = decrypt_token('invalid_token_format')
        
        # Should return None on failure
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main() 