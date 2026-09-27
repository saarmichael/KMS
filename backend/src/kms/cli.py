"""`uv run kms <command>`: operational commands."""

import sys


def main() -> None:
    """Run the command named on the command line: `migrate` or `worker`."""
    from kms.logs import configure_logging

    configure_logging()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "migrate":
        from kms.config import get_settings
        from kms.migrations import upgrade_head

        upgrade_head(get_settings().database_url)
        print("migrations: head")
    elif cmd == "worker":
        import threading

        from kms.config import get_settings
        from kms.ingest.pool import WorkerPool

        pool = WorkerPool(get_settings().worker_threads)
        pool.start()
        try:
            # The pool's threads do the work; this thread only waits for Ctrl+C.
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
        finally:
            pool.stop()
    else:
        print("usage: kms migrate | worker")
