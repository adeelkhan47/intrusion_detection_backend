from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi import Request

from model import  Account
router = APIRouter()


@router.get("/signup")
def login(username, password, request: Request):
    account = Account.get_by_username(username)
    if account:
        raise HTTPException(status_code=400, detail="Already Exist.")
    account = Account(username=username, password=password)
    account.insert()

    return account.id
@router.get("/login")
def login(username, password, request: Request):
    account = Account.get_by_username_pass(username, password)
    if not account:
        raise HTTPException(status_code=404, detail="Not Found.")

    return account.id

