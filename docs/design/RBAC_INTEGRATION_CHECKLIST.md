# RBAC Integration Checklist

Follow these steps to integrate the RBAC module into the Hotel Chipre PMS codebase.

---

## Phase 1: Database & Models

### Step 1.1: Update User Model
**File:** `app/models/user.py`

Add the relationship to User class:
```python
from sqlalchemy.orm import relationship

class User(Base):
    # ... existing fields ...
    
    # NEW: Many-to-many relationship with roles
    roles = relationship(
        "Role",
        secondary="user_roles",
        back_populates="users",
        lazy="selectin",
        viewonly=True
    )
```

### Step 1.2: Create Alembic Migration
**File:** `alembic/versions/*.py`

```bash
cd /path/to/project
alembic revision -m "Add RBAC: User Roles, Permissions, and Relationships"
```

Then edit the generated file with the SQL from `alembic/versions/TEMPLATE_rbac_implementation.py`:
- Create `permissions` table
- Create `roles` table (hotel-scoped)
- Create `role_permissions` junction table
- Create `user_roles` junction table (hotel-scoped)

Run migration:
```bash
alembic upgrade head
```

### Step 1.3: Verify Models Are Imported
**File:** `app/models/__init__.py`

Add import (if using wildcard import):
```python
from app.models.role import Permission, Role, role_permissions, user_roles
```

---

## Phase 2: Authentication & Dependencies

### Step 2.1: Extend AuthContext
**File:** `app/dependencies/auth.py`

Update `AuthContext` dataclass:
```python
from dataclasses import dataclass
from typing import Optional, Set, List

@dataclass
class AuthContext:
    hotel_id: int
    user_id: Optional[int] = None
    user_email: Optional[str] = None
    user_role: Optional[str] = None  # Legacy field (keep for backwards compat)
    is_verified: bool = False
    permissions: Optional[Set[str]] = None  # NEW: permission codes
    roles: Optional[List[str]] = None  # NEW: role slugs
```

### Step 2.2: (Optional) Update Auth Decorators
**File:** `app/dependencies/auth.py`

Add helper function for permission-based authorization:
```python
from app.services.role_service import has_permission

def require_permission(permission_code: str):
    """Dependency: require specific permission."""
    def check(context: AuthContext = Depends(require_roles("owner", "co_owner", "manager"))):
        if not has_permission(db, context.user_id, permission_code, context.hotel_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission_code}' required"
            )
        return context
    return check
```

---

## Phase 3: API Routers

### Step 3.1: Register Roles Router
**File:** `main.py` or router aggregator (e.g., `app/main.py`)

```python
from app.api.roles import router as roles_router

# In FastAPI app setup
app.include_router(roles_router)
```

Example (if using router aggregator):
```python
# app/api/__init__.py or similar
from fastapi import APIRouter

api_router = APIRouter()

from app.api.companies import router as companies_router
from app.api.roles import router as roles_router

api_router.include_router(companies_router)
api_router.include_router(roles_router)

# In main.py:
app.include_router(api_router)
```

### Step 3.2: Verify API Documentation
Start the FastAPI app and verify new endpoints appear in Swagger/OpenAPI:
```bash
python -m uvicorn main:app --reload
# Visit http://localhost:8000/docs
# Look for /api/roles section
```

---

## Phase 4: Database Initialization

### Step 4.1: Seed System Permissions
Create a one-time script:

**File:** `scripts/init_permissions.py`
```python
"""Initialize system permissions (run once after migration)."""
import sys
sys.path.insert(0, '/path/to/project')

from app.database import get_session_factory
from app.services.role_service import init_system_permissions

factory = get_session_factory()
db = factory()

print("Initializing system permissions...")
init_system_permissions(db)
print("✓ Permissions initialized successfully")

db.close()
```

Run it:
```bash
cd /path/to/project
python scripts/init_permissions.py
```

### Step 4.2: Create Built-in Roles (per Hotel)
Create another one-time script:

