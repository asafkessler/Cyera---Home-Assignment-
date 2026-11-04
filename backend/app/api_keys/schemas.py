from datetime import datetime

from pydantic import BaseModel, Field


class CreateApiKeyRequest(BaseModel):
    name: str = Field(
        min_length=1, max_length=100,
        description="A label so you can recognise the key later, e.g. the system that will use it.",
        examples=["nightly-nhi-scanner"],
    )


class ApiKeyResponse(BaseModel):
    id: int
    name: str
    key_prefix: str = Field(description="The first characters of the key, to identify it. The full key is never shown again.")
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None

    model_config = {"from_attributes": True}


class ApiKeyCreatedResponse(ApiKeyResponse):
    key: str = Field(
        description="The full API key. **Shown only in this response.** Store it securely; it cannot be retrieved later.",
        examples=["ihk_3f9a1c2b4d5e6f708192a3b4c5d6e7f8a9b0c1d2e3f4"],
    )
