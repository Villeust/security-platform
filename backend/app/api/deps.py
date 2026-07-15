from uuid import UUID

from fastapi import Header, HTTPException, status


def get_current_contractor_id(x_contractor_id: UUID | None = Header(default=None)) -> UUID:
    # TODO: Replace this test-only stub with real identity/authorization integration.
    if x_contractor_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Contractor context is required",
        )
    return x_contractor_id


def get_current_internal_actor_id(x_actor_id: UUID | None = Header(default=None)) -> UUID | None:
    # TODO: Replace this temporary stub with real Security Platform identity context.
    return x_actor_id
