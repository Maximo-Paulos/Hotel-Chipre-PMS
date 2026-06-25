# Role-Based Access Control (RBAC) — Design & Implementation

## Overview

This module implements a hierarchical RBAC system for Hotel Chipre PMS. It enables fine-grained permission control through:
- **Permissions**: Atomic capabilities (e.g., `user:create`, `reservation:read`)
- **Roles**: Named collections of permissions (e.g., Manager, Receptionist)
- **User-Role Bindings**: Hotel-scoped assignments linking users to roles

---

## Architecture

### 1. Core Models

#### `Permission`
```python
class Permission(Base):
    id: int
    code: str  # Unique identifier: "user:create"
    name: str  # Display name: "Create Users"
    description: str  # Optional explanation
    category: str  # Grouping: "user", "role", "hotel", etc.
    is_system: bool  # Immutable if True (cannot be edited/deleted)
    created_at, updated_at: datetime
```

**Features:**
- Immutable system permissions prevent accidental breaking changes
- Categories enable filtering and logical grouping in UI
- Code-based (not ID-based) for configuration-as-code portability

**Pre-seeded permissions** (via `PermissionEnum`):
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

#### `Role`
```python
class Role(Base):
    id: int
    hotel_id: int  # Multi-tenancy: roles belong to a hotel
    name: str  # Display name: "Manager"
    slug: str  # URL-safe identifier: "manager"
    description: str
    is_builtin: bool  # Built-in roles (owner, co_owner, manager, staff) cannot be deleted
    is_active: bool  # Soft-disable roles without deleting
    permissions: List[Permission]  # Many-to-many via role_permissions table
    created_at, updated_at: datetime
```

**Constraints:**
- Unique (hotel_id, slug) prevents duplicate role names per hotel
- Unique (hotel_id, name) ensures display name uniqueness
- Built-in roles are immutable (cannot be deleted or heavily modified)

**Built-in roles** (system-provided):
| Role | Typical Permissions |
|------|-------------------|
| owner | All permissions (full access) |
| co_owner | Most permissions except user deletion, payment override |
| manager | Reservation, guest, room, checkin/checkout, reports |
| staff | Read-only on reservations/guests, checkin/checkout operations |

---

#### `User-Role Association`
```python
# Junction table: user_roles
user_id: int  # FK to users.id
role_id: int  # FK to roles.id
hotel_id: int  # FK to hotel_configuration.id
# Primary key: (user_id, role_id, hotel_id)
# Unique constraint prevents duplicate assignments
```

**Design principle:** Roles are **hotel-scoped**.
- Same user can have different roles in different hotels
- Example: Alice is "manager" at Hotel A, "owner" at Hotel B

---

### 2. Database Schema

```
┌─────────────────────────────────────┐
│        permissions                  │
├──────────┬──────────────────────────┤
│ id (PK)  │ code (unique, indexed)   │
│ name     │ category (indexed)       │
│ is_system│ created_at, updated_at   │
└─────────────────────────────────────┘
          ▲
          │ (many-to-many)
          └── role_permissions ──┐
                                 ▼
┌──────────────────────────────────────────┐
│              roles                       │
├──────────┬───────────────────────────────┤
│ id (PK)  │ hotel_id (FK, indexed)       │
│ slug     │ is_builtin, is_active        │
│ name     │ created_at, updated_at       │
└──────────────────────────────────────────┘
          ▲
          │ (many-to-many, hotel-scoped)
          └── user_roles ────┬──────────────────────┐
                             ▼                      ▼
                    ┌──────────────────┐   ┌──────────────────────┐
                    │ users (existing) │   │ hotel_configuration  │
                    │ id, email, ...   │   │ (already exists)     │
                    └──────────────────┘   └──────────────────────┘
```

---

## API Endpoints

### Permissions (Admin only)

```
GET    /api/roles/permissions              # List all permissions
GET    /api/roles/permissions?category=user
POST   /api/roles/permissions              # Create permission
GET    /api/roles/permissions/{id}         # Get permission
PATCH  /api/roles/permissions/{id}         # Update (name, description, category)
```

### Roles

```
GET    /api/roles                          # List roles (hotel-scoped)
POST   /api/roles                          # Create role
GET    /api/roles/{id}                     # Get role with permissions
PATCH  /api/roles/{id}                     # Update role
DELETE /api/roles/{id}                     # Delete role (no users assigned)

POST   /api/roles/{id}/assign-permissions  # Assign perms to role
POST   /api/roles/{id}/revoke-permissions  # Revoke perms from role
```

### User Roles

