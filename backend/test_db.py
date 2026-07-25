"""Unit tests for db module."""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

# NOTE: mock_env and isolated_db (in-memory SQLite + schema) come from
# conftest.py and are applied automatically to every test in this file.


class TestPasswordHashing:
    """Tests for password hashing in db module."""

    def test_get_password_hash_returns_string(self):
        import db
        result = db.get_password_hash("testpassword")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_password_hash_different_for_same_input(self):
        """Hashing the same password twice should produce different hashes."""
        import db
        hash1 = db.get_password_hash("samepassword")
        hash2 = db.get_password_hash("samepassword")
        assert hash1 != hash2


class TestUserCRUD:
    """Tests for User CRUD operations."""

    def test_insert_user_data(self, db_session):
        import db
        db.insert_user_data("testuser", "hashedpass", 1073741824)
        user = db.get_user_data("testuser")
        assert user is not None
        assert user.login == "testuser"
        assert user.password_hash == "hashedpass"
        assert user.size_of_memory == 1073741824

    def test_insert_user_data_defaults_storage_used_to_zero(self, db_session):
        import db
        db.insert_user_data("freshuser", "hash", 1000)
        user = db.get_user_data("freshuser")
        assert user.storage_used == 0

    def test_insert_user_data_rolls_back_on_duplicate_login(self, db_session):
        """Inserting a user with a login that already exists must raise
        (login is unique) and must not leave a half-committed row behind."""
        import db
        db.insert_user_data("dupelogin", "hash1", 100)
        with pytest.raises(Exception):
            db.insert_user_data("dupelogin", "hash2", 200)

        # The original user must be untouched by the failed second insert.
        user = db.get_user_data("dupelogin")
        assert user.password_hash == "hash1"

    def test_get_user_data_returns_none_for_nonexistent(self):
        import db
        result = db.get_user_data("nonexistent")
        assert result is None

    def test_get_users_data_empty(self):
        """Should return empty list when no users exist."""
        import db
        result = db.get_users_data()
        assert isinstance(result, list)
        assert len(result) == 0

    def test_get_users_data_after_insert(self, db_session):
        import db
        db.insert_user_data("user1", "hash1", 500)
        db.insert_user_data("user2", "hash2", 600)
        users = db.get_users_data()
        assert len(users) == 2

    def test_delete_user_data(self, db_session):
        import db
        db.insert_user_data("todelete", "hash", 100)
        # Mock input to confirm deletion
        with patch("builtins.input", return_value="y"):
            db.delete_user_data("todelete")
        result = db.get_user_data("todelete")
        assert result is None

    def test_delete_user_data_not_found(self):
        """Deleting non-existent user should not raise error."""
        import db
        with patch("builtins.input", return_value="y"):
            db.delete_user_data("nonexistent")  # Should not raise

    def test_delete_user_data_declined_keeps_user(self, db_session):
        """If the operator answers anything other than 'y', the user must survive."""
        import db
        db.insert_user_data("keepme", "hash", 100)
        with patch("builtins.input", return_value="n"):
            db.delete_user_data("keepme")
        assert db.get_user_data("keepme") is not None

    def test_delete_user_data_empty_input_defaults_to_no(self, db_session):
        """An empty response at the confirmation prompt must default to 'no',
        not silently delete the user."""
        import db
        db.insert_user_data("emptyresponse", "hash", 100)
        with patch("builtins.input", return_value=""):
            db.delete_user_data("emptyresponse")
        assert db.get_user_data("emptyresponse") is not None

    def test_update_user_storage_positive_delta(self, db_session):
        import db
        db.insert_user_data("updater", "hash", 1000)
        user = db.get_user_data("updater")
        db.update_user_storage(user.id, 500)
        updated = db.get_user_data("updater")
        assert updated.storage_used == 500

    def test_update_user_storage_negative_delta(self, db_session):
        import db
        db.insert_user_data("reducer", "hash", 1000)
        user = db.get_user_data("reducer")
        # First add some storage used
        db.update_user_storage(user.id, 300)
        # Then reduce it
        db.update_user_storage(user.id, -100)
        updated = db.get_user_data("reducer")
        assert updated.storage_used == 200

    def test_update_user_storage_no_negative(self, db_session):
        """Storage used should not go below 0."""
        import db
        db.insert_user_data("negative_test", "hash", 100)
        user = db.get_user_data("negative_test")
        # Try to reduce below 0
        db.update_user_storage(user.id, -200)
        updated = db.get_user_data("negative_test")
        assert updated.storage_used == 0

    def test_update_user_storage_nonexistent_user_is_noop(self):
        """Calling update_user_storage for a user id that doesn't exist must
        not raise - it should just do nothing."""
        import db
        db.update_user_storage(999999, 500)  # should not raise

    def test_update_user_storage_swallows_commit_errors(self, db_session, monkeypatch):
        """If the commit itself fails (e.g. lost DB connection), the function
        must roll back and swallow the error rather than crash the caller."""
        import db
        from sqlalchemy.orm import Session

        db.insert_user_data("commitfail", "hash", 1000)
        user = db.get_user_data("commitfail")

        def failing_commit(self):
            raise RuntimeError("connection lost")

        monkeypatch.setattr(Session, "commit", failing_commit)
        db.update_user_storage(user.id, 100)  # must not raise

    def test_update_user_by_login(self, db_session):
        import db
        db.insert_user_data("loginupdater", "hash", 1000)
        result = db.update_user_by_login("loginupdater", size_of_memory=2000)
        assert result is True
        user = db.get_user_data("loginupdater")
        assert user.size_of_memory == 2000

    def test_update_user_by_login_not_found(self):
        """Updating non-existent user should return False."""
        import db
        result = db.update_user_by_login("nonexistent", size_of_memory=100)
        assert result is False

    def test_update_user_by_login_unknown_field_is_ignored(self, db_session):
        """Fields that don't exist on the User model must be silently ignored,
        not raise an AttributeError."""
        import db
        db.insert_user_data("unknownfield", "hash", 100)
        result = db.update_user_by_login("unknownfield", not_a_real_field="x")
        assert result is True

    def test_update_user_by_login_returns_false_on_commit_error(self, db_session, monkeypatch):
        """A DB error during update_user_by_login must be caught, rolled back,
        and reported as a False return value rather than propagating."""
        import db
        from sqlalchemy.orm import Session

        db.insert_user_data("updatecommitfail", "hash", 1000)

        def failing_commit(self):
            raise RuntimeError("connection lost")

        monkeypatch.setattr(Session, "commit", failing_commit)
        result = db.update_user_by_login("updatecommitfail", size_of_memory=999)
        assert result is False

    def test_protected_fields_cannot_be_updated(self, db_session):
        """Protected fields (id, storage_used, files) cannot be changed via update_user_by_login."""
        import db
        db.insert_user_data("protected", "hash", 1000)
        # Try to change protected field
        result = db.update_user_by_login("protected", id=999, storage_used=500)
        assert result is True
        user = db.get_user_data("protected")
        assert user.id != 999  # Should remain original
        assert user.storage_used == 0  # storage_used must also remain untouched


