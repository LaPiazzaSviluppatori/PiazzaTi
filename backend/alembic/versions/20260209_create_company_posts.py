"""
Migration Alembic: crea tabella company_posts
"""
from alembic import op
import sqlalchemy as sa
import uuid

revision = '20260209_create_company_posts'
down_revision = '586594a0af72_004_schema_hardening_enums_indexes_'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'company_posts',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('company_id', sa.String(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('images', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )

def downgrade():
    op.drop_table('company_posts')
