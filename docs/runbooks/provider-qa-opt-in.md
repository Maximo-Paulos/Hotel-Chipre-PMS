# Provider QA opt-in for pull requests

The `operating-system` job in `release-gate.yml` and the
`trusted-base-evidence` job in `trusted-release-gate.yml` are opt-in. They run
only while a pull request has the `require-provider-qa` label. Adding or
removing that label triggers both workflows again; the jobs run when the label
is present and skip when it is absent.

The regular backend, frontend, E2E, and contract checks are unchanged. A normal
pull request does not require Render QA. Add the label when provider-bound QA
evidence is explicitly requested; the existing isolated-preview, provenance,
and signature validations remain in force for that run.

`PR Validation` is triggered by `pull_request` events only, so backend,
frontend, and E2E checks run once for each pull request event/update. Source
branch pushes do not start a duplicate validation run.

Local tests and sessions against a shared production deployment do not qualify
as isolated provider evidence. Do not use them as substitutes when the opt-in
gate is enabled.
