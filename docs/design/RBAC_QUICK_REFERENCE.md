# RBAC Quick Reference

**Use this guide for quick lookups during development.**

---

## Files at a Glance

| File | Lines | Purpose |
|------|-------|---------|
| `app/models/role.py` | 270 | Permission, Role, and junction table models |
| `app/schemas/roles.py` | 220 | Pydantic request/response schemas |
| `app/services/role_service.py` | 400 | Business logic (CRUD, permission checks) |
| `app/api/roles.py` | 350 | REST endpoints (15+) |
| `app/tests/test_roles.py` | 500 | Unit tests (25+) |
| `alembic/versions/TEMPLATE_rbac_implementation.py` | 90 | Database schema migration |
| `docs/RBAC_DESIGN.md` | 500 | Full architecture & design |
| `docs/RBAC_INTEGRATION_CHECKLIST.md` | 400 | Step-by-step integration guide |

**Total: ~2,700 lines of production-ready code**

---

## API Endpoints (15 total)

### Permissions (Admin)
```
GET    /api/roles/permissions                     # List permissions
POST   /api/roles/permissions                     # Create permission
GET    /api/roles/permissions/{id}                # Get permission
PATCH  /api/roles/permissions/{id}                # Update permission
```

### Roles (Hotel-scoped)
```
GET    /api/roles                                 # List roles
POST   /api/roles                                 # Create role
GET    /api/roles/{id}                            # Get role (with permissions)
PATCH  /api/roles/{id}                            # Update role
DELETE /api/roles/{id}                            # Delete role

POST   /api/roles/{id}/assign-permissions         # Add permissions to role
POST   /api/roles/{id}/revoke-permissions         # Remove permissions from role
```

### User Roles
```
GET    /api/roles/users/{user_id}/roles           # Get user's roles
POST   /api/roles/users/{user_id}/assign-roles    # Assign roles to user
POST   /api/roles/users/{user_id}/revoke-roles    # Revoke roles from user
POST   /api/roles/users/bulk-assign-roles         # Bulk assign to multiple users

GET    /api/roles/check-permission                # Check current user's permission
```

---

## Key Service Functions

### Permission Service
```python
from app.services.role_service import (
    get_permission_or_404,           # Get by ID or fail
    get_permission_by_code,          # Get by code (e.g., "user:create")
    create_permission,               # Create new permission
    list_permissions,                # List all (with optional category filter)
    update_permission,               # Update (name, description, category)
    init_system_permissions,         # Seed PermissionEnum into DB
)
```

### Role Service
```python
from app.services.role_service import (
    get_role_or_404,                 # Get by ID + hotel_id
    get_role_by_slug,                # Get by slug + hotel_id
    list_roles,                      # List hotel's roles
    create_role,                     # Create role with permissions
    update_role,                     # Update role (not built-in)
    delete_role,                     # Delete role (if no users)
    assign_permissions_to_role,      # Add permissions
    revoke_permissions_from_role,    # Remove permissions
)
```

### User-Role Service
```python
from app.services.role_service import (
    assign_roles_to_user,            # Assign roles in hotel context
    revoke_roles_from_user,          # Revoke roles
    get_user_roles,                  # Get user's roles (in hotel)
    get_user_permissions,            # Get permission codes
    has_permission,                  # Check single permission
    has_any_permission,              # Check any of list
    has_all_permissions,             # Check all of list
    bulk_assign_roles,               # Assign roles to multiple users
)
```

---

## Permission Codes (Quick Reference)

```
user:create, user:read, user:update, user:delete, user:reset_password
role:create, role:read, role:update, role:delete, role:assign
hotel:config, hotel:analytics
reservation:create, reservation:read, reservation:update, reservation:delete
guest:create, guest:read, guest:update, guest:delete
room:manage
checkin_checkout:manage
payments:manage
reports:view, analytics:view
audit:view
```

---

## Built-in Roles

```python
# Each hotel has 4 system roles (is_builtin=True)
owner      → All permissions
co_owner   → All except user:delete
manager    → Reservation, guest, room, checkin, reports
staff      → Read-only + checkin
```

---

## Common Operations

### Create a Role with Permissions
```python
from app.services import role_service

role = role_service.create_role(
    db,
    hotel_id=1,
    name="Receptionist",
    slug="receptionist",
    description="Front desk staff",
    permission_ids=[perm1.id, perm2.id]  # Get IDs from permissions
)
```

### Assign Roles to User
```python
role_service.assign_roles_to_user(
    db,
    user_id=123,
    hotel_id=1,
    role_ids=[4, 5]  # Role IDs to assign
)
```

### Check Permission
```python
has_perm = role_service.has_permission(
    db,
    user_id=123,
    permission_code="user:create",
    hotel_id=1
)
if has_perm:
    # Allow operation
else:
    # Deny operation
```

### Update Role Permissions
```python
role_service.assign_permissions_to_role(
    db,
    role_id=5,
    hotel_id=1,
    permission_ids=[1, 2, 3]  # Replace existing permissions
)
```

---

## Request/Response Examples

### Create Permission
```bash
POST /api/roles/permissions
{
  "code": "custom:action",
  "name": "Custom Action",
  "description": "Does something custom",
  "category": "custom",
  "is_system": false
}

Response 201:
{
  "id": 52,
  "code": "custom:action",
  "name": "Custom Action",
  "category": "custom",
  "is_system": false,
  "created_at": "2026-06-09T12:00:00Z",
  "updated_at": "2026-06-09T12:00:00Z"
}
```

