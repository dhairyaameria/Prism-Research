"""Tenant RBAC: optional strict mode requires X-Prism-Principal + tenant_members row."""

from __future__ import annotations

import os

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from prism_api.models import TenantMember

_ROLE_ORDER = {"viewer": 1, "analyst": 2, "admin": 3}


async def require_tenant_role(
    db: AsyncSession,
    *,
    tenant_id: str,
    principal: str | None,
    min_role: str = "analyst",
) -> None:
    """Raise 401/403 if PRISM_RBAC_STRICT and caller lacks role."""
    strict = os.environ.get("PRISM_RBAC_STRICT", "").lower() in ("1", "true", "yes")
    if not strict:
        return
    p = (principal or "").strip()
    if not p:
        raise HTTPException(401, "X-Prism-Principal required when PRISM_RBAC_STRICT=1")
    res = await db.execute(
        select(TenantMember).where(
            TenantMember.tenant_id == tenant_id,
            TenantMember.principal == p,
        )
    )
    row = res.scalar_one_or_none()
    if row is None:
        raise HTTPException(403, "principal not registered for this tenant")
    need = _ROLE_ORDER.get(min_role, 2)
    have = _ROLE_ORDER.get(row.role, 0)
    if have < need:
        raise HTTPException(403, f"requires role {min_role} or higher")
