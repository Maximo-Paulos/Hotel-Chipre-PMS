# Automatic no-show sweep

The no-show sweep is database-only: it marks eligible overdue reservations as
`no_show`, keeps payment and deposit records unchanged, and never issues a
charge or refund. The same runner is available to Celery and as a one-shot CLI.

The current production workspace has no connected Celery worker/Beat. To add
the periodic runner without provisioning Redis or a worker, create a separate
Render Blueprint using `render-no-show-cron.yaml` as its Blueprint file path.
The file references the existing `hotel-backend` service's `DATABASE_URL`; it
does not copy database credentials into the repository. Keep it separate from
the root `render.yaml`, which declares additional resources.

The schedule runs once an hour at minute 10 UTC. The Cron process uses one
database connection and exits unsuccessfully if any hotel reconciliation
fails, so Render records failed runs for investigation. Render bills Cron by
active runtime and has a minimum monthly charge of USD 1 per Cron service.
Creating or activating this service requires owner approval of that recurring
charge and the automatic status transitions on production reservations.
