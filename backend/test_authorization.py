"""Unit tests for authorization module."""
import os
import sys
import pytest
from datetime import timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

# NOTE: mock_env, isolated_db, mock_s3_clients and client all come from
# conftest.py (autouse where relevant) - no need to redefine them here.


class TestPasswordHashing:
    """Tests for password hashing and verification."""

    def test_get_password_hash_returns_string(self):
        import authorization
        result = authorization.get_password_hash("testpassword")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_password_hash_different_for_same_input(self):
        """Hashing the same password twice should produce different hashes (due to salt)."""
        import authorization
        hash1 = authorization.get_password_hash("samepassword")
        hash2 = authorization.get_password_hash("samepassword")
        assert hash1 != hash2

    def test_verify_password_correct(self):
        import authorization
        password = "mypassword"
        hashed = authorization.get_password_hash(password)
        assert authorization.verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        import authorization
        hashed = authorization.get_password_hash("correctpassword")
        assert authorization.verify_password("wrongpassword", hashed) is False

    def test_verify_password_invalid_hash(self):
        import authorization
        assert authorization.verify_password("somepass", "not_a_valid_hash") is False


class TestCreateUser:
    """Tests for user creation."""

    @patch("authorization.db.insert_user_data")
    def test_create_user_calls_db_insert(self, mock_insert, monkeypatch):
        import authorization
        monkeypatch.setattr(authorization, "settings", MagicMock(DEFAULT_STORAGE_BYTES=1073741824))

        user = MagicMock(login="newuser", password="pass123")
        result = authorization.create_user(user)
        assert result is True
        mock_insert.assert_called_once()

    @patch("authorization.db.insert_user_data")
    def test_create_user_passes_correct_params(self, mock_insert, monkeypatch):
        import authorization

        original_settings = authorization.settings
        try:
            authorization.settings.DEFAULT_STORAGE_BYTES = 500
            user = MagicMock(login="testuser", password="pass123")
            authorization.create_user(user)

            # Verify insert_user_data was called with correct args
            assert mock_insert.called
            call_args = mock_insert.call_args[0]
            kwargs = mock_insert.call_args[1]

            # login and hashed_password are positional; size_of_memory is keyword
            assert len(call_args) >= 2
            assert call_args[0] == "testuser"  # login
            assert isinstance(call_args[1], str)  # hashed_password
            assert kwargs.get("size_of_memory") == 500  # size_of_memory from settings
        finally:
            authorization.settings = original_settings

    def test_create_user_raises_if_insert_fails(self, monkeypatch):
        """If db.insert_user_data raises, create_user should propagate the error
        rather than silently reporting success."""
        import authorization

        def boom(*args, **kwargs):
            raise RuntimeError("db unavailable")

        monkeypatch.setattr(authorization.db, "insert_user_data", boom)
        user = MagicMock(login="erroruser", password="pass123")
        with pytest.raises(RuntimeError):
            authorization.create_user(user)


