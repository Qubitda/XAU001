"""Field-level permissions for OPS product mutations."""
from config.exceptions import DomainError

FIELD_PERMISSIONS: dict[str, str] = {
    "ledger": "pricing:edit",
    "pricingMode": "pricing:edit",
    "fireRatePct": "pricing:edit",
    "stockQty": "inventory:manage",
    "ownerOrganizationId": "orgs:manage",
    "salesChannels": "catalog:publish",
    "catalogStatus": "catalog:publish",
}


def _enforce_field_permissions(ctx, data: dict) -> None:
    for field_name, perm in FIELD_PERMISSIONS.items():
        if field_name in data and perm not in ctx.permissions:
            raise DomainError(
                f"'{field_name}' alanını değiştirmek için '{perm}' yetkisi gereklidir.",
                code="FORBIDDEN_FIELD",
                status_code=403,
            )


