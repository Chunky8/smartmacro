from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status

ROLE_USER = "USER"
ROLE_ADMIN = "ADMIN"
VALID_ROLES = {ROLE_USER, ROLE_ADMIN}


@dataclass(frozen=True)
class CurrentUser:
    user_id: int
    role: str


def get_current_user(
    x_user_id: int = Header(default=1, alias="X-User-Id"),
    x_user_role: str = Header(default=ROLE_USER, alias="X-User-Role"),
) -> CurrentUser:
    """Extract and validate user identity and role from request headers."""
    if x_user_id < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Érvénytelen X-User-Id fejléc.",
        )
    normalized_role = x_user_role.strip().upper()
    if normalized_role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Érvénytelen szerepkör: '{x_user_role}'. Engedélyezett: USER, ADMIN.",
        )
    return CurrentUser(user_id=x_user_id, role=normalized_role)


def require_admin(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Dependency enforcing ADMIN role for master data modifications."""
    if current_user.role != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin jogosultság szükséges a törzsadatok módosításához.",
        )
    return current_user