class TestFileCRUD:
    """Tests for File CRUD operations."""

    def test_insert_file(self, db_session):
        import db
        db.insert_user_data("fileuser", "hash", 1073741824)
        user = db.get_user_data("fileuser")
        file_record = db.insert_file(user.id, "test.txt", "fileuser/test.txt", 100)
        assert file_record is not None
        assert file_record.file_name == "test.txt"
        assert file_record.s3_key == "fileuser/test.txt"
        assert file_record.file_size == 100

    def test_insert_file_updates_storage_used(self, db_session):
        import db
        db.insert_user_data("storageuser", "hash", 1073741824)
        user = db.get_user_data("storageuser")
        initial_used = user.storage_used
        db.insert_file(user.id, "file.txt", "storageuser/file.txt", 500)
        updated = db.get_user_data("storageuser")
        assert updated.storage_used == initial_used + 500

    def test_insert_file_rolls_back_on_duplicate_s3_key(self, db_session):
        """s3_key is unique; a duplicate insert must raise and must not have
        double-counted storage_used for the user."""
        import db
        db.insert_user_data("dupekey", "hash", 1073741824)
        user = db.get_user_data("dupekey")
        db.insert_file(user.id, "a.txt", "dupekey/same-key", 100)

        with pytest.raises(Exception):
            db.insert_file(user.id, "b.txt", "dupekey/same-key", 200)

        updated = db.get_user_data("dupekey")
        assert updated.storage_used == 100  # only the first insert counted

    def test_get_user_files(self, db_session):
        import db
        db.insert_user_data("listfiles", "hash", 1073741824)
        user = db.get_user_data("listfiles")
        db.insert_file(user.id, "file1.txt", "listfiles/file1.txt", 100)
        db.insert_file(user.id, "file2.txt", "listfiles/file2.txt", 200)
        files = db.get_user_files(user.id)
        assert len(files) == 2

    def test_get_user_files_only_returns_own_files(self, db_session):
        """A user must never see another user's files from get_user_files."""
        import db
        db.insert_user_data("owner", "hash", 1073741824)
        db.insert_user_data("other", "hash", 1073741824)
        owner = db.get_user_data("owner")
        other = db.get_user_data("other")
        db.insert_file(owner.id, "mine.txt", "owner/mine.txt", 100)
        db.insert_file(other.id, "theirs.txt", "other/theirs.txt", 100)

        files = db.get_user_files(owner.id)
        assert len(files) == 1
        assert files[0].file_name == "mine.txt"

    def test_get_file(self, db_session):
        import db
        db.insert_user_data("getfileuser", "hash", 1073741824)
        user = db.get_user_data("getfileuser")
        file_record = db.insert_file(user.id, "target.txt", "getfileuser/target.txt", 300)
        retrieved = db.get_file(file_record.id, user.id)
        assert retrieved is not None
        assert retrieved.file_name == "target.txt"

    def test_get_file_not_found(self):
        """Getting non-existent file should return None."""
        import db
        result = db.get_file(999, 1)
        assert result is None

    def test_get_file_wrong_owner_returns_none(self, db_session):
        """A file must not be retrievable by a user who doesn't own it -
        this is the DB-level enforcement of per-user file isolation."""
        import db
        db.insert_user_data("owner2", "hash", 1073741824)
        db.insert_user_data("intruder", "hash", 1073741824)
        owner = db.get_user_data("owner2")
        intruder = db.get_user_data("intruder")
        file_record = db.insert_file(owner.id, "secret.txt", "owner2/secret.txt", 100)

        result = db.get_file(file_record.id, intruder.id)
        assert result is None

    def test_delete_file_record(self, db_session):
        import db
        db.insert_user_data("deletefileuser", "hash", 1073741824)
        user = db.get_user_data("deletefileuser")
        file_record = db.insert_file(user.id, "todelete.txt", "deletefileuser/todelete.txt", 150)
        result = db.delete_file_record(file_record.id, user.id)
        assert result is True

    def test_delete_file_record_updates_storage(self, db_session):
        import db
        db.insert_user_data("storagefilereducer", "hash", 1073741824)
        user = db.get_user_data("storagefilereducer")
        file_record = db.insert_file(user.id, "reducer.txt", "storagefilereducer/reducer.txt", 500)
        # Re-read user to get updated storage_used after insert_file
        updated_user = db.get_user_data("storagefilereducer")
        initial_used = updated_user.storage_used
        db.delete_file_record(file_record.id, user.id)
        final = db.get_user_data("storagefilereducer")
        assert final.storage_used == initial_used - 500

    def test_delete_file_record_wrong_owner_fails(self, db_session):
        """Deleting a file by id while passing another user's id must fail
        (return False) and must not remove the file or touch its owner's storage."""
        import db
        db.insert_user_data("realowner", "hash", 1073741824)
        db.insert_user_data("attacker", "hash", 1073741824)
        owner = db.get_user_data("realowner")
        attacker = db.get_user_data("attacker")
        file_record = db.insert_file(owner.id, "mine.txt", "realowner/mine.txt", 100)

        result = db.delete_file_record(file_record.id, attacker.id)
        assert result is False
        # File must still exist for the real owner
        assert db.get_file(file_record.id, owner.id) is not None

    def test_delete_nonexistent_file(self):
        """Deleting non-existent file should return False."""
        import db
        result = db.delete_file_record(999, 1)
        assert result is False

    def test_delete_file_record_returns_false_on_commit_error(self, db_session, monkeypatch):
        """If the delete-and-commit fails partway through, the function must
        roll back and return False instead of raising."""
        import db
        from sqlalchemy.orm import Session

        db.insert_user_data("deletecommitfail", "hash", 1073741824)
        user = db.get_user_data("deletecommitfail")
        f = db.insert_file(user.id, "x.txt", "deletecommitfail/x.txt", 100)

        def failing_commit(self):
            raise RuntimeError("connection lost")

        monkeypatch.setattr(Session, "commit", failing_commit)
        result = db.delete_file_record(f.id, user.id)
        assert result is False

    def test_rename_file(self, db_session):
        import db
        db.insert_user_data("renameuser", "hash", 1073741824)
        user = db.get_user_data("renameuser")
        file_record = db.insert_file(user.id, "oldname.txt", "renameuser/oldname.txt", 100)
        result = db.rename_file(file_record.id, user.id, "newname.txt")
        assert result is True
        updated = db.get_file(file_record.id, user.id)
        assert updated.file_name == "newname.txt"

    def test_rename_nonexistent_file(self):
        """Renaming non-existent file should return False."""
        import db
        result = db.rename_file(999, 1, "newname.txt")
        assert result is False

    def test_rename_file_returns_false_on_commit_error(self, db_session, monkeypatch):
        """If the commit fails, rename_file must roll back and return False."""
        import db
        from sqlalchemy.orm import Session

        db.insert_user_data("renamecommitfail", "hash", 1073741824)
        user = db.get_user_data("renamecommitfail")
        f = db.insert_file(user.id, "old.txt", "renamecommitfail/old.txt", 100)

        def failing_commit(self):
            raise RuntimeError("connection lost")

        monkeypatch.setattr(Session, "commit", failing_commit)
        result = db.rename_file(f.id, user.id, "new.txt")
        assert result is False

    def test_rename_file_wrong_owner_fails(self, db_session):
        import db
        db.insert_user_data("owner3", "hash", 1073741824)
        db.insert_user_data("notowner", "hash", 1073741824)
        owner = db.get_user_data("owner3")
        notowner = db.get_user_data("notowner")
        file_record = db.insert_file(owner.id, "keep.txt", "owner3/keep.txt", 100)

        result = db.rename_file(file_record.id, notowner.id, "hacked.txt")
        assert result is False
        assert db.get_file(file_record.id, owner.id).file_name == "keep.txt"


