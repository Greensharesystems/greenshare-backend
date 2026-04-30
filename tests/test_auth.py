from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.auth import (
	AuthPrincipal,
	build_user_principal,
	can_access_customer_data,
	create_access_token,
	get_current_principal,
	has_shared_platform_access,
	resolve_access_token,
)
import app.core.auth as auth_module


def test_resolve_access_token_prefers_bearer_credentials() -> None:
	credentials = SimpleNamespace(scheme="Bearer", credentials="header-token")

	assert resolve_access_token(credentials, "query-token") == "header-token"


def test_get_current_principal_accepts_query_access_token(monkeypatch) -> None:
	principal = AuthPrincipal(
		email="employee@example.com",
		displayName="Employee User",
		identifier="EMP-001",
		accountType="user",
		role="employee",
		customerId=None,
	)
	token = create_access_token(principal)

	fake_user = SimpleNamespace(
		email="employee@example.com",
		first_name="Employee",
		last_name="User",
		user_id="EMP-001",
		role="employee",
		customer_id=None,
	)

	monkeypatch.setattr(auth_module, "get_user_by_user_id", lambda db, identifier: fake_user if identifier == "EMP-001" else None)

	resolved_principal = get_current_principal(credentials=None, access_token=token, db=None)

	assert resolved_principal.identifier == "EMP-001"
	assert resolved_principal.role == "employee"


def test_has_shared_platform_access_allows_admin_and_employee_only() -> None:
	admin_principal = AuthPrincipal(
		email="admin@example.com",
		displayName="Admin User",
		identifier="UID-0001",
		accountType="user",
		role="admin",
		customerId=None,
	)
	employee_principal = AuthPrincipal(
		email="employee@example.com",
		displayName="Employee User",
		identifier="UID-0002",
		accountType="user",
		role="employee",
		customerId=None,
	)
	customer_principal = AuthPrincipal(
		email="customer@example.com",
		displayName="Customer User",
		identifier="UID-0003",
		accountType="user",
		role="customer",
		customerId="CID-0001",
	)

	assert has_shared_platform_access(admin_principal) is True
	assert has_shared_platform_access(employee_principal) is True
	assert has_shared_platform_access(customer_principal) is False


def test_can_access_customer_data_keeps_customer_scoped_but_shares_admin_and_employee_access() -> None:
	employee_principal = AuthPrincipal(
		email="employee@example.com",
		displayName="Employee User",
		identifier="UID-0002",
		accountType="user",
		role="employee",
		customerId=None,
	)
	customer_principal = AuthPrincipal(
		email="customer@example.com",
		displayName="Customer User",
		identifier="UID-0003",
		accountType="user",
		role="customer",
		customerId="CID-0001",
	)

	assert can_access_customer_data(employee_principal, "CID-0001") is True
	assert can_access_customer_data(employee_principal, "CID-0002") is True
	assert can_access_customer_data(customer_principal, "CID-0001") is True
	assert can_access_customer_data(customer_principal, "CID-0002") is False


def test_build_user_principal_rejects_customer_user_without_linked_customer(monkeypatch) -> None:
	orphaned_user = SimpleNamespace(
		email="customer@example.com",
		first_name="Customer",
		last_name="User",
		user_id="UID-0003",
		role="Customer",
		customer_id="CID-0001",
	)

	monkeypatch.setattr(auth_module, "get_customer_by_customer_id", lambda db, customer_id: None)

	assert build_user_principal(db=None, user=orphaned_user) is None


def test_get_current_principal_rejects_deleted_user_token(monkeypatch) -> None:
	principal = AuthPrincipal(
		email="customer@example.com",
		displayName="Customer User",
		identifier="UID-0003",
		accountType="user",
		role="customer",
		customerId="CID-0001",
	)
	token = create_access_token(principal)

	monkeypatch.setattr(auth_module, "get_user_by_user_id", lambda db, identifier: None)

	with pytest.raises(HTTPException) as exc_info:
		get_current_principal(credentials=None, access_token=token, db=None)

	assert exc_info.value.status_code == 401


def test_get_current_principal_rejects_legacy_customer_account_type_token() -> None:
	legacy_principal = AuthPrincipal(
		email="customer@example.com",
		displayName="Customer User",
		identifier="CID-0001",
		accountType="customer",
		role="customer",
		customerId="CID-0001",
	)
	token = create_access_token(legacy_principal)

	with pytest.raises(HTTPException) as exc_info:
		get_current_principal(credentials=None, access_token=token, db=None)

	assert exc_info.value.status_code == 401


def test_get_current_principal_rejects_customer_user_token_when_customer_is_deleted(monkeypatch) -> None:
	principal = AuthPrincipal(
		email="customer@example.com",
		displayName="Customer User",
		identifier="UID-0003",
		accountType="user",
		role="customer",
		customerId="CID-0001",
	)
	token = create_access_token(principal)
	orphaned_user = SimpleNamespace(
		email="customer@example.com",
		first_name="Customer",
		last_name="User",
		user_id="UID-0003",
		role="Customer",
		customer_id="CID-0001",
	)

	monkeypatch.setattr(auth_module, "get_user_by_user_id", lambda db, identifier: orphaned_user)
	monkeypatch.setattr(auth_module, "get_customer_by_customer_id", lambda db, customer_id: None)

	with pytest.raises(HTTPException) as exc_info:
		get_current_principal(credentials=None, access_token=token, db=None)

	assert exc_info.value.status_code == 401