from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class NlpExtractRequest(BaseModel):
    text: str = Field(min_length=1)


class ExtractedEntity(BaseModel):
    type: Literal["diagnosis", "procedure"]
    value: str
    start: int
    end: int
    confidence: float
    negated: bool = False


class NlpExtractResponse(BaseModel):
    diagnosis: List[str]
    procedures: List[str]
    entities: List[ExtractedEntity]


class TermUpsert(BaseModel):
    type: Literal["diagnosis", "procedure"]
    canonical: str = Field(min_length=1, max_length=255)
    synonyms: Optional[List[str]] = None
    enabled: bool = True


class TermOut(BaseModel):
    id: int
    type: str
    canonical: str
    synonyms: List[str]
    enabled: bool

