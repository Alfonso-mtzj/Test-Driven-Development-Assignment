"""
KnightCash API — v2 (fixed)

A tiny in-memory banking API for UCF students.
Endpoints:
    GET  /balance/{account_id}
    POST /transfer
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="KnightCash API")

# In-memory "database" of student wallets
accounts = {
    "knight_001": 100.00,
    "knight_002": 50.00,
    "knight_003": 0.00,
}


class TransferRequest(BaseModel):
    from_account: str
    to_account: str
    amount: float


@app.get("/balance/{account_id}")
def get_balance(account_id: str):
    if account_id not in accounts:
        # Fix (Bug #3 — data leakage): return a clean 404 instead of
        # letting a raw KeyError bubble up into a 500 traceback that
        # exposes the shape of the in-memory ledger.
        raise HTTPException(status_code=404, detail="Account not found")

    balance = accounts[account_id]
    return {"account_id": account_id, "balance": round(balance, 2)}


@app.post("/transfer")
def transfer(req: TransferRequest):
    # Fix (Bug #1 — money minting): reject non-positive amounts. A
    # "transfer" of $0 or less can never move real value, and a
    # negative amount would otherwise let a user mint funds by
    # subtracting a negative number from their own balance.
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than 0")

    if req.from_account == req.to_account:
        raise HTTPException(status_code=400, detail="Cannot transfer to the same account")

    if req.from_account not in accounts:
        raise HTTPException(status_code=404, detail="Sending account not found")
    if req.to_account not in accounts:
        raise HTTPException(status_code=404, detail="Receiving account not found")

    # Fix (Bug #2 — infinite overdraft): reject transfers that exceed
    # the sender's available balance. Compare against a rounded value
    # so a fractional cent of float noise doesn't wrongly block a
    # "transfer full balance" request.
    if round(req.amount, 2) > round(accounts[req.from_account], 2):
        raise HTTPException(status_code=400, detail="Insufficient funds")

    # Fix (float precision): round every ledger write to the cent so
    # balances never drift into 89.99499999999999-style float dust.
    accounts[req.from_account] = round(accounts[req.from_account] - req.amount, 2)
    accounts[req.to_account] = round(accounts[req.to_account] + req.amount, 2)

    return {
        "status": "success",
        "from_balance": accounts[req.from_account],
        "to_balance": accounts[req.to_account],
    }