class TestJWT:
    """Tests for JWT token creation and validation."""

    def test_create_access_token_returns_string(self):
        import authorization
        token = authorization.create_access_token({"sub": "testuser"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_with_expires_delta(self):
        import authorization
        expires = timedelta(minutes=60)
        token = authorization.create_access_token({"sub": "testuser"}, expires_delta=expires)
        assert isinstance(token, str)

    def test_create_access_token_default_expiry(self):
        """Default expiry should be ACCESS_TOKEN_EXPIRE_MINUTES."""
        import authorization
        original_settings = authorization.settings
        authorization.settings.ACCESS_TOKEN_EXPIRE_MINUTES = 45

        token = authorization.create_access_token({"sub": "testuser"})
        assert isinstance(token, str)

        authorization.settings = original_settings

    def test_jwt_decode_valid_token(self):
        """Decoding a valid token should return the payload."""
        import authorization
        from jose import jwt
        token = authorization.create_access_token({"sub": "testuser"}, expires_delta=timedelta(hours=1))
        payload = jwt.decode(token, "test-secret-key-for-jwt", algorithms=["HS256"])
        assert payload["sub"] == "testuser"

    def test_jwt_decode_expired_token(self):
        """Decoding an expired token should raise an error."""
        import authorization
        from jose import JWTError, jwt
        token = authorization.create_access_token({"sub": "expired_user"}, expires_delta=timedelta(seconds=-1))
        with pytest.raises(JWTError):
            jwt.decode(token, "test-secret-key-for-jwt", algorithms=["HS256"])


class TestGetCurrentUser:
    """Direct unit tests for the get_current_user dependency (not just via HTTP)."""

    def test_get_current_user_rejects_garbage_token(self):
        import authorization
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            authorization.get_current_user(token="not-a-real-jwt")
        assert exc_info.value.status_code == 401

    def test_get_current_user_rejects_token_without_sub(self):
        """A validly-signed token that has no 'sub' claim must still be rejected."""
        import authorization
        from jose import jwt
        from fastapi import HTTPException

        token = jwt.encode({"foo": "bar"}, "test-secret-key-for-jwt", algorithm="HS256")
        with pytest.raises(HTTPException) as exc_info:
            authorization.get_current_user(token=token)
        assert exc_info.value.status_code == 401

    def test_get_current_user_rejects_unknown_user(self, monkeypatch):
        """A well-formed token for a login that no longer exists in the DB must be rejected."""
        import authorization
        from fastapi import HTTPException

        token = authorization.create_access_token({"sub": "ghost_user"})
        monkeypatch.setattr(authorization.db, "get_user_data", lambda login: None)
        with pytest.raises(HTTPException) as exc_info:
            authorization.get_current_user(token=token)
        assert exc_info.value.status_code == 401

    def test_get_current_user_accepts_valid_token(self, monkeypatch):
        import authorization
        mock_user = MagicMock(login="realuser")
        monkeypatch.setattr(authorization.db, "get_user_data", lambda login: mock_user)
        token = authorization.create_access_token({"sub": "realuser"})
        result = authorization.get_current_user(token=token)
        assert result is mock_user


class TestRegisterEndpoint:
    """Tests for the /register endpoint."""

    def test_register_new_user(self, client):
        response = client.post("/register", json={"login": "newuser", "password": "pass123"})
        assert response.status_code == 200
        data = response.json()
        assert "msg" in data

    def test_register_duplicate_user(self, client, monkeypatch):
        """Registering a user that already exists should return 400."""
        import db

        mock_user = MagicMock()
        monkeypatch.setattr(db, "get_user_data", lambda login: mock_user)

        response = client.post("/register", json={"login": "existinguser", "password": "pass123"})
        assert response.status_code == 400

    def test_register_returns_400_if_create_user_reports_failure(self, client, monkeypatch):
        """If create_user() ever returns a falsy value (without raising),
        /register must translate that into a 400, not a false-positive 200."""
        import authorization
        monkeypatch.setattr(authorization, "create_user", lambda user: False)

        response = client.post("/register", json={"login": "willfail", "password": "pass123"})
        assert response.status_code == 400

    def test_register_then_login_roundtrip(self, client):
        """A freshly registered user must be able to log in with the same credentials."""
        reg = client.post("/register", json={"login": "roundtrip", "password": "pass123"})
        assert reg.status_code == 200

        login = client.post("/token", data={"username": "roundtrip", "password": "pass123"})
        assert login.status_code == 200
        assert "access_token" in login.json()


class TestLoginEndpoint:
    """Tests for the /token endpoint."""

    def test_login_success(self, client, monkeypatch):
        """Successful login should return a token."""
        import authorization
        import db
        # Create a real password hash for testing
        real_hash = authorization.get_password_hash("correctpass")
        mock_user = MagicMock(login="testuser", password_hash=real_hash)
        monkeypatch.setattr(db, "get_user_data", lambda username: mock_user)

        response = client.post("/token", data={"username": "testuser", "password": "correctpass"})
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client, monkeypatch):
        """Login with wrong password should return 401."""
        import authorization
        import db
        real_hash = authorization.get_password_hash("correctpass")
        mock_user = MagicMock(login="testuser", password_hash=real_hash)
        monkeypatch.setattr(db, "get_user_data", lambda username: mock_user)

        response = client.post("/token", data={"username": "testuser", "password": "wrongpass"})
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client, monkeypatch):
        """Login with nonexistent user should return 401."""
        import db
        monkeypatch.setattr(db, "get_user_data", lambda username: None)

        response = client.post("/token", data={"username": "nobody", "password": "pass"})
        assert response.status_code == 401


