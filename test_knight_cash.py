"""
test_knight_cash.py

Pytest suite for knight_cash_api.py — /transfer and /balance endpoints.

Generated per the Step 1 prompt:
"Generate a comprehensive Pytest suite for @knight_cash_api.py testing the
/transfer and /balance endpoints. Include the 'Happy Path' but focus heavily
on edge cases, negative tests, and boundary values using pytest.fixture
where appropriate."
"""
import pytest
from fastapi.testclient import TestClient

from knight_cash_api import app, accounts


@pytest.fixture(autouse=True)
def reset_accounts():
    """Reset the in-memory ledger to a known state before every test."""
    accounts.clear()
    accounts.update({
        "knight_001": 100.00,
        "knight_002": 50.00,
        "knight_003": 0.00,
    })
    yield


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /balance/{account_id}
# ---------------------------------------------------------------------------

class TestGetBalance:
    def test_happy_path_returns_correct_balance(self, client):
        # ARRANGE
        # ACT
        response = client.get("/balance/knight_001")
        # ASSERT
        assert response.status_code == 200
        assert response.json() == {"account_id": "knight_001", "balance": 100.00}

    def test_balance_of_zero_account(self, client):
        response = client.get("/balance/knight_003")
        assert response.status_code == 200
        assert response.json()["balance"] == 0.00

    def test_unknown_account_returns_404_not_500(self, client):
        # Edge case: nonexistent account must not blow up the server.
        response = client.get("/balance/knight_does_not_exist")
        assert response.status_code == 404

    def test_unknown_account_error_does_not_leak_internals(self, client):
        # Security: the error body must never expose the raw dict/traceback.
        response = client.get("/balance/knight_does_not_exist")
        body = response.text.lower()
        assert "traceback" not in body
        assert "keyerror" not in body
        assert "accounts[" not in body

    def test_empty_account_id_handled_gracefully(self, client):
        # Boundary: an empty path segment should not 500.
        response = client.get("/balance/")
        assert response.status_code in (404, 307, 308)


# ---------------------------------------------------------------------------
# POST /transfer
# ---------------------------------------------------------------------------

class TestTransferHappyPath:
    def test_valid_transfer_moves_funds(self, client):
        # ARRANGE
        payload = {"from_account": "knight_001", "to_account": "knight_002", "amount": 25.00}
        # ACT
        response = client.post("/transfer", json=payload)
        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert data["from_balance"] == 75.00
        assert data["to_balance"] == 75.00

    def test_transfer_entire_balance(self, client):
        payload = {"from_account": "knight_002", "to_account": "knight_001", "amount": 50.00}
        response = client.post("/transfer", json=payload)
        assert response.status_code == 200
        assert response.json()["from_balance"] == 0.00


class TestTransferNegativeAndBoundary:
    def test_negative_amount_is_rejected(self, client):
        # This is the classic "mint money" exploit.
        payload = {"from_account": "knight_001", "to_account": "knight_002", "amount": -50.00}
        response = client.post("/transfer", json=payload)
        assert response.status_code == 400

    def test_zero_amount_is_rejected(self, client):
        payload = {"from_account": "knight_001", "to_account": "knight_002", "amount": 0}
        response = client.post("/transfer", json=payload)
        assert response.status_code == 400

    def test_insufficient_funds_is_rejected(self, client):
        # knight_003 starts at 0.00 — this should never be allowed to go negative.
        payload = {"from_account": "knight_003", "to_account": "knight_001", "amount": 10.00}
        response = client.post("/transfer", json=payload)
        assert response.status_code == 400

    def test_transfer_exactly_full_balance_succeeds(self, client):
        # Boundary: amount == balance should succeed and leave exactly 0.
        payload = {"from_account": "knight_002", "to_account": "knight_001", "amount": 50.00}
        response = client.post("/transfer", json=payload)
        assert response.status_code == 200
        assert response.json()["from_balance"] == 0.00

    def test_transfer_one_cent_over_balance_fails(self, client):
        # Boundary: amount == balance + 0.01 should fail.
        payload = {"from_account": "knight_002", "to_account": "knight_001", "amount": 50.01}
        response = client.post("/transfer", json=payload)
        assert response.status_code == 400

    def test_self_transfer_is_rejected(self, client):
        # Transferring to yourself should be an explicit 400, not a silent no-op.
        payload = {"from_account": "knight_001", "to_account": "knight_001", "amount": 10.00}
        response = client.post("/transfer", json=payload)
        assert response.status_code == 400

    def test_unknown_from_account_returns_404(self, client):
        payload = {"from_account": "ghost_account", "to_account": "knight_001", "amount": 10.00}
        response = client.post("/transfer", json=payload)
        assert response.status_code == 404

    def test_unknown_to_account_returns_404(self, client):
        payload = {"from_account": "knight_001", "to_account": "ghost_account", "amount": 10.00}
        response = client.post("/transfer", json=payload)
        assert response.status_code == 404


class TestTransferTypeErrors:
    def test_string_amount_is_rejected(self, client):
        payload = {"from_account": "knight_001", "to_account": "knight_002", "amount": "fifty dollars"}
        response = client.post("/transfer", json=payload)
        assert response.status_code == 422  # FastAPI/Pydantic validation error

    def test_missing_field_is_rejected(self, client):
        payload = {"from_account": "knight_001", "amount": 10.00}
        response = client.post("/transfer", json=payload)
        assert response.status_code == 422

    def test_null_amount_is_rejected(self, client):
        payload = {"from_account": "knight_001", "to_account": "knight_002", "amount": None}
        response = client.post("/transfer", json=payload)
        assert response.status_code == 422


class TestTransferFloatingPointAndSecurity:
    def test_floating_point_precision_is_rounded(self, client):
        # 10.005 has no exact binary representation; result should be
        # rounded to 2 decimal places, not leak float dust.
        payload = {"from_account": "knight_001", "to_account": "knight_002", "amount": 10.005}
        response = client.post("/transfer", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert round(data["from_balance"], 2) == data["from_balance"]
        assert round(data["to_balance"], 2) == data["to_balance"]

    def test_error_response_does_not_leak_internal_state(self, client):
        payload = {"from_account": "knight_003", "to_account": "knight_001", "amount": 999999.00}
        response = client.post("/transfer", json=payload)
        body = response.text.lower()
        assert "traceback" not in body
        assert "accounts[" not in body
