"""LLM Provider API routes."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.dependencies import get_provider_repo
from db.repositories import LLMProviderRepository

router = APIRouter()


class ProviderCreate(BaseModel):
    """Request model for creating a provider."""

    name: str
    provider_type: str  # openai, anthropic, custom
    api_key: str
    model_id: str
    base_url: Optional[str] = None
    host_country: Optional[str] = None
    is_default: bool = False


class ProviderUpdate(BaseModel):
    """Request model for updating a provider."""

    name: Optional[str] = None
    provider_type: Optional[str] = None
    api_key: Optional[str] = None
    model_id: Optional[str] = None
    base_url: Optional[str] = None
    host_country: Optional[str] = None
    is_default: Optional[bool] = None


class ProviderResponse(BaseModel):
    """Response model for a provider (without API key)."""

    id: int
    name: str
    provider_type: str
    model_id: str
    base_url: Optional[str] = None
    host_country: Optional[str] = None
    is_default: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ProviderListResponse(BaseModel):
    """Response model for listing providers."""

    providers: List[ProviderResponse]
    total: int


def _provider_to_response(provider) -> ProviderResponse:
    """Convert provider model to response (excluding API key)."""
    return ProviderResponse(
        id=provider.id,
        name=provider.name,
        provider_type=provider.provider_type,
        model_id=provider.model_id,
        base_url=provider.base_url,
        host_country=provider.host_country,
        is_default=provider.is_default,
        created_at=provider.created_at.isoformat(),
        updated_at=provider.updated_at.isoformat(),
    )


@router.get("/providers", response_model=ProviderListResponse)
async def list_providers(
    provider_repo: LLMProviderRepository = Depends(get_provider_repo),
):
    """List all LLM providers."""
    providers = await provider_repo.get_all()
    return ProviderListResponse(
        providers=[_provider_to_response(p) for p in providers],
        total=len(providers),
    )


@router.get("/providers/default", response_model=Optional[ProviderResponse])
async def get_default_provider(
    provider_repo: LLMProviderRepository = Depends(get_provider_repo),
):
    """Get the default LLM provider."""
    provider = await provider_repo.get_default()
    if not provider:
        return None
    return _provider_to_response(provider)


@router.get("/providers/{provider_id}", response_model=ProviderResponse)
async def get_provider(
    provider_id: int,
    provider_repo: LLMProviderRepository = Depends(get_provider_repo),
):
    """Get a specific LLM provider."""
    provider = await provider_repo.get_by_id(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return _provider_to_response(provider)


@router.post("/providers", response_model=ProviderResponse)
async def create_provider(
    data: ProviderCreate,
    provider_repo: LLMProviderRepository = Depends(get_provider_repo),
):
    """Create a new LLM provider."""
    # Validate provider type
    valid_types = ["openai", "anthropic", "custom"]
    if data.provider_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid provider_type. Must be one of: {', '.join(valid_types)}",
        )

    provider = await provider_repo.create(
        name=data.name,
        provider_type=data.provider_type,
        api_key=data.api_key,
        model_id=data.model_id,
        base_url=data.base_url,
        host_country=data.host_country,
        is_default=data.is_default,
    )
    return _provider_to_response(provider)


@router.put("/providers/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: int,
    data: ProviderUpdate,
    provider_repo: LLMProviderRepository = Depends(get_provider_repo),
):
    """Update an LLM provider."""
    # Validate provider type if provided
    if data.provider_type is not None:
        valid_types = ["openai", "anthropic", "custom"]
        if data.provider_type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid provider_type. Must be one of: {', '.join(valid_types)}",
            )

    provider = await provider_repo.update(
        provider_id=provider_id,
        name=data.name,
        provider_type=data.provider_type,
        api_key=data.api_key,
        model_id=data.model_id,
        base_url=data.base_url,
        host_country=data.host_country,
        is_default=data.is_default,
    )

    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    return _provider_to_response(provider)


@router.delete("/providers/{provider_id}")
async def delete_provider(
    provider_id: int,
    provider_repo: LLMProviderRepository = Depends(get_provider_repo),
):
    """Delete an LLM provider."""
    success = await provider_repo.delete(provider_id)
    if not success:
        raise HTTPException(status_code=404, detail="Provider not found")
    return {"status": "deleted", "provider_id": provider_id}


@router.post("/providers/{provider_id}/set-default", response_model=ProviderResponse)
async def set_default_provider(
    provider_id: int,
    provider_repo: LLMProviderRepository = Depends(get_provider_repo),
):
    """Set a provider as the default."""
    provider = await provider_repo.set_default(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return _provider_to_response(provider)
