from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from core.version import get_release_version

router = APIRouter(prefix="/api/runtime-config", tags=["runtime-config"])


class RuntimeConfigResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    product_name: str
    product_version: str = Field(alias="version")
    feature_flags: dict[str, bool] = Field(alias="features")


@router.get("", response_model=RuntimeConfigResponse)
async def get_runtime_config():
    # Return basic non-secret configuration.
    return RuntimeConfigResponse(
        product_name="Naruon",
        product_version=get_release_version(),
        feature_flags={
            "llm_enabled": True,
            "smtp_enabled": True,
            "imap_enabled": True,
        },
    )
