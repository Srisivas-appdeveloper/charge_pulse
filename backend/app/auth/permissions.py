"""FastAPI RBAC permission guard dependencies."""
from __future__ import annotations

from fastapi import Depends, HTTPException, status

from app.dependencies import _get_current_user, CurrentUserCtx


def require_role(*allowed_roles: str):
    async def dependency(user: CurrentUserCtx = Depends(_get_current_user)) -> CurrentUserCtx:
        # Non-impersonating superadmin can only access explicit superadmin routes
        if user.is_superadmin and not user.impersonating:
            if "superadmin" in allowed_roles:
                return user
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Superadmin must impersonate an organization to perform tenant operations",
            )

        # Check if the ordinary role is allowed
        if user.role in allowed_roles:
            return user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    return dependency
