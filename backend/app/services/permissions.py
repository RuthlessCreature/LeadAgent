from __future__ import annotations

from app.models import PermissionAction, Role


ROLE_PERMISSIONS: dict[Role, set[PermissionAction]] = {
    Role.admin: {
        PermissionAction.read_data,
        PermissionAction.edit_data,
        PermissionAction.approve,
        PermissionAction.export,
    },
    Role.sales_rep: {
        PermissionAction.read_data,
        PermissionAction.edit_data,
    },
    Role.reviewer: {
        PermissionAction.read_data,
        PermissionAction.approve,
    },
    Role.data_engineer: {
        PermissionAction.read_data,
        PermissionAction.edit_data,
        PermissionAction.export,
    },
}


def has_permission(role: Role, action: PermissionAction) -> bool:
    return action in ROLE_PERMISSIONS.get(role, set())
