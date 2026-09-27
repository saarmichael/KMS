"""Run the worker in background threads: several workers, one listener, one reaper.

The listener holds the process's single LISTEN connection and wakes every worker when an asset
is announced. Workers also check the queue every POLL_SECONDS on their own, so an asset is still
picked up while the listener is reconnecting or a notification was missed.
"""

import logging
import threading

from kms.db import ASSET_PENDING_CHANNEL, listen_connection
from kms.ingest.worker import reaper, run_once

logger = logging.getLogger(__name__)

# The longest a worker waits before checking the queue again.
POLL_SECONDS = 1
REAPER_INTERVAL_SECONDS = 60
# How long the listener waits before reconnecting after losing its connection.
RECONNECT_SECONDS = 1
# How long stop() waits for each thread.
STOP_TIMEOUT_SECONDS = 5


class WorkerPool:
    """The worker threads, the listener thread and the reaper thread of one process.

    Attributes:
        thread_count: How many worker threads `start` runs.
    """

    def __init__(self, thread_count: int) -> None:
        """Prepare the pool; no thread runs until `start`.

        Args:
            thread_count: How many worker threads to run.
        """
        self.thread_count = thread_count
        self._stop = threading.Event()
        # Set by the listener on every notification; the workers wait on it between drains.
        self._wake = threading.Event()
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        """Start the worker threads, the listener thread and the reaper thread."""
        for number in range(1, self.thread_count + 1):
            worker = threading.Thread(target=self._work_loop, name=f"worker-{number}", daemon=True)
            self._threads.append(worker)
        listener = threading.Thread(target=self._listen_loop, name="listener", daemon=True)
        self._threads.append(listener)
        reaper_thread = threading.Thread(target=self._reap_loop, name="reaper", daemon=True)
        self._threads.append(reaper_thread)

        for thread in self._threads:
            thread.start()
        logger.info("pool_started threads=%d", self.thread_count)

    def stop(self) -> None:
        """Ask every thread to finish and wait for each up to STOP_TIMEOUT_SECONDS.

        Never raises. A thread still busy after its timeout is left behind; it is a daemon
        thread, so it does not keep the process alive, and its asset's lease runs out.
        """
        self._stop.set()
        # Workers sleep on the wake event, so setting it too ends their wait at once.
        self._wake.set()
        for thread in self._threads:
            thread.join(STOP_TIMEOUT_SECONDS)
        logger.info("pool_stopped")

    def _work_loop(self) -> None:
        """Drain the queue, then sleep until woken or POLL_SECONDS pass; repeat until stopped.

        The wake event is cleared before draining, so a notification that arrives mid-drain
        leaves it set and the next wait returns at once: no announced asset is missed.
        """
        while not self._stop.is_set():
            self._wake.clear()
            try:
                # Checked between assets, so a stopping worker finishes its current asset and quits.
                while not self._stop.is_set() and run_once():
                    pass
            except Exception as error:
                # The database dropped while claiming; the loop keeps going and tries again.
                logger.warning("worker_error error=%r", f"{type(error).__name__}: {error}")
            self._wake.wait(POLL_SECONDS)

    def _listen_loop(self) -> None:
        """Hold the LISTEN connection and set the wake event on each notification.

        Waits in slices of one second so a stop is noticed. A lost connection is logged and
        opened again after RECONNECT_SECONDS; the workers keep polling in the meantime.
        """
        while not self._stop.is_set():
            try:
                with listen_connection(ASSET_PENDING_CHANNEL) as connection:
                    logger.info("listener_connected channel=%s", ASSET_PENDING_CHANNEL)
                    while not self._stop.is_set():
                        for _notification in connection.notifies(timeout=1):
                            self._wake.set()
            except Exception as error:
                logger.warning("listener_lost error=%r", f"{type(error).__name__}: {error}")
                self._stop.wait(RECONNECT_SECONDS)

    def _reap_loop(self) -> None:
        """Run the reaper now and then every REAPER_INTERVAL_SECONDS until stopped."""
        while not self._stop.is_set():
            try:
                reaper()
            except Exception as error:
                # The database dropped; the next round tries again.
                logger.warning("reaper_error error=%r", f"{type(error).__name__}: {error}")
            self._stop.wait(REAPER_INTERVAL_SECONDS)
