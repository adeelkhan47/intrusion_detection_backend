from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi import Request

from api.packet.schemas import GetPackets
from model import Packet

router = APIRouter()


@router.get("", response_model=GetPackets)
def FetchPackets(request: Request):
    packets, count = Packet.filter_and_order({})
    return {"packets": packets, "count": count}
