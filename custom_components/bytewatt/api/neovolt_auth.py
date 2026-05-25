"""Authentication module for Neovolt API."""
from __future__ import annotations

import base64
import hashlib
import logging

from Crypto.Cipher import AES  # pycryptodome — declared in manifest.json

_LOGGER = logging.getLogger(__name__)


class EncryptionError(RuntimeError):
    """Raised when password encryption fails.

    Returning an empty string on failure (the old behaviour) was dangerous —
    the server rejects the "" password with a non-200 code, the login flow
    treats that as an auth error, and the plaintext form-data fallback then
    sends the user's password unencrypted. Raising forces every caller to
    handle the failure explicitly without ever leaking plaintext.
    """


def encrypt_password(password: str, username: str) -> str:
    """Encrypt the password using the Neovolt API protocol.

    AES-256-CBC with:
        Key: SHA-256(username) — 32 bytes
        IV:  MD5(username)     — 16 bytes (deterministic per the server's
                                 required protocol; not under our control)
        PKCS#7 padding to 16-byte blocks
        Base64 encoding of the ciphertext

    Raises:
        EncryptionError: if any step fails. Callers MUST NOT fall through
        to a plaintext path on this exception.
    """
    try:
        key = hashlib.sha256(username.encode("utf-8")).digest()
        iv = hashlib.md5(username.encode("utf-8")).digest()

        data = password.encode("utf-8")
        pad_len = AES.block_size - (len(data) % AES.block_size)
        data += bytes([pad_len]) * pad_len

        cipher = AES.new(key, AES.MODE_CBC, iv)
        ct = cipher.encrypt(data)
        return base64.b64encode(ct).decode("ascii")
    except Exception as exc:
        _LOGGER.error("Password encryption failed: %s", exc)
        raise EncryptionError(str(exc)) from exc
