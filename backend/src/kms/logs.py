"""One log format for the whole app: a line per event, `event key=value ...`.

Plain text rather than JSON, so it reads the same in a local terminal and in the platform's log
view, and needs no extra library.
"""

import logging


def configure_logging() -> None:
    """Send INFO and above from every logger to standard error, one line per record.

    Safe to call more than once: `basicConfig` does nothing when logging is already set up.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
