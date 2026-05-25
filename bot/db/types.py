from pydantic import BaseModel


class CompletionModel(BaseModel):
    id: str
    prompt: str
    completion: str
    discord_user: str
    created_at: str
