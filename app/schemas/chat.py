from pydantic import BaseModel, Field

from app.schemas.booking import BookingState


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, description="Unique conversation session identifier")
    message: str = Field(min_length=1, description="User query or message")
    document_ids: list[str] | None = Field(default=None, description="Optional document ID filter")


class SourceChunk(BaseModel):
    document_id: str
    chunk_index: int


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
    booking: BookingState | None = None