class TestFmt:
    """Tests for the _fmt helper function."""

    def test_fmt_zero_bytes(self):
        import db
        assert db._fmt(0) == "0 B"

    def test_fmt_negative_bytes(self):
        import db
        assert db._fmt(-1) == "-1 B"

    def test_fmt_bytes(self):
        import db
        assert db._fmt(500) == "500 B"

    def test_fmt_kilobytes(self):
        import db
        result = db._fmt(2048)
        assert "KB" in result

    def test_fmt_megabytes(self):
        import db
        result = db._fmt(1048576)
        assert "MB" in result

    def test_fmt_gigabytes(self):
        import db
        result = db._fmt(1073741824)
        assert "GB" in result


class TestDatabaseModels:
    """Tests for database model definitions."""

    def test_user_model_attributes(self):
        import db
        from db import User
        assert hasattr(User, 'login')
        assert hasattr(User, 'password_hash')
        assert hasattr(User, 'storage_used')
        assert hasattr(User, 'size_of_memory')
        assert hasattr(User, 'files')

    def test_file_model_attributes(self):
        import db
        from db import File
        assert hasattr(File, 'user_id')
        assert hasattr(File, 'file_name')
        assert hasattr(File, 's3_key')
        assert hasattr(File, 'file_size')


class TestLazyEngineInitialization:
    """Tests for the lazy engine/SessionLocal creation path in db._get_session().

    Every other test in this suite runs with db.engine / db.SessionLocal
    already monkeypatched to a ready-made in-memory SQLite engine (see the
    autouse `isolated_db` fixture in conftest.py), so `_get_session()` never
    actually has to create anything itself. This test simulates the
    "nothing has touched the DB yet" state directly to exercise that
    lazy-creation branch, and confirms it both creates a working engine and
    creates the schema via Base.metadata.create_all.
    """

    def test_get_session_creates_engine_when_not_set(self, monkeypatch):
        import db
        monkeypatch.setattr(db, "engine", None)
        monkeypatch.setattr(db, "SessionLocal", None)
        monkeypatch.setattr(db, "DATABASE_URL", "sqlite:///:memory:")

        session = db._get_session()
        try:
            assert db.engine is not None
            assert db.SessionLocal is not None
            # Base.metadata.create_all should have run, so querying should
            # succeed (not raise "no such table") even though we never
            # called create_all ourselves in this test.
            assert session.query(db.User).count() == 0
        finally:
            session.close()

    def test_get_session_reuses_existing_session_local(self, monkeypatch):
        """If db.SessionLocal is already set (as tests normally leave it),
        _get_session() must not recreate the engine, and must just use it."""
        import db
        sentinel_session = MagicMock()
        sentinel_factory = MagicMock(return_value=sentinel_session)
        monkeypatch.setattr(db, "SessionLocal", sentinel_factory)

        result = db._get_session()
        assert result is sentinel_session
        sentinel_factory.assert_called_once()


class TestDatabaseURL:
    """Tests for database URL configuration."""

    def test_database_url_default(self):
        import db
        # Should have a default value
        assert "postgresql" in db.DATABASE_URL or "sqlite" in db.DATABASE_URL

    def test_engine_is_created(self):
        import db
        assert db.engine is not None

    def test_session_local_is_created(self):
        import db
        assert db.SessionLocal is not None
