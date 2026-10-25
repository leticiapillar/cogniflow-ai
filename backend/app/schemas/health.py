from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response contract."""

    status: str = Field(..., examples=["healthy"], description="Service health status.")
    service: str = Field(
        ..., examples=["CogniFlow AI Backend"], description="Application name."
    )
    environment: str = Field(
        ..., examples=["development"], description="Current runtime environment."
    )
    database_connected: bool = Field(
        default=True, description="Indicates whether database connectivity is active."
    )

