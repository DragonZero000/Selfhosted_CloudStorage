"""Unit tests for storage module."""
import os
import sys
import io
import pytest
from unittest.mock import patch, MagicMock, call
from datetime import datetime
from botocore.exceptions import ClientError

sys.path.insert(0, os.path.dirname(__file__))

# NOTE: mock_env, isolated_db and mock_s3_clients all come from conftest.py
# and apply automatically to every test in this file.


# ─── Helpers ────────────────────────────────────────────────────────────────

def _make_upload_file(name="test.txt", content=b"hello world", content_type="text/plain"):
    """Build a MagicMock that looks enough like FastAPI's UploadFile for the
    handful of tests that still call the router function directly instead of
    going through HTTP (kept only where HTTP-level testing brings no extra
    value, e.g. pure input-validation branches)."""
    mock_file = MagicMock()
    mock_file.filename = name
    mock_file.size = len(content)
    mock_file.content_type = content_type
    mock_file.file = io.BytesIO(content)
    return mock_file


class TestEnsureBucket:
    """Tests for _ensure_bucket function."""

    def test_ensure_bucket_creates_new(self, monkeypatch):
        import storage
        mock_s3 = MagicMock()
        mock_s3.list_buckets.return_value = {"Buckets": []}
        monkeypatch.setattr(storage, "s3", mock_s3)

        storage._ensure_bucket()
        mock_s3.create_bucket.assert_called_once_with(Bucket="test-bucket")

    def test_ensure_bucket_skips_existing(self, monkeypatch):
        import storage
        mock_s3 = MagicMock()
        mock_s3.list_buckets.return_value = {"Buckets": [{"Name": "test-bucket"}]}
        monkeypatch.setattr(storage, "s3", mock_s3)

        storage._ensure_bucket()
        mock_s3.create_bucket.assert_not_called()

    def test_ensure_bucket_handles_error(self, monkeypatch):
        import storage
        mock_s3 = MagicMock()
        mock_s3.list_buckets.side_effect = Exception("Connection error")
        monkeypatch.setattr(storage, "s3", mock_s3)

        # Should not raise, just print warning
        storage._ensure_bucket()


class TestGeneratePresignedUrl:
    """Tests for generate_presigned_url function."""

    def test_generate_presigned_url_success(self, monkeypatch):
        import storage
        mock_s3_public = MagicMock()
        mock_s3_public.generate_presigned_url.return_value = "https://presigned-url.example.com"
        monkeypatch.setattr(storage, "s3_public", mock_s3_public)

        url = storage.generate_presigned_url("test-key.txt", "test.txt")
        assert url == "https://presigned-url.example.com"

    def test_generate_presigned_url_returns_none_on_error(self, monkeypatch):
        import storage
        mock_s3_public = MagicMock()
        mock_s3_public.generate_presigned_url.side_effect = Exception("Error")
        monkeypatch.setattr(storage, "s3_public", mock_s3_public)

        url = storage.generate_presigned_url("test-key.txt", "test.txt")
        assert url is None


# ─── Auth enforcement across all /files endpoints ──────────────────────────
# These are the tests that were completely missing before: every /files/*
# route must reject requests with no token / an invalid token, exactly like
# /users/me does. Previously every "endpoint" test called the router
# function directly with a manually-constructed user, which never exercised
# FastAPI's Depends(get_current_user) wiring at all.

class TestFilesEndpointsRequireAuth:
    """Every /files/* route must be behind authentication."""

    @pytest.mark.parametrize(
        "method,path",
        [
            ("get", "/files"),
            ("get", "/files/download/1"),
            ("get", "/files/share/1"),
            ("delete", "/files/1"),
        ],
    )
    def test_rejects_missing_token(self, client, method, path):
        response = getattr(client, method)(path)
        assert response.status_code == 401

    @pytest.mark.parametrize(
        "method,path",
        [
            ("get", "/files"),
            ("get", "/files/download/1"),
            ("get", "/files/share/1"),
            ("delete", "/files/1"),
        ],
    )
    def test_rejects_invalid_token(self, client, method, path):
        response = getattr(client, method)(path, headers={"Authorization": "Bearer garbage.token.value"})
        assert response.status_code == 401

    def test_upload_rejects_missing_token(self, client):
        response = client.post("/files/upload", files={"file": ("a.txt", b"data", "text/plain")})
        assert response.status_code == 401

    def test_rename_rejects_missing_token(self, client):
        response = client.patch("/files/1/rename", params={"new_name": "x"})
        assert response.status_code == 401


# ─── /files (list) — real HTTP round trip ──────────────────────────────────

