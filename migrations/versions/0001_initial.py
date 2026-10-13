"""Create the operational schema from the reviewed SQLAlchemy metadata."""
from alembic import op
from app.models import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    Base.metadata.create_all(bind=op.get_bind())

def downgrade():
    # The first production migration is intentionally non-destructive on downgrade.
    pass
