# app/AGENTS

- Keep API routers thin.
- Put business rules in `app/services/`, not in routers.
- Preserve hotel scoping, auth, and validation on every sensitive path.
- Update tests for any behavior change in models, services, or APIs.
- Keep Gemma and OTA logic bounded, auditable, and separate from core transactional rules.
- Do not broaden scope without a clear product or security reason.