**File:** `scripts/init_builtin_roles.py`
```python
"""Create built-in roles for existing hotels."""
import sys
sys.path.insert(0, '/path/to/project')

from app.database import get_session_factory
from app.models.hotel_configuration import HotelConfiguration
from app.services.role_service import create_role, get_permission_by_code
from app.models.role import PermissionEnum

factory = get_session_factory()
db = factory()

# Get all existing hotels
hotels = db.query(HotelConfiguration).all()

for hotel in hotels:
    print(f"\nInitializing roles for hotel {hotel.id}: {hotel.name}")

    # Get all permissions
    all_perms = db.query(Permission).all()
    read_only_perms = [p for p in all_perms if p.code in [
        PermissionEnum.USER_READ.value,
        PermissionEnum.RESERVATION_READ.value,
        PermissionEnum.GUEST_READ.value,
        PermissionEnum.REPORTS_VIEW.value,
    ]]

    # Owner: all permissions
    owner = create_role(
        db, hotel.id,
        name="Owner",
        slug="owner",
        is_builtin=True,
        permission_ids=[p.id for p in all_perms]
    )
    print(f"  ✓ Created Owner role (all {len(all_perms)} permissions)")

    # Co-owner: almost all (except user deletion, payment override)
    co_owner_perms = [p for p in all_perms if p.code not in [
        PermissionEnum.USER_DELETE.value,
    ]]
    co_owner = create_role(
        db, hotel.id,
        name="Co-Owner",
        slug="co_owner",
        is_builtin=True,
        permission_ids=[p.id for p in co_owner_perms]
    )
    print(f"  ✓ Created Co-Owner role ({len(co_owner_perms)} permissions)")

    # Manager: operations, reports, limited user management
    manager_perms = [p for p in all_perms if p.category in [
        "reservation", "guest", "room", "checkin_checkout", "reports"
    ] or p.code in [PermissionEnum.USER_READ.value]]
    manager = create_role(
        db, hotel.id,
        name="Manager",
        slug="manager",
        is_builtin=True,
        permission_ids=[p.id for p in manager_perms]
    )
    print(f"  ✓ Created Manager role ({len(manager_perms)} permissions)")

    # Staff: read-only + checkin/checkout
    staff_perms = read_only_perms + [p for p in all_perms if p.code == PermissionEnum.CHECKIN_CHECKOUT.value]
    staff = create_role(
        db, hotel.id,
        name="Staff",
        slug="staff",
        is_builtin=True,
        permission_ids=[p.id for p in staff_perms]
    )
    print(f"  ✓ Created Staff role ({len(staff_perms)} permissions)")

db.close()
print("\n✓ All hotel roles initialized successfully")
```

Run it:
```bash
python scripts/init_builtin_roles.py
```

### Step 4.3: Assign Existing Users to Roles
Create a migration script:

**File:** `scripts/migrate_user_roles.py`
```python
"""Migrate existing user.role field to new role_permissions system."""
import sys
sys.path.insert(0, '/path/to/project')

from app.database import get_session_factory
from app.models.user import User
from app.models.hotel_membership import HotelMembership
from app.services.role_service import get_role_by_slug, assign_roles_to_user

factory = get_session_factory()
db = factory()

# Mapping from old user.role to new role slug
ROLE_MAPPING = {
    "owner": "owner",
    "co_owner": "co_owner",
    "manager": "manager",
    "staff": "staff",
}

users = db.query(User).all()

for user in users:
    old_role = user.role
    if old_role not in ROLE_MAPPING:
        print(f"⚠ User {user.id} ({user.email}): unknown role '{old_role}', skipping")
        continue

    # Find user's hotels
    memberships = db.query(HotelMembership).filter(
        HotelMembership.user_id == user.id,
        HotelMembership.status == "active"
    ).all()

    for membership in memberships:
        new_role_slug = ROLE_MAPPING[old_role]
        role = get_role_by_slug(db, membership.hotel_id, new_role_slug)

        if role:
            assign_roles_to_user(db, user.id, membership.hotel_id, [role.id])
            print(f"✓ User {user.id} ({user.email}) in hotel {membership.hotel_id}: assigned '{new_role_slug}'")
        else:
            print(f"✗ User {user.id} ({user.email}) in hotel {membership.hotel_id}: role '{new_role_slug}' not found")

db.close()
print("\n✓ User roles migrated successfully")
```

Run it:
```bash
python scripts/migrate_user_roles.py
```

---

## Phase 5: Testing

### Step 5.1: Run Unit Tests
```bash
pytest app/tests/test_roles.py -v
```

