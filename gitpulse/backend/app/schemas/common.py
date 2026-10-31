from typing import Generic, TypeVar, Optional, List, Any
from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Any] = None
    request_id: Optional[str] = None


class APIResponse(BaseModel, Generic[T]):
    success: bool = True
    data: Optional[T] = None
    message: Optional[str] = None


class PaginationMeta(BaseModel):
    total: int = Field(..., description="Total count of items matching the query")
    page: int = Field(default=1, ge=1, description="Current page number")
    limit: int = Field(default=50, ge=1, le=100, description="Items per page")
    pages: int = Field(..., description="Total number of pages")


class PaginatedResponse(BaseModel, Generic[T]):
    success: bool = True
    items: List[T]
    pagination: PaginationMeta


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    uptime_seconds: float
    database: dict

