from pydantic import BaseModel


class PromptTuningApply(BaseModel):
    system_prompt: str
