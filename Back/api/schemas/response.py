"""
공통 응답 스키마
"""
from typing import TypeVar, Generic, List, Optional
from pydantic import BaseModel


T = TypeVar('T')


class PaginatedResponse(BaseModel, Generic[T]):
    data: List[T]
    total: int
    page: int
    limit: int


class ApiResponse(BaseModel, Generic[T]):
    data: T
    success: bool = True
    message: Optional[str] = None


