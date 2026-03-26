from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    file_id: str
    filename: str
    content_type: str
    size_bytes: int
    text: str


class ProcessRequest(BaseModel):
    text: str = Field(min_length=1)


class ExtractedEntity(BaseModel):
    type: Literal["diagnosis", "procedure", "medication"]
    value: str
    start: int
    end: int
    confidence: float


class ProcessResponse(BaseModel):
    diagnosis: List[str]
    procedures: List[str]
    medications: List[str]
    entities: Optional[List[ExtractedEntity]] = None

