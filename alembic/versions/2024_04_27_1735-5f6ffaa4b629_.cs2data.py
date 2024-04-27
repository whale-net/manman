"""cs2 data

Revision ID: 5f6ffaa4b629
Revises: 0df8f684d1c7
Create Date: 2024-04-27 17:35:51.259556

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy.orm import Session

from manman.models import GameServer, GameServerConfig
from manman.worker.server import ServerType


# revision identifiers, used by Alembic.
revision: str = "5f6ffaa4b629"
down_revision: Union[str, None] = "0df8f684d1c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    session = Session(bind=op.get_bind())
    cs2 = GameServer(name="cs2", server_type=ServerType.STEAM, app_id=730)
    session.add(cs2)
    session.flush()

    cs2_config = GameServerConfig(
        game_server_id=cs2.game_server_id,
        is_default=True,
        executable="game/bin/linuxsteamrt64/cs2",
        args=["-dedicated", "-port", "27015", "+map", "de_ancient"],
    )
    session.add(cs2_config)
    session.commit()


def downgrade() -> None:
    # do this shit manually, not touching it here
    pass
