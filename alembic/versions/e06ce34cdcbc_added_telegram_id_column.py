"""Added telegram_id column

Revision ID: e06ce34cdcbc
Revises: 29bf54ed6456
Create Date: 2021-01-24 16:48:23.311745

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e06ce34cdcbc'
down_revision = '29bf54ed6456'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('players', sa.Column('telegram_id', sa.BIGINT(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('players', 'telegram_id')
    # ### end Alembic commands ###