class TestListFilesEndpoint:
    """Tests for the /files GET endpoint, exercised over real HTTP so the
    actual `list_files` handler (not just db.get_user_files) is covered."""

    def test_list_files_empty_for_new_user(self, client, auth_headers):
        response = client.get("/files", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_list_files_returns_user_files(self, client, auth_headers, test_user_data):
        import db
        user = db.get_user_data(test_user_data["login"])
        db.insert_file(user.id, "file1.txt", f"{user.login}/file1.txt", 100)
        db.insert_file(user.id, "file2.txt", f"{user.login}/file2.txt", 200)

        response = client.get("/files", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        names = {f["file_name"] for f in data}
        assert names == {"file1.txt", "file2.txt"}
        assert all("file_size" in f and "uploaded_at" in f and "id" in f for f in data)

    def test_list_files_does_not_leak_other_users_files(self, client, auth_headers, test_user_data):
        import db
        db.insert_user_data("someoneelse", "hash", 1073741824)
        other = db.get_user_data("someoneelse")
        db.insert_file(other.id, "not_yours.txt", "someoneelse/not_yours.txt", 100)

        response = client.get("/files", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []


# ─── /files/upload — real HTTP round trip ──────────────────────────────────

class TestUploadFileEndpoint:
    """Tests for the /files/upload POST endpoint."""

    def test_upload_success(self, client, auth_headers, mock_s3_clients):
        mock_s3, _ = mock_s3_clients
        response = client.post(
            "/files/upload",
            headers=auth_headers,
            files={"file": ("hello.txt", b"hello world", "text/plain")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["file_name"] == "hello.txt"
        assert data["file_size"] == len(b"hello world")
        assert "file_id" in data
        mock_s3.upload_fileobj.assert_called_once()

    def test_upload_persists_file_record(self, client, auth_headers, test_user_data):
        import db
        client.post(
            "/files/upload",
            headers=auth_headers,
            files={"file": ("persisted.txt", b"1234567890", "text/plain")},
        )
        user = db.get_user_data(test_user_data["login"])
        files = db.get_user_files(user.id)
        assert len(files) == 1
        assert files[0].file_name == "persisted.txt"
        assert files[0].file_size == 10

    def test_upload_blocked_when_limit_zero(self, client, monkeypatch):
        """A user whose size_of_memory is 0 (blocked) must get 403, over real HTTP."""
        import db
        db.insert_user_data("blockeduser", db.get_password_hash("pass123"), 0)
        login = client.post("/token", data={"username": "blockeduser", "password": "pass123"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        response = client.post(
            "/files/upload",
            headers=headers,
            files={"file": ("x.txt", b"data", "text/plain")},
        )
        assert response.status_code == 403
        assert response.json()["detail"]["error"] == "storage_blocked"

    def test_upload_blocked_when_over_limit(self, client):
        import db
        db.insert_user_data("smalluser", db.get_password_hash("pass123"), 10)
        login = client.post("/token", data={"username": "smalluser", "password": "pass123"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        response = client.post(
            "/files/upload",
            headers=headers,
            files={"file": ("big.txt", b"this is definitely more than 10 bytes", "text/plain")},
        )
        assert response.status_code == 413
        detail = response.json()["detail"]
        assert detail["error"] == "storage_limit_exceeded"

    def test_upload_empty_file_uses_seek_tell_fallback(self, client, auth_headers):
        """When Starlette reports file.size == 0 (e.g. a genuinely empty
        file), the handler falls back to file.seek/tell to determine size.
        This must not crash and must report file_size == 0."""
        response = client.post(
            "/files/upload",
            headers=auth_headers,
            files={"file": ("empty.txt", b"", "text/plain")},
        )
        assert response.status_code == 200
        assert response.json()["file_size"] == 0

    def test_upload_s3_failure_returns_500(self, client, auth_headers, mock_s3_clients):
        """If the S3/MinIO upload itself fails, the API must surface a 500
        rather than silently creating a DB record for a file that was never
        actually stored."""
        mock_s3, _ = mock_s3_clients
        mock_s3.upload_fileobj.side_effect = Exception("MinIO is down")

        response = client.post(
            "/files/upload",
            headers=auth_headers,
            files={"file": ("fails.txt", b"data", "text/plain")},
        )
        assert response.status_code == 500

    def test_duplicate_filename_gets_unique_key(self, client, auth_headers, test_user_data):
        """Uploading a file with the same name twice must not collide on
        s3_key (which is unique in the DB) - the second upload should still
        succeed."""
        import db
        client.post(
            "/files/upload", headers=auth_headers,
            files={"file": ("dup.txt", b"first", "text/plain")},
        )
        response = client.post(
            "/files/upload", headers=auth_headers,
            files={"file": ("dup.txt", b"second-version", "text/plain")},
        )
        assert response.status_code == 200

        user = db.get_user_data(test_user_data["login"])
        files = db.get_user_files(user.id)
        assert len(files) == 2
        assert len({f.s3_key for f in files}) == 2  # keys must be distinct


# ─── /files/download/{id} ───────────────────────────────────────────────────

class TestDownloadEndpoint:
    """Tests for the /files/download/{file_id} GET endpoint."""

    def test_download_file_not_found(self, client, auth_headers):
        response = client.get("/files/download/999", headers=auth_headers)
        assert response.status_code == 404

    def test_download_success_streams_content(self, client, auth_headers, test_user_data, mock_s3_clients):
        import db
        mock_s3, _ = mock_s3_clients
        user = db.get_user_data(test_user_data["login"])
        f = db.insert_file(user.id, "dl.txt", f"{user.login}/dl.txt", 5)

        body = MagicMock()
        body.iter_chunks.return_value = iter([b"hello"])
        mock_s3.get_object.return_value = {
            "Body": body,
            "ContentType": "text/plain",
            "ContentLength": 5,
        }

        response = client.get(f"/files/download/{f.id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.content == b"hello"
        assert "attachment" in response.headers.get("content-disposition", "")

    def test_download_cannot_access_other_users_file(self, client, auth_headers):
        """A user must get 404 (not another user's data) when trying to
        download a file that belongs to someone else."""
        import db
        db.insert_user_data("filerowner", "hash", 1073741824)
        owner = db.get_user_data("filerowner")
        f = db.insert_file(owner.id, "secret.txt", "filerowner/secret.txt", 10)

        response = client.get(f"/files/download/{f.id}", headers=auth_headers)
        assert response.status_code == 404

    def test_download_s3_error_returns_500(self, client, auth_headers, test_user_data, mock_s3_clients):
        import db
        mock_s3, _ = mock_s3_clients
        user = db.get_user_data(test_user_data["login"])
        f = db.insert_file(user.id, "broken.txt", f"{user.login}/broken.txt", 5)
        mock_s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "missing"}}, "GetObject"
        )

        response = client.get(f"/files/download/{f.id}", headers=auth_headers)
        assert response.status_code == 500


# ─── /files/share/{id} ───────────────────────────────────────────────────────

class TestShareLinkEndpoint:
    """Tests for the /files/share/{file_id} GET endpoint."""

    def test_share_link_success(self, client, auth_headers, test_user_data, mock_s3_clients):
        import db
        _, mock_s3_public = mock_s3_clients
        mock_s3_public.generate_presigned_url.return_value = "https://example.com/presigned"
        user = db.get_user_data(test_user_data["login"])
        f = db.insert_file(user.id, "shareme.txt", f"{user.login}/shareme.txt", 100)

        response = client.get(f"/files/share/{f.id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["share_url"] == "https://example.com/presigned"

    def test_share_nonexistent_file(self, client, auth_headers):
        response = client.get("/files/share/999", headers=auth_headers)
        assert response.status_code == 404

    def test_share_link_failure_returns_500(self, client, auth_headers, test_user_data, mock_s3_clients):
        """If presigned URL generation fails, the endpoint must report 500,
        not silently return an empty/None share_url."""
        import db
        _, mock_s3_public = mock_s3_clients
        mock_s3_public.generate_presigned_url.side_effect = Exception("boom")
        user = db.get_user_data(test_user_data["login"])
        f = db.insert_file(user.id, "willfail.txt", f"{user.login}/willfail.txt", 100)

        response = client.get(f"/files/share/{f.id}", headers=auth_headers)
        assert response.status_code == 500


# ─── DELETE /files/{id} ──────────────────────────────────────────────────────

class TestDeleteFileEndpoint:
    """Tests for the /files/{file_id} DELETE endpoint."""

    def test_delete_file_success(self, client, auth_headers, test_user_data, mock_s3_clients):
        import db
        mock_s3, _ = mock_s3_clients
        user = db.get_user_data(test_user_data["login"])
        f = db.insert_file(user.id, "todelete.txt", f"{user.login}/todelete.txt", 100)

        response = client.delete(f"/files/{f.id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["msg"] == "File deleted successfully"
        mock_s3.delete_object.assert_called_once()
        assert db.get_file(f.id, user.id) is None

    def test_delete_nonexistent_file(self, client, auth_headers):
        response = client.delete("/files/999", headers=auth_headers)
        assert response.status_code == 404

    def test_delete_other_users_file_returns_404(self, client, auth_headers):
        import db
        db.insert_user_data("victim", "hash", 1073741824)
        victim = db.get_user_data("victim")
        f = db.insert_file(victim.id, "notyours.txt", "victim/notyours.txt", 100)

        response = client.delete(f"/files/{f.id}", headers=auth_headers)
        assert response.status_code == 404
        # File must still exist for its real owner
        assert db.get_file(f.id, victim.id) is not None

    def test_delete_db_failure_after_s3_success_returns_500(self, client, auth_headers, test_user_data, monkeypatch):
        """If S3 deletion succeeds but the DB record removal itself fails
        (e.g. a race condition), the API must still report 500, not a
        false-positive success."""
        import db
        user = db.get_user_data(test_user_data["login"])
        f = db.insert_file(user.id, "racy.txt", f"{user.login}/racy.txt", 100)

        monkeypatch.setattr(db, "delete_file_record", lambda file_id, user_id: False)

        response = client.delete(f"/files/{f.id}", headers=auth_headers)
        assert response.status_code == 500

    def test_delete_s3_error_returns_500_and_keeps_db_record(self, client, auth_headers, test_user_data, mock_s3_clients):
        """If deleting the object from S3 fails, we must not delete the DB
        record either - otherwise the file becomes permanently orphaned in
        storage with no way to retry the deletion."""
        import db
        mock_s3, _ = mock_s3_clients
        user = db.get_user_data(test_user_data["login"])
        f = db.insert_file(user.id, "stuck.txt", f"{user.login}/stuck.txt", 100)
        mock_s3.delete_object.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "boom"}}, "DeleteObject"
        )

        response = client.delete(f"/files/{f.id}", headers=auth_headers)
        assert response.status_code == 500
        assert db.get_file(f.id, user.id) is not None


# ─── PATCH /files/{id}/rename ────────────────────────────────────────────────

class TestRenameFileEndpoint:
    """Tests for the /files/{file_id}/rename PATCH endpoint."""

    def test_rename_file_success(self, client, auth_headers, test_user_data):
        import db
        user = db.get_user_data(test_user_data["login"])
        f = db.insert_file(user.id, "oldname.txt", f"{user.login}/oldname.txt", 100)

        response = client.patch(f"/files/{f.id}/rename", headers=auth_headers, params={"new_name": "newname.txt"})
        assert response.status_code == 200
        assert response.json()["new_name"] == "newname.txt"
        assert db.get_file(f.id, user.id).file_name == "newname.txt"

    def test_rename_empty_name_raises_error(self, client, auth_headers, test_user_data):
        import db
        user = db.get_user_data(test_user_data["login"])
        f = db.insert_file(user.id, "keep.txt", f"{user.login}/keep.txt", 100)

        response = client.patch(f"/files/{f.id}/rename", headers=auth_headers, params={"new_name": "   "})
        assert response.status_code == 400

    def test_rename_nonexistent_file(self, client, auth_headers):
        response = client.patch("/files/999/rename", headers=auth_headers, params={"new_name": "x.txt"})
        assert response.status_code == 404

    def test_rename_db_failure_returns_500(self, client, auth_headers, test_user_data, monkeypatch):
        """If the file is found but the DB rename itself fails, the API must
        report 500 rather than a false-positive success."""
        import db
        user = db.get_user_data(test_user_data["login"])
        f = db.insert_file(user.id, "racy.txt", f"{user.login}/racy.txt", 100)

        monkeypatch.setattr(db, "rename_file", lambda file_id, user_id, new_name: False)

        response = client.patch(f"/files/{f.id}/rename", headers=auth_headers, params={"new_name": "x.txt"})
        assert response.status_code == 500

    def test_rename_other_users_file_returns_404(self, client, auth_headers):
        import db
        db.insert_user_data("rvictim", "hash", 1073741824)
        victim = db.get_user_data("rvictim")
        f = db.insert_file(victim.id, "original.txt", "rvictim/original.txt", 100)

        response = client.patch(f"/files/{f.id}/rename", headers=auth_headers, params={"new_name": "hacked.txt"})
        assert response.status_code == 404
        assert db.get_file(f.id, victim.id).file_name == "original.txt"


class TestS3Configuration:
    """Tests for S3 client configuration."""

    def test_s3_clients_are_configured(self):
        import storage
        assert hasattr(storage, "s3")
        assert hasattr(storage, "s3_public")

    def test_bucket_is_set(self):
        import storage
        assert storage.BUCKET == "test-bucket"

    def test_router_prefix(self):
        import storage
        assert storage.router.prefix == "/files"

    def test_router_has_files_tag(self):
        import storage
        assert "files" in storage.router.tags
