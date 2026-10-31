"""
Database Telemetry & Status API Schemas.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DatabasePoolStatus(BaseModel):
    pool_size: int
    checked_in: int
    checked_out: int
    overflow: int


class DatabaseStatusResponse(BaseModel):
    status: str = Field(description="'healthy' or 'degraded'")
    connected: bool
    dialect: str
    database_name: str
    server_host: Optional[str] = None
    server_port: Optional[int] = None
    latency_ms: float
    pool: Optional[DatabasePoolStatus] = None
    checked_at: datetime = Field(default_factory=datetime.utcnow)


class TableStatistics(BaseModel):
    table_name: str
    row_count: int
    tier: str = Field(description="bronze | silver | operational")
    last_updated: Optional[datetime] = None


class DatabaseStatisticsResponse(BaseModel):
    total_tables: int
    total_records: int
    bronze_records: int
    silver_records: int
    operational_records: int
    tables: List[TableStatistics]
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool
    primary_key: bool
    default: Optional[str] = None


class TableDetail(BaseModel):
    name: str
    tier: str
    columns: List[ColumnInfo]
    indexes: List[str]
    estimated_row_count: int


class DatabaseTablesResponse(BaseModel):
    tables: List[TableDetail]
    count: int


class TierSummary(BaseModel):
    tier: str
    table_count: int
    total_rows: int
    tables: List[str]
    last_ingestion: Optional[datetime] = None


class StorageSummaryResponse(BaseModel):
    engine_dialect: str
    tiers: Dict[str, TierSummary]
    total_raw_payloads: int
    total_storage_rows: int
    generated_at: datetime = Field(default_factory=datetime.utcnow)