### Create Role
```bash
POST /api/roles
Header: X-Hotel-Id: 1

{
  "name": "Receptionist",
  "slug": "receptionist",
  "description": "Front desk staff",
  "permission_ids": [1, 2, 3]
}

Response 201:
{
  "id": 5,
  "name": "Receptionist",
  "slug": "receptionist",
  "hotel_id": 1,
  "is_builtin": false,
  "is_active": true,
  "permissions": [
    {"id": 1, "code": "guest:read", ...},
    {"id": 2, "code": "reservation:read", ...},
    {"id": 3, "code": "checkin_checkout:manage", ...}
  ],
  "created_at": "2026-06-09T12:00:00Z",
  "updated_at": "2026-06-09T12:00:00Z"
}
```

### Assign Roles to User
```bash
POST /api/roles/users/123/assign-roles
Header: X-Hotel-Id: 1

{
  "role_ids": [4, 5]
}

Response:
{
  "user_id": 123,
  "hotel_id": 1,
  "roles": [
    {"id": 4, "name": "Manager", "slug": "manager", ...},
    {"id": 5, "name": "Receptionist", "slug": "receptionist", ...}
  ]
}
```

### Check Permission
```bash
GET /api/roles/check-permission?permission_code=user:create
Header: X-Hotel-Id: 1

Response:
{
  "user_id": 123,
  "has_permission": true,
  "permission_code": "user:create",
  "message": "Permission granted"
}
```

---

## Database Schema (Quick View)

```sql
-- Permissions (system-wide)
permissions (id, code, name, category, is_system, created_at, updated_at)

-- Roles (per hotel)
roles (id, hotel_id, name, slug, is_builtin, is_active, created_at, updated_at)

-- Role → Permission (many-to-many)
role_permissions (role_id, permission_id)

-- User → Role → Hotel (many-to-many, scoped)
user_roles (user_id, role_id, hotel_id)
```

---

## Authorization Guards

```python
from app.dependencies.auth import require_roles

# Require owner or co_owner
@router.post("/...")
def endpoint(..., context: AuthContext = Depends(require_roles("owner", "co_owner"))):
    # user can perform action
    pass
```

---

## Error Codes

| Code | Meaning | Solution |
|------|---------|----------|
| 400 Bad Request | Validation error | Check request payload |
| 404 Not Found | Resource not found | Verify ID and hotel_id |
| 403 Forbidden | Insufficient permissions | Assign required role |

---

## Testing

### Run All Tests
```bash
pytest app/tests/test_roles.py -v
```

### Run Specific Test Class
```bash
pytest app/tests/test_roles.py::TestRoles -v
```

### Run Specific Test
```bash
pytest app/tests/test_roles.py::TestRoles::test_create_role -v
```

### With Coverage
```bash
pytest app/tests/test_roles.py --cov=app.services.role_service --cov-report=html
```

---

## Integration Checklist (Condensed)

- [ ] Update User model: add `roles` relationship
- [ ] Create Alembic migration: `alembic revision -m "Add RBAC..."`
- [ ] Run migration: `alembic upgrade head`
- [ ] Register router in main.py
- [ ] Seed permissions: `python scripts/init_permissions.py`
- [ ] Create built-in roles: `python scripts/init_builtin_roles.py`
- [ ] Run tests: `pytest app/tests/test_roles.py -v`
- [ ] Test via Swagger: http://localhost:8000/docs
- [ ] Update frontend to use `/api/roles/check-permission` for UI
- [ ] Monitor logs in production

---

## Common Mistakes to Avoid

| Mistake | Fix |
|---------|-----|
| Forgetting `X-Hotel-Id` header | Always include hotel context in requests |
| Trying to modify `is_builtin=True` roles | Deactivate instead: `is_active=False` |
| Using permission IDs instead of codes | Use codes: `"user:create"` not ID `7` |
| Not scoping role queries to hotel | All `get_role()` calls need `hotel_id` |
| Assigning roles without verifying they exist | Service will raise `ValueError` |
| Deleting role with assigned users | Remove users first, then delete |

---

## Performance Tips

1. **Permission Checks**: Cache `get_user_permissions()` in Redis for frequent checks
2. **Role Listing**: Uses index on (hotel_id, is_active)
3. **User-Role Lookup**: Lazy-loaded; consider eager loading if slow
4. **Bulk Operations**: Use `bulk_assign_roles()` instead of looping
5. **Pagination**: Use skip/limit parameters on list endpoints

---

## Useful Links (within repo)

- Full Design: `docs/RBAC_DESIGN.md`
- Integration: `docs/RBAC_INTEGRATION_CHECKLIST.md`
- Tests: `app/tests/test_roles.py`
- Models: `app/models/role.py`
- Service: `app/services/role_service.py`
- API: `app/api/roles.py`

---

## Example: Role Setup Script

```python
from app.database import get_session_factory
from app.services import role_service
from app.models.role import PermissionEnum

db = get_session_factory()()

# Seed permissions
role_service.init_system_permissions(db)

# Create custom role
role = role_service.create_role(
    db,
    hotel_id=1,
    name="Night Manager",
    slug="night_manager",
    permission_ids=[
        role_service.get_permission_by_code(db, PermissionEnum.RESERVATION_READ.value).id,
        role_service.get_permission_by_code(db, PermissionEnum.CHECKIN_CHECKOUT.value).id,
        role_service.get_permission_by_code(db, PermissionEnum.GUEST_READ.value).id,
    ]
)

# Assign to user
role_service.assign_roles_to_user(db, user_id=5, hotel_id=1, role_ids=[role.id])

db.close()
print("Night Manager role created and assigned!")
```

---

**Last Updated:** June 9, 2026  
**Version:** 1.0
