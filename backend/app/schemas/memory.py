from pydantic import BaseModel


class MemoryAdd(BaseModel):
    content: str
    kind: str = "fact"
