from fastapi import APIRouter
from app.schemas import HelloResponse
router = APIRouter()

@router.get("/",response_model=HelloResponse)
async def hello():
    return HelloResponse(message="Hello, World!")