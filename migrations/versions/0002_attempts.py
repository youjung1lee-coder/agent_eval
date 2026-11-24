from alembic import op
from backend.schema_v2 import attempts

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    attempts.create(op.get_bind(), checkfirst=True)


def downgrade():
    attempts.drop(op.get_bind(), checkfirst=True)
