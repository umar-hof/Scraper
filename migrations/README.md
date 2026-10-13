Alembic-compatible migration location. The worker currently creates the minimal schema on startup for a zero-friction pilot; production teams may run `alembic init` and generate a reviewed migration from `app.models.Base.metadata` before first deployment.

