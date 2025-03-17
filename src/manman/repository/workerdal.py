from sqlmodel import and_, func, update

from manman.models import Worker
from manman.util import get_sqlalchemy_session


def close_other_workers(worker_id: int) -> int:
    with get_sqlalchemy_session() as sess:
        stmt = (
            update(Worker)
            .where(
                and_(
                    Worker.worker_id != worker_id,
                    Worker.end_date.is_(
                        None
                    ),  # SQLModel translates this to IS NULL in SQL
                )
            )
            .values(end_date=func.now())
        )
        result = sess.exec(stmt)
        affected_rows = result.rowcount  # Get number of rows affected
        sess.commit()
        return affected_rows