Expected output: All tests pass (>20 tests covering permissions, roles, assignments)

### Step 5.2: Test API Endpoints (Swagger)
Start the app:
```bash
python -m uvicorn main:app --reload
```

Visit http://localhost:8000/docs and test:
1. **GET /api/roles/permissions** — List permissions
2. **POST /api/roles** — Create a role
3. **GET /api/roles** — List roles
4. **POST /api/roles/{id}/assign-permissions** — Assign permissions to role
5. **POST /api/roles/users/{user_id}/assign-roles** — Assign roles to user
6. **GET /api/roles/check-permission** — Check user's permission

### Step 5.3: Manual Integration Test
```bash
# 1. Create a new role
curl -X POST http://localhost:8000/api/roles \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Hotel-Id: 1" \
  -H "Content-Type: application/json" \
  -d '{"name": "Custom Role", "slug": "custom", "permission_ids": [1, 2, 3]}'

# 2. Assign role to user
curl -X POST http://localhost:8000/api/roles/users/123/assign-roles \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Hotel-Id: 1" \
  -H "Content-Type: application/json" \
  -d '{"role_ids": [5]}'

# 3. Check user permission
curl -X GET "http://localhost:8000/api/roles/check-permission?permission_code=user:create" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Hotel-Id: 1"
```

---

## Phase 6: Backwards Compatibility (Optional)

### Update Auth Middleware (if needed)
If existing code relies on `user.role` field, keep it for now but populate it from the new role system:

**File:** `app/services/auth.py` or similar
```python
def get_primary_role_legacy(db: Session, user_id: int, hotel_id: int) -> str:
    """Get user's primary role (legacy compatibility)."""
    roles = role_service.get_user_roles(db, user_id, hotel_id)
    if not roles:
        return "staff"  # Default
    
    # Prioritize by importance
    priority = {"owner": 0, "co_owner": 1, "manager": 2, "staff": 3}
    return min(roles, key=lambda r: priority.get(r.slug, 999)).slug
```

---

## Phase 7: Documentation & Handoff

### Files to Review
1. **`docs/RBAC_DESIGN.md`** — Architecture, models, endpoints
2. **`app/models/role.py`** — Permission, Role, and junction tables
3. **`app/schemas/roles.py`** — Request/response schemas
4. **`app/services/role_service.py`** — Business logic
5. **`app/api/roles.py`** — API endpoints
6. **`app/tests/test_roles.py`** — Unit tests

### Update Project README
Add section to `README.md`:
```markdown
## Role-Based Access Control (RBAC)

The system uses a hierarchical RBAC with:
- **Permissions**: Atomic capabilities (e.g., `user:create`, `reservation:read`)
- **Roles**: Named collections of permissions (e.g., Manager, Staff)
- **User-Role Bindings**: Hotel-scoped assignments

See [RBAC Design](docs/RBAC_DESIGN.md) for details.

### Endpoints
- `GET /api/roles/permissions` — List permissions
- `POST /api/roles` — Create role
- `POST /api/roles/{id}/assign-permissions` — Assign permissions
- `POST /api/roles/users/{user_id}/assign-roles` — Assign roles to user
```

---

## Post-Integration Cleanup

### After Rolling Out to Production

1. **Monitor logs** for any permission-related errors
2. **Update frontend** to use `/api/roles/check-permission` for conditional UI rendering
3. **Deprecate `user.role` field** if legacy compatibility is no longer needed
4. **Set up audit logging** to track role assignments (see RBAC_DESIGN.md Future Enhancements)

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Migration fails | Ensure `hotel_configuration` table exists first; check Alembic revision chain |
| Endpoints return 404 | Verify router is registered in main.py; restart app |
| Permission checks always fail | Verify user is assigned role in correct hotel; check role has permission |
| "Role not found" errors | Ensure built-in roles are created for hotel; run `init_builtin_roles.py` |
| Tests fail | Ensure test database is properly initialized; check conftest.py fixtures |

---

## Support & References

- RBAC Design: `docs/RBAC_DESIGN.md`
- API Reference: Swagger at `/docs`
- Test Examples: `app/tests/test_roles.py`
- SQLAlchemy ORM: https://docs.sqlalchemy.org/
- FastAPI Dependencies: https://fastapi.tiangolo.com/tutorial/dependencies/
