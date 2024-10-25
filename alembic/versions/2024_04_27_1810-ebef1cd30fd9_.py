"""empty message

Revision ID: ebef1cd30fd9
Revises: 793f88201df6
Create Date: 2024-04-27 18:10:35.259313

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ebef1cd30fd9"
down_revision: Union[str, None] = "793f88201df6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "servers",
        sa.Column("game_server_config_id", sa.Integer(), nullable=False),
        schema="manman",
    )
    op.drop_index(
        "ix_manman_servers_game_server_id", table_name="servers", schema="manman"
    )
    op.create_index(
        op.f("ix_manman_servers_game_server_config_id"),
        "servers",
        ["game_server_config_id"],
        unique=False,
        schema="manman",
    )
    op.drop_constraint(
        "servers_game_server_id_fkey", "servers", schema="manman", type_="foreignkey"
    )
    op.create_foreign_key(
        None,
        "servers",
        "game_server_configs",
        ["game_server_config_id"],
        ["game_server_config_id"],
        source_schema="manman",
        referent_schema="manman",
    )
    op.drop_column("servers", "game_server_id", schema="manman")
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "servers",
        sa.Column("game_server_id", sa.INTEGER(), autoincrement=False, nullable=False),
        schema="manman",
    )
    op.drop_constraint(None, "servers", schema="manman", type_="foreignkey")
    op.create_foreign_key(
        "servers_game_server_id_fkey",
        "servers",
        "game_servers",
        ["game_server_id"],
        ["game_server_id"],
        source_schema="manman",
        referent_schema="manman",
    )
    op.drop_index(
        op.f("ix_manman_servers_game_server_config_id"),
        table_name="servers",
        schema="manman",
    )
    op.create_index(
        "ix_manman_servers_game_server_id",
        "servers",
        ["game_server_id"],
        unique=False,
        schema="manman",
    )
    op.drop_column("servers", "game_server_config_id", schema="manman")
    # ### end Alembic commands ###
