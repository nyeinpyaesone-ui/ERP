from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.models import Permission, Role, User
from app.permissions_catalogue import ALL_PERMISSIONS
from app.routers import auth
from app.services.permissions import get_user_permissions, has_permission

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("default_role_exists", [True, False])
def test_registration_cannot_request_privileged_role(
    db: Mock, audit: Mock, monkeypatch: pytest.MonkeyPatch, default_role_exists: bool
) -> None:
    default_role = (
        Role(name="user", display_name="User") if default_role_exists else None
    )
    db.query.return_value.first.side_effect = [None, default_role]
    hash_password = Mock(return_value="hashed-password")
    monkeypatch.setattr(auth, "get_password_hash", hash_password)
    data = auth.UserCreate(
        email="new@example.com",
        password="test-password",
        full_name="New User",
        role="superadmin",
    )

    user = auth.register(data, db)

    assert user.role == "user"
    assert user.roles == ([default_role] if default_role_exists else [])
    assert user.hashed_password == "hashed-password"
    hash_password.assert_called_once_with("test-password")
    db.flush.assert_called_once_with()
    db.commit.assert_called_once_with()


def test_disabled_account_never_gets_token(
    db: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = User(id=9, is_active=False, hashed_password="hash")
    db.query.return_value.first.return_value = user
    monkeypatch.setattr(auth, "verify_password", Mock(return_value=True))
    token = Mock()
    monkeypatch.setattr(auth, "create_access_token", token)

    with pytest.raises(HTTPException) as error:
        auth.login(
            SimpleNamespace(username="user@example.com", password="password"), db
        )

    assert (error.value.status_code, error.value.detail) == (401, "Account disabled")
    assert user.last_login is None
    token.assert_not_called()
    db.commit.assert_not_called()


def test_active_account_logs_in(
    db: Mock, audit: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = User(id=9, role="user", is_active=True, hashed_password="hash")
    db.query.return_value.first.return_value = user
    monkeypatch.setattr(auth, "verify_password", Mock(return_value=True))
    token = Mock(return_value="synthetic-token")
    refresh = Mock(return_value="synthetic-refresh")
    monkeypatch.setattr(auth, "create_access_token", token)
    monkeypatch.setattr(auth, "create_refresh_token", refresh)
    result = auth.login(
        SimpleNamespace(username="user@example.com", password="password"), db
    )
    assert result == {
        "access_token": "synthetic-token",
        "token_type": "bearer",
        "refresh_token": "synthetic-refresh",
        "user": user,
    }
    token.assert_called_once_with({"sub": "9", "role": "user"})
    refresh.assert_called_once_with(9)
    assert user.last_login is not None


@pytest.mark.parametrize("roles", [None, [], ["manager", "unknown"]])
def test_user_update_preserves_protected_fields_and_syncs_roles(
    db: Mock, actor: SimpleNamespace, roles: list[str] | None
) -> None:
    original_role = Role(name="user", display_name="User")
    manager = Role(name="manager", display_name="Manager")
    user = User(
        id=7,
        role="user",
        hashed_password="original",
        email="old@example.com",
        full_name="Old",
        roles=[original_role],
    )
    db.query.return_value.first.side_effect = [user, manager, None]
    changes = {
        "full_name": "New",
        "id": 99,
        "role": "superadmin",
        "hashed_password": "replacement",
    }
    if roles is not None:
        changes["roles"] = roles

    result = auth.update_user(7, auth.UserUpdate(**changes), db, actor)

    assert result is user
    assert (user.id, user.role, user.hashed_password, user.email) == (
        7,
        "user",
        "original",
        "old@example.com",
    )
    assert user.full_name == "New"
    assert user.roles == (
        [original_role] if roles is None else ([manager] if roles else [])
    )
    db.commit.assert_called_once_with()


def test_user_update_missing_user_has_no_writes(
    db: Mock, actor: SimpleNamespace
) -> None:
    with pytest.raises(HTTPException) as error:
        auth.update_user(999, auth.UserUpdate(full_name="New"), db, actor)
    assert error.value.status_code == 404
    db.commit.assert_not_called()


def test_permission_helpers_return_synchronous_deduplicated_results(db: Mock) -> None:
    read = Permission(resource="contacts", action="read")
    write = Permission(resource="contacts", action="update")
    user = User(
        role="user",
        is_active=True,
        roles=[Role(permissions=[read]), Role(permissions=[read, write])],
    )
    assert set(get_user_permissions(user, db)) == {"contacts:read", "contacts:update"}
    assert has_permission(user, "contacts", "read", db) is True
    assert has_permission(user, "contacts", "delete", db) is False


@pytest.mark.parametrize("role", ["user", "superadmin"])
def test_permission_helpers_handle_empty_roles(db: Mock, role: str) -> None:
    user = User(role=role, is_active=True, roles=[])
    if role == "superadmin":
        assert set(get_user_permissions(user, db)) == set(ALL_PERMISSIONS)
    else:
        assert get_user_permissions(user, db) == []
    assert has_permission(user, "users", "delete", db) is (role == "superadmin")


def _decode_for_test(token: str):
    from app import auth as auth_core

    return auth_core.decode_token(token, expected_type=None)


def test_refresh_rotates_pair_and_revokes_old_jti(
    db: Mock, audit: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app import auth as auth_core
    from app.schemas.auth import TokenRefreshRequest

    user = User(id=9, role="user", is_active=True, hashed_password="hash")
    db.query.return_value.first.return_value = user
    spent_refresh = auth_core.create_refresh_token(9)
    old_jti = _decode_for_test(spent_refresh)["jti"]

    revoked: list[tuple[str, int]] = []
    monkeypatch.setattr(
        auth_core.token_store,
        "revoke",
        lambda jti, ttl: revoked.append((jti, ttl)) or True,
    )

    result = auth.refresh_tokens(TokenRefreshRequest(refresh_token=spent_refresh), db)

    access_claims = _decode_for_test(result["access_token"])
    assert access_claims["sub"] == "9" and access_claims["type"] == "access"
    new_refresh_claims = _decode_for_test(result["refresh_token"])
    assert new_refresh_claims["type"] == "refresh"
    assert new_refresh_claims["jti"] != old_jti
    assert revoked and revoked[0][0] == old_jti and revoked[0][1] > 0


def test_refresh_rejects_access_token_as_refresh(
    db: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app import auth as auth_core
    from app.schemas.auth import TokenRefreshRequest

    monkeypatch.setattr(auth_core.token_store, "is_revoked", lambda jti: False)
    access = auth_core.create_access_token({"sub": "9", "role": "user"})

    with pytest.raises(HTTPException) as error:
        auth.refresh_tokens(TokenRefreshRequest(refresh_token=access), db)
    assert (error.value.status_code, error.value.detail) == (401, "Invalid token type")
    db.query.assert_not_called()


def test_refresh_rejects_disabled_user(
    db: Mock, audit: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app import auth as auth_core
    from app.schemas.auth import TokenRefreshRequest

    user = User(id=9, role="user", is_active=False, hashed_password="hash")
    db.query.return_value.first.return_value = user
    monkeypatch.setattr(auth_core.token_store, "is_revoked", lambda jti: False)
    refresh = auth_core.create_refresh_token(9)

    with pytest.raises(HTTPException) as error:
        auth.refresh_tokens(TokenRefreshRequest(refresh_token=refresh), db)
    assert (error.value.status_code, error.value.detail) == (401, "Invalid token")


def test_logout_revokes_access_jti(
    db: Mock, audit: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app import auth as auth_core

    user = User(id=9, role="user", is_active=True, hashed_password="hash")
    access = auth_core.create_access_token({"sub": "9", "role": "user"})
    access_jti = _decode_for_test(access)["jti"]

    revoked: list[tuple[str, int]] = []
    monkeypatch.setattr(
        auth_core.token_store,
        "revoke",
        lambda jti, ttl: revoked.append((jti, ttl)) or True,
    )
    monkeypatch.setattr(auth_core.token_store, "is_revoked", lambda jti: False)

    result = auth.logout(access, user, db)

    assert result["revoked"] is True
    assert revoked and revoked[0][0] == access_jti
    # Revoked token must now be rejected by decode (store mocked, so check
    # that decode consults the store with this jti).
    queried: list[str] = []
    monkeypatch.setattr(
        auth_core.token_store, "is_revoked", lambda jti: queried.append(jti) or False
    )
    auth_core.decode_token(access)
    assert queried == [access_jti]
