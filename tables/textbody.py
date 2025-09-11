import pydantic
import uuid

class TextBody(pydantic.BaseModel):
    lectureId: uuid
    text: str