```
GET    /api/roles/users/{user_id}/roles              # Get user's roles
POST   /api/roles/users/{user_id}/assign-roles       # Assign roles
POST   /api/roles/users/{user_id}/revoke-roles       # Revoke roles
POST   /api/roles/users/bulk-assign-roles            # Bulk assignment

GET    /api/roles/check-permission                   # Check current user's permission
```

---

## Service Layer (`role_service.py`)

### Permission Management

```python
# CRUD
get_permission_or_404(db, permission_id) -> Permission
get_permission_by_code(db, code: str) -> Permission | None
create_permission(db, code, name, ...) -> Permission
list_permissions(db, category, skip, limit) -> List[Permission]
update_permission(db, permission_id, ...) -> Permission

# Initialization
init_system_permissions(db)  # Seed PermissionEnum into DB
```

### Role Management

```python
# CRUD (hotel-scoped)
get_role_or_404(db, role_id, hotel_id) -> Role
get_role_by_slug(db, hotel_id, slug) -> Role | None
list_roles(db, hotel_id, active_only) -> List[Role]
create_role(db, hotel_id, name, slug, ...) -> Role
update_role(db, role_id, hotel_id, ...) -> Role
delete_role(db, role_id, hotel_id) -> None

# Permission assignment
assign_permissions_to_role(db, role_id, hotel_id, permission_ids) -> Role
revoke_permissions_from_role(db, role_id, hotel_id, permission_ids) -> Role
```

### User-Role Binding

```python
# Assignment
assign_roles_to_user(db, user_id, hotel_id, role_ids) -> None
revoke_roles_from_user(db, user_id, hotel_id, role_ids) -> None
get_user_roles(db, user_id, hotel_id=None) -> List[Role]

# Bulk operations
bulk_assign_roles(db, hotel_id, user_ids, role_ids) -> List[Result]
```

### Permission Checking

```python
# Query user's permissions
get_user_permissions(db, user_id, hotel_id=None) -> List[str]  # Permission codes

# Checks
has_permission(db, user_id, code, hotel_id) -> bool
has_any_permission(db, user_id, codes, hotel_id) -> bool
has_all_permissions(db, user_id, codes, hotel_id) -> bool
```

---

## Request/Response Schemas (`schemas/roles.py`)

### Permission Schemas

- `PermissionCreate`: Create permission (code, name, category, is_system)
- `PermissionUpdate`: Update (name, description, category)
- `PermissionRead`: Response with id, code, name, timestamps

### Role Schemas

- `RoleCreatePayload`: Create role (name, slug, permission_ids)
- `RoleUpdate`: Update (name, description, is_active, permission_ids)
- `RoleRead`: Full response with nested permissions
- `RoleReadSummary`: Compact response (no nested permissions, permission_count)
- `RolePermissionAssign/Revoke`: Bulk permission assignment/revocation

### User-Role Schemas

- `UserRoleAssign/Revoke`: Assign/revoke roles to/from user
- `UserRoleRead`: User's role assignments in a hotel
- `BulkRoleAssignPayload`: Bulk assign roles to multiple users
- `RoleAssignmentResult`: Result of assignment (success/failure info)
- `PermissionCheckResponse`: Current user's permission check result

---

## Authorization Rules

### Who can do what?

| Action | Required Roles | Notes |
|--------|---|---|
| List permissions | owner, co_owner, manager | Informational access |
| Create permission | owner, co_owner | Admin-only |
| Update permission | owner, co_owner | Cannot change code or is_system |
| List roles | owner, co_owner, manager | Within hotel scope |
| Create role | owner, co_owner | Hotel-scoped |
| Update role | owner, co_owner | Cannot modify built-in roles |
| Delete role | owner, co_owner | Only if no users assigned |
| Assign roles to user | owner, co_owner | Within hotel scope |
| Revoke roles from user | owner, co_owner | Within hotel scope |
| Check own permissions | Any authenticated user | Via /check-permission |

---

## Integration Points

### 1. User Model Enhancement
The existing `User` model needs to support roles via the `user_roles` junction table:

```python
# In app/models/user.py (add to existing User class)
roles = relationship(
    "Role",
    secondary="user_roles",
    back_populates="users",
    lazy="selectin",
    viewonly=True
)
```

### 2. Auth Dependency Update
The `AuthContext` (in `dependencies/auth.py`) should be extended:

```python
@dataclass
class AuthContext:
    hotel_id: int
    user_id: Optional[int] = None
    user_email: Optional[str] = None
    user_role: Optional[str] = None  # Existing legacy field
    is_verified: bool = False
    permissions: Optional[Set[str]] = None  # NEW: permission codes
    roles: Optional[List[str]] = None  # NEW: role slugs
```

