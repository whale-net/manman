import logging
import io

logger = logging.getLogger(__name__)


def log_stream(
    stream: io.IOBase | None,
    prefix: str | None = None,
    logger: logging.Logger = logger,
    max_lines: int | None = None,
):
    if prefix is None:
        prefix = ""

    if stream is None:
        logger.info(f"cannot read, stream is empty prefix=[{prefix}]")
        return

    line_count = 0
    while True:
        if max_lines is not None and line_count >= max_lines:
            logger.info(
                "exiting stream read early %s of %s max lines read",
                line_count,
                max_lines,
            )
            break

        line = stream.readline()
        if line is None or len(line) == 0:
            break
        logger.info("%s%s", prefix, line.decode("utf-8").rstrip())
        line_count += 1

    logger.info("finished reading stream")
