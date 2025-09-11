import pydantic
import uuid
import datetime

class LectureMetadata(pydantic.BaseModel):
    id: str = pydantic.Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    professor: str
    date: datetime.date
    duration_seconds: int
    class_number: str
    language: str = "en-US"
