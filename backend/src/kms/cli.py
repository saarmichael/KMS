"""`uv run kms <command>`: operational commands."""

import sys


def main() -> None:
    """Run the command named on the command line; `migrate` is the only one."""
    from kms.logs import configure_logging

    configure_logging()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "migrate":
        from kms.config import get_settings
        from kms.migrations import upgrade_head

        upgrade_head(get_settings().database_url)
        print("migrations: head")
    else:
        print("usage: kms migrate")
