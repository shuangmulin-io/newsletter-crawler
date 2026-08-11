from pydantic import BaseModel, Field
from typing import List, Optional

class TargetModel(BaseModel):
    """
    Validation schema for a single newsletter crawler target.
    """
    name: str = Field(..., max_length=100, description="Name of the newsletter target")
    url: str = Field(..., max_length=2000, description="URL of the newsletter archive/latest issue")

class CacheMetadata(BaseModel):
    """
    Schema for cache metadata stored inside cached JSON files.
    """
    cache_key: str = Field(..., description="Deterministically generated cache key hash")
    generated_at: str = Field(..., description="Timestamp when the report was generated")
    target_count: int = Field(..., description="Number of targets included in the run")