### 3. FastAPI Router Registration
Add to main application (e.g., `main.py` or router aggregator):

```python
from app.api.roles import router as roles_router
app.include_router(roles_router)
```

### 4. Database Initialization
On app startup, seed system permissions:

```python
# In startup hook or migration
from app.services.role_service import init_system_permissions
init_system_permissions(db)
```

---

## Migration Path

### Step 1: Create Tables
```bash
alembic revision -m "Add RBAC: User Roles, Permissions, and Relationships"
alembic upgrade head
```

### Step 2: Seed System Permissions
```python
# One-time script
from app.database import get_session_factory
from app.services.role_service import init_system_permissions

factory = get_session_factory()
db = factory()
init_system_permissions(db)
db.close()
```

### Step 3: Create Built-in Roles (per hotel)
```python
# For each existing hotel:
from app.services.role_service import create_role, assign_permissions_to_role

hotel_id = 1
owner_role = create_role(
    db, hotel_id,
    name="Owner",
    slug="owner",
    is_builtin=True,
    permission_ids=[p.id for p in db.query(Permission).all()]  # All perms
)
# Repeat for co_owner, manager, staff
```

### Step 4: Assign Existing Users
```python
# Map existing users to appropriate built-in roles
# (based on their current `user.role` field)
```

---

## Validation Rules

### Permission Creation
- ✓ Code must be unique (e.g., "user:create")
- ✓ Code format: `category:action` (validated via regex/enum)
- ✓ Name must be non-empty and <= 200 chars
- ✓ Category must match known categories
- ✗ Cannot modify is_system after creation

### Role Creation
- ✓ Hotel must exist
- ✓ Slug must be unique per hotel
- ✓ Display name must be unique per hotel
- ✓ Permission IDs must all exist
- ✗ Built-in roles: cannot delete; cannot heavily modify
- ✗ Cannot delete role if users are assigned

### User-Role Assignment
- ✓ User must exist
- ✓ Hotel must exist
- ✓ All role IDs must exist and belong to the hotel
- ✓ Roles must be active (is_active=True)
- ✗ Same user cannot have duplicate role in same hotel (enforced by unique constraint)

---

## Security Considerations

1. **Hotel Isolation**: All role queries are scoped to hotel_id. Roles cannot "leak" across hotels.
2. **Built-in Protection**: System roles and permissions are marked `is_builtin=True` and cannot be deleted.
3. **Audit Trail**: All tables have `created_at` and `updated_at` timestamps. Consider adding an audit log table for mutations.
4. **Permission Granularity**: Permissions are fine-grained and composable; avoid overly broad permissions.
5. **Rate Limiting**: Role assignment endpoints should enforce rate limits to prevent abuse.

---

## Testing Strategy

### Unit Tests
- Permission CRUD and validation
- Role CRUD within hotel scope
- User-role assignment and revocation
- Permission checking (has_permission, has_all_permissions, etc.)

### Integration Tests
- End-to-end API flows (create role → assign permissions → assign to user → check permission)
- Hotel isolation (role from hotel A cannot leak to hotel B)
- Built-in role immutability
- Cascade deletion (deleting hotel → deletes its roles → deletes user-role mappings)

### Authorization Tests
- Verify non-owner users cannot create/modify roles
- Verify only authorized users can call admin endpoints
- Verify permission checks work correctly

---

## Future Enhancements

1. **Dynamic Permissions**: Allow custom permissions per hotel (not just pre-seeded)
2. **Permission Inheritance**: Support role hierarchies (e.g., manager inherits staff permissions)
3. **Audit Logging**: Track who assigned/revoked roles and when
4. **Time-limited Roles**: Support temporary role assignments (expires_at)
5. **Resource-level Permissions**: Extend to support "can edit reservation #123" level granularity
6. **Policy-as-Code**: Use a policy engine (OPA, Cedar) for complex rules

---

## Troubleshooting

### "Role X not found"
- Verify role belongs to correct hotel (all queries include hotel_id filter)
- Check is_active status (some queries filter by is_active=True)

### "Cannot delete built-in role"
- Built-in roles (owner, co_owner, manager, staff) cannot be deleted
- Deactivate with PATCH instead: `is_active=False`

### "Permission denied"
- Verify user is assigned a role in the current hotel
- Check role has required permission
- Use /api/roles/check-permission endpoint to debug

---

## References

- SQLAlchemy ORM: Many-to-Many relationships
- FastAPI: Dependency injection and security
- Role-Based Access Control patterns
