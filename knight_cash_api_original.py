"""
KnightCash API — v1 (as delivered by the original developer)

"It works perfectly." — original dev, probably lying.

A tiny in-memory banking API for UCF students.
Endpoints:
    GET  /balance/{account_id}
    POST /transfer
"""
from fastapi import FastAPI
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
    # Bug: no existence check -> raw KeyError -> FastAPI 500 with a
    # traceback that leaks the in-memory dict structure to the caller.
    balance = accounts[account_id]
    return {"account_id": account_id, "balance": balance}


@app.post("/transfer")
def transfer(req: TransferRequest):
    # Bug 1: no check that amount > 0. A "transfer" of -50 subtracts
    # -50 (i.e. ADDS 50) from the sender and adds -50 to the receiver,
    # letting a user mint money out of thin air.
    #
    # Bug 2: no check that from_account has sufficient funds. Any
    # account can go arbitrarily negative — free overdraft forever.
    #
    # Bug 3: no check that from_account != to_account. Transferring to
    # yourself is a silent no-op that still returns 200 OK, masking
    # what should probably be a 400.
    accounts[req.from_account] -= req.amount
    accounts[req.to_account] += req.amount

    return {
        "status": "success",
        "from_balance": accounts[req.from_account],
        "to_balance": accounts[req.to_account],
    }
