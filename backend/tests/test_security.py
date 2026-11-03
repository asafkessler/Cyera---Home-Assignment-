import pytest
from cryptography.fernet import Fernet

from app.core.security import (
    CredentialCipher,
    generate_secret,
    hash_password,
    hash_secret,
    verify_password,
)


def test_password_roundtrip():
    h = hash_password("correct horse battery staple")
    assert h != "correct horse battery staple"
    assert verify_password("correct horse battery staple", h)
    assert not verify_password("wrong", h)


def test_same_password_hashes_differently_each_time():
    # bcrypt salts every hash, so equal passwords must not produce equal hashes
    assert hash_password("x") != hash_password("x")


def test_secrets_are_unique_and_hash_is_stable():
    a, b = generate_secret(), generate_secret()
    assert a != b
    assert hash_secret(a) == hash_secret(a)
    assert hash_secret(a) != hash_secret(b)


def test_cipher_roundtrip_and_key_binding():
    key = Fernet.generate_key().decode()
    cipher = CredentialCipher(key)
    token = cipher.encrypt("ATATT3xFfGF0-very-secret")
    assert token != "ATATT3xFfGF0-very-secret"
    assert cipher.decrypt(token) == "ATATT3xFfGF0-very-secret"

    other = CredentialCipher(Fernet.generate_key().decode())
    with pytest.raises(ValueError):
        other.decrypt(token)
