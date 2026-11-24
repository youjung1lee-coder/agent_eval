from alembic import op
from backend.schema_v1 import metadata, initial_tables

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    metadata.create_all(op.get_bind(), tables=initial_tables)


def downgrade():
    metadata.drop_all(op.get_bind(), tables=initial_tables)
