"""
Revision ID: 20260205_update_cv_index
Revises: 586594a0af72
Create Date: 2026-02-05
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260205_update_cv_index'
down_revision = '586594a0af72'
branch_labels = None
depends_on = None

def upgrade():
    # Drop old index
    op.drop_index('unique_latest_cv_per_user', table_name='documents')
    # Create new unique index on (user_id, is_latest)
    op.create_index('unique_latest_cv_per_user', 'documents', ['user_id', 'is_latest'], unique=True)

def downgrade():
    # Drop new index
    op.drop_index('unique_latest_cv_per_user', table_name='documents')
    # Recreate old unique index on user_id only
    op.create_index('unique_latest_cv_per_user', 'documents', ['user_id'], unique=True)
