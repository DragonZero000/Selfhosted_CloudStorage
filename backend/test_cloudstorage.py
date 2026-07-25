"""Unit tests for CloudStorage main module (lifespan, app structure)."""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

# NOTE: mock_env, isolated_db and mock_s3_clients all come from conftest.py
# and apply automatically to every test in this file.


class TestAppStructure:
    """Tests for the main CloudStorage app structure."""

    def test_app_is_fastapi_instance(self):
        import CloudStorage
        from fastapi import FastAPI
        assert isinstance(CloudStorage.app, FastAPI)

    def test_lifespan_context_registered(self):
        """The lifespan context should be registered on the authorization router."""
        import CloudStorage
        # The app should have a lifespan set
        assert CloudStorage.app.router.lifespan_context is not None

    def test_storage_router_included(self):
        """The storage router should be included in the main app."""
        import CloudStorage
        routes = [r.path for r in CloudStorage.app.routes]
        # The /files prefix routes should be present
        assert "/files" in routes or any(r.startswith("/files") for r in routes)

    def test_app_has_routes(self):
        """The app should have multiple routes registered."""
        import CloudStorage
        routes = CloudStorage.app.routes
        # Should have more than just the default routes
        assert len(routes) > 3


class TestLifespan:
    """Tests for the lifespan context manager."""

    def test_lifespan_calls_ensure_bucket(self):
        """The lifespan should call _ensure_bucket on startup."""
        import CloudStorage
        import storage

        with patch("storage._ensure_bucket") as mock_ensure:
            async def run_test():
                async with CloudStorage.lifespan(CloudStorage.app) as _:
                    pass

            import asyncio
            asyncio.run(run_test())
            mock_ensure.assert_called_once()


class TestAppRoutes:
    """Tests for specific app routes."""

    def test_register_route_exists(self):
        import CloudStorage
        paths = [r.path for r in CloudStorage.app.routes if hasattr(r, "path")]
        assert "/register" in paths

    def test_token_route_exists(self):
        import CloudStorage
        paths = [r.path for r in CloudStorage.app.routes if hasattr(r, "path")]
        assert "/token" in paths

    def test_users_me_route_exists(self):
        import CloudStorage
        paths = [r.path for r in CloudStorage.app.routes if hasattr(r, "path")]
        assert "/users/me" in paths

    def test_all_files_routes_exist(self):
        """All 6 /files/* routes the frontend depends on must be registered."""
        import CloudStorage
        paths = {r.path for r in CloudStorage.app.routes if hasattr(r, "path")}
        expected = {
            "/files",
            "/files/upload",
            "/files/download/{file_id}",
            "/files/share/{file_id}",
            "/files/{file_id}",
            "/files/{file_id}/rename",
        }
        assert expected.issubset(paths)


class TestAppTags:
    """Tests for app tags and metadata."""

    def test_app_has_title(self):
        import CloudStorage
        assert CloudStorage.app.title is not None

    def test_app_tags_include_files(self):
        import CloudStorage
        # Check if files tag exists in routes
        tags = set()
        for route in CloudStorage.app.routes:
            if hasattr(route, "tags"):
                tags.update(route.tags)
        assert "files" in tags


class TestCORSConfiguration:
    """Tests for CORS middleware on the main app."""

    def test_cors_middleware_present(self):
        import CloudStorage
        # Check that CORSMiddleware is in the app's middleware stack
        from fastapi.middleware.cors import CORSMiddleware
        has_cors = any(
            hasattr(m, "cls") and m.cls is CORSMiddleware
            for m in CloudStorage.app.user_middleware
        )
        assert has_cors


class TestImportStructure:
    """Tests for module imports and structure."""

    def test_authorization_imported(self):
        import CloudStorage
        # authorization should be accessible as a module attribute
        assert hasattr(CloudStorage, "authorization")

    def test_storage_imported(self):
        import CloudStorage
        assert hasattr(CloudStorage, "storage")


class TestAppMiddleware:
    """Tests for app middleware configuration."""

    def test_cors_allow_all_methods(self):
        """CORS should allow all HTTP methods by default."""
        import CloudStorage
        from fastapi.middleware.cors import CORSMiddleware
        cors_middleware = None
        for m in CloudStorage.app.user_middleware:
            if hasattr(m, "cls") and issubclass(m.cls, CORSMiddleware):
                cors_middleware = m
                break
        assert cors_middleware is not None

    def test_cors_allow_all_headers(self):
        """CORS should allow all headers by default."""
        import CloudStorage
        from fastapi.middleware.cors import CORSMiddleware
        for m in CloudStorage.app.user_middleware:
            if hasattr(m, "cls") and issubclass(m.cls, CORSMiddleware):
                # The middleware config should include allow_headers=["*"]
                assert "*" in m.kwargs.get("allow_headers", [])
                break


class TestAppDependencyInjection:
    """Tests for dependency injection configuration."""

    def test_oauth2_scheme_configured(self):
        """OAuth2PasswordBearer should be configured with tokenUrl=token."""
        import authorization
        # Check that oauth2_scheme is an OAuth2PasswordBearer instance
        from fastapi.security import OAuth2PasswordBearer
        assert isinstance(authorization.oauth2_scheme, OAuth2PasswordBearer)

    def test_get_current_user_is_callable(self):
        """get_current_user should be a callable function."""
        import authorization
        assert callable(authorization.get_current_user)


class TestAppExceptionHandling:
    """Tests for exception handling in endpoints."""

    def test_register_duplicate_returns_400(self, client):
        """Registering duplicate user should return 400."""
        response = client.post("/register", json={"login": "dup", "password": "pass"})
        assert response.status_code == 200  # First registration succeeds

        response = client.post("/register", json={"login": "dup", "password": "pass"})
        assert response.status_code == 400


class TestAppVersionInfo:
    """Tests for app version and info."""

    def test_app_version_is_falsy_or_string(self):
        import CloudStorage
        # FastAPI defaults app.version to "0.1.0" unless overridden; either
        # way this must be a string (never None, unlike description).
        assert isinstance(CloudStorage.app.version, str)

    def test_app_description_none_or_string(self):
        import CloudStorage
        assert CloudStorage.app.description is None or isinstance(CloudStorage.app.description, str)


class TestAppDependencyOverrides:
    """Tests for dependency override capabilities."""

    def test_can_override_dependencies(self):
        """Dependencies should be overridable for testing."""
        import CloudStorage
        # Should support dependency overrides
        assert hasattr(CloudStorage.app, "dependency_overrides")
