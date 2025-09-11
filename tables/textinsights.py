import pydantic
import uuid

class TextInsights(pydantic.BaseModel):
    lectureId: uuid
    summary: str
    keyTerms: list[str]
    mainIdeas: list[str]
    reviewQuestions: list[str]