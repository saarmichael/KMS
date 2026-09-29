"""`uv run kms <command>`: operational commands."""

import sys
from pathlib import Path
from typing import TYPE_CHECKING

# Only for the type hint: importing the worker loads the database and vendor libraries, which
# `migrate` and `worker` should not pay for at start-up.
if TYPE_CHECKING:
    from kms.ingest.worker import PreparedFile

USAGE = "usage: kms migrate | worker | describe <file> | embed <file>..."


def load_file(path: Path) -> tuple[str, "PreparedFile"]:
    """Read a file and prepare it exactly as the worker would.

    Args:
        path: The file on disk.

    Returns:
        `(asset_type, prepared)`: "image" or "text", and the prepared inputs for the AI calls.

    Raises:
        OSError: The file cannot be read, or an image's bytes cannot be decoded.
        UnsupportedFileType: The bytes are neither an accepted image nor UTF-8 text.
    """
    from kms.ingest.upload import sniff
    from kms.ingest.worker import prepare_file

    data = path.read_bytes()
    asset_type, _mime = sniff(data)
    return asset_type, prepare_file(data, asset_type)


def describe_command(path: Path) -> int:
    """Describe one file with the vision model and print the answer as JSON on stdout.

    Args:
        path: The file on disk; its name is the filename the model is given.

    Returns:
        0 on success; 1 when anything fails, after printing the error on stderr.
    """
    import dataclasses
    import json

    from kms.ai import get_vision
    from kms.ai.errors import BACKGROUND_POLICY

    try:
        asset_type, prepared = load_file(path)
        description = get_vision().describe(
            prepared.content, asset_type, path.name, prepared.photo_details, BACKGROUND_POLICY
        )
    except Exception as error:
        # A command-line tool reports any failure as one line and an exit code, not a traceback.
        print(f"error: {type(error).__name__}: {error}", file=sys.stderr)
        return 1

    photo_details = None
    if prepared.photo_details is not None:
        photo_details = dataclasses.asdict(prepared.photo_details)
    result = {
        "model": description.model,
        "photo_details": photo_details,
        "metadata": description.metadata.model_dump(),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def embed_command(paths: list[Path]) -> int:
    """Embed the files' content inputs in one call and print a line per vector on stdout.

    An image contributes its prepared JPEG, a text file one input per chunk: what the worker
    embeds apart from the metadata and filename units.

    Args:
        paths: The files on disk.

    Returns:
        0 on success; 1 when anything fails, after printing the error on stderr.
    """
    import math
    import time

    from kms.ai import get_embedder
    from kms.ai.errors import BACKGROUND_POLICY

    labels = []
    inputs = []
    try:
        for path in paths:
            asset_type, prepared = load_file(path)
            if asset_type == "image":
                labels.append((path, "image", 0))
                inputs.append(prepared.prepared_image)
            else:
                for index, chunk in enumerate(prepared.chunks):
                    labels.append((path, "content", index))
                    inputs.append(chunk.text)
        embedder = get_embedder()
        started = time.monotonic()
        vectors = embedder.embed(inputs, "document", BACKGROUND_POLICY)
        seconds = time.monotonic() - started
    except Exception as error:
        # A command-line tool reports any failure as one line and an exit code, not a traceback.
        print(f"error: {type(error).__name__}: {error}", file=sys.stderr)
        return 1

    for (path, kind, index), vector in zip(labels, vectors, strict=True):
        norm = math.sqrt(sum(value * value for value in vector))
        first_values = [round(value, 4) for value in vector[:4]]
        print(f"{path} {kind} {index} dims={len(vector)} norm={norm:.4f} {first_values}")
    print(f"model={embedder.model} inputs={len(inputs)} seconds={seconds:.2f}")
    return 0


def main() -> None:
    """Run the command named on the command line: `migrate`, `worker`, `describe` or `embed`."""
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
    elif cmd == "describe":
        if len(sys.argv) < 3:
            print(USAGE, file=sys.stderr)
            sys.exit(2)
        sys.exit(describe_command(Path(sys.argv[2])))
    elif cmd == "embed":
        if len(sys.argv) < 3:
            print(USAGE, file=sys.stderr)
            sys.exit(2)
        paths = [Path(argument) for argument in sys.argv[2:]]
        sys.exit(embed_command(paths))
    else:
        print(USAGE)
