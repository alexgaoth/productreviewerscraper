"""Encryption utilities for securing sensitive data."""

from cryptography.fernet import Fernet
from app.config import settings


class EncryptionService:
    """Service for encrypting and decrypting sensitive data."""

    def __init__(self, key: str):
        """Initialize with encryption key."""
        self.fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext string."""
        if not plaintext:
            raise ValueError("Cannot encrypt empty string")
        encrypted_bytes = self.fernet.encrypt(plaintext.encode())
        return encrypted_bytes.decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt ciphertext string."""
        if not ciphertext:
            raise ValueError("Cannot decrypt empty string")
        decrypted_bytes = self.fernet.decrypt(ciphertext.encode())
        return decrypted_bytes.decode()


# Global encryption service
encryption_service = EncryptionService(settings.encryption_key)


def encrypt_refresh_token(refresh_token: str) -> str:
    """Encrypt a refresh token for storage."""
    return encryption_service.encrypt(refresh_token)


def decrypt_refresh_token(encrypted_token: str) -> str:
    """Decrypt a stored refresh token."""
    return encryption_service.decrypt(encrypted_token)