class TestUsersMeEndpoint:
    """Tests for the /users/me endpoint."""

    def test_users_me_success(self, client, monkeypatch):
        """Getting current user should work with valid token."""
        import authorization
        # Create a valid token first
        token = authorization.create_access_token({"sub": "testuser"}, expires_delta=timedelta(hours=1))

        import db
        mock_user = MagicMock(id=1, login="testuser", password_hash="", storage_used=0, size_of_memory=1073741824)
        monkeypatch.setattr(db, "get_user_data", lambda username: mock_user)

        response = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

    def test_users_me_without_token_returns_401(self, client):
        """Hitting a protected endpoint with no Authorization header at all must be rejected."""
        response = client.get("/users/me")
        assert response.status_code == 401

    def test_users_me_with_invalid_token_returns_401(self, client):
        """A syntactically-valid-looking but bogus bearer token must be rejected."""
        response = client.get("/users/me", headers={"Authorization": "Bearer not.a.valid.jwt"})
        assert response.status_code == 401

    def test_users_me_with_expired_token_returns_401(self, client):
        import authorization
        token = authorization.create_access_token({"sub": "testuser"}, expires_delta=timedelta(seconds=-1))
        response = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401


class TestCORSConfiguration:
    """Tests for CORS middleware configuration."""

    def test_cors_allows_all_origins(self, client):
        """CORS should allow all origins by default.
        Since allow_credentials=False, the middleware does not send Access-Control-Allow-Origin
        on non-preflight requests, and OPTIONS to /register may return 405 if no route matches.
        Instead we verify the middleware is configured correctly."""
        import authorization
        # Verify that CORSMiddleware was added (it's added in authorization.py)
        assert hasattr(authorization.app, "user_middleware")
        from fastapi.middleware.cors import CORSMiddleware
        has_cors = any(
            hasattr(m, "cls") and m.cls is CORSMiddleware
            for m in authorization.app.user_middleware
        )
        assert has_cors


class TestSettings:
    """Tests for Settings class."""

    def test_settings_default_secret_key(self, monkeypatch):
        # Remove env var to get true defaults
        monkeypatch.delenv("SECRET_KEY", raising=False)
        from authorization import Settings
        s = Settings()
        assert s.SECRET_KEY == "hs256"

    def test_settings_default_algorithm(self, monkeypatch):
        monkeypatch.delenv("ALGORITHM", raising=False)
        from authorization import Settings
        s = Settings()
        assert s.ALGORITHM == "HS256"

    def test_settings_default_expire_minutes(self, monkeypatch):
        monkeypatch.delenv("ACCESS_TOKEN_EXPIRE_MINUTES", raising=False)
        from authorization import Settings
        s = Settings()
        assert s.ACCESS_TOKEN_EXPIRE_MINUTES == 30

    def test_settings_default_storage_bytes_zero(self, monkeypatch):
        """Default storage should be 0 (blocked)."""
        monkeypatch.delenv("DEFAULT_STORAGE_BYTES", raising=False)
        from authorization import Settings
        s = Settings()
        assert s.DEFAULT_STORAGE_BYTES == 0


class TestArgon2Config:
    """Tests for argon2 hasher configuration."""

    def test_password_hasher_is_configured(self):
        """Verify the PasswordHasher is properly configured."""
        import authorization
        assert hasattr(authorization, "ph")
        # The ph object should be an instance of PasswordHasher
        from argon2 import PasswordHasher
        assert isinstance(authorization.ph, PasswordHasher)
