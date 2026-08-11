import pytest
from utils.security import is_safe_url, sanitize_credentials, sanitize_input, sanitize_url

def test_is_safe_url():
    assert is_safe_url("https://tldr.tech/ai") is True
    assert is_safe_url("http://127.0.0.1") is False
    assert is_safe_url("http://localhost") is False
    assert is_safe_url("http://192.168.1.50") is False
    assert is_safe_url("http://169.254.169.254") is False

def test_sanitize_credentials():
    assert sanitize_credentials("AIzaSyD1234567890_abcdefghijklmnopqrstuvw") == "GEMINI_API_KEY_MASKED"
    assert "BEARER_TOKEN_MASKED" in sanitize_credentials("Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")
    assert "PASSWORD_MASKED" in sanitize_credentials("password=super_secret")

def test_sanitize_input():
    assert sanitize_input("<script>alert(1)</script>hello") == "alert(1)hello"
    assert sanitize_input("normal text") == "normal text"

def test_sanitize_url():
    assert sanitize_url("https://example.com/some path") == "https://example.com/somepath"
    assert sanitize_url("javascript:alert(1)") == ""
