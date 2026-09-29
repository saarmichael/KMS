import io
import threading
import time
from types import SimpleNamespace

import pytest
from PIL import Image
from voyageai import error as voyage_errors

from kms.ai import get_embedder
from kms.ai.errors import BACKGROUND_POLICY, RetryPolicy
from kms.ai.voyage import VoyageClients, VoyageEmbedder, classify_voyage_error
from kms.config import get_settings

MODEL = "voyage-test-model"
DIMS = 1024
PARALLEL_CALLS = 20


class StubClient:
    """Stands in for voyageai.Client: records each call and answers with numbered vectors.

    Batches arrive from several threads at once and in any order, so a vector carries its own
    input's number: the number a text ends with ("note 17" gives 17), otherwise the input's
    position in its call. The order of the returned vectors can then be checked.
    """

    def __init__(
        self,
        errors: list[Exception] | None = None,
        vector_length: int | None = None,
        barrier: threading.Barrier | None = None,
        hold_seconds: float = 0.0,
        fail_on: str | None = None,
    ):
        self.errors = errors or []
        self.vector_length = vector_length
        # Every call waits here, so a test can prove that calls are in flight together.
        self.barrier = barrier
        # How long each call takes, so calls in flight overlap.
        self.hold_seconds = hold_seconds
        # A call whose inputs include this text fails with a permanent error.
        self.fail_on = fail_on
        self.calls = []
        self.in_flight = 0
        self.most_in_flight = 0
        self.lock = threading.Lock()

    def multimodal_embed(self, **kwargs):
        with self.lock:
            self.calls.append(kwargs)
            self.in_flight += 1
            self.most_in_flight = max(self.most_in_flight, self.in_flight)
            error = self.errors.pop(0) if self.errors else None
        try:
            if self.barrier is not None:
                self.barrier.wait()
            # An Event's wait, not time.sleep, which the sleeps fixture replaces.
            threading.Event().wait(self.hold_seconds)
            if error is not None:
                raise error
            if self.fail_on is not None and [self.fail_on] in kwargs["inputs"]:
                raise voyage_errors.AuthenticationError("bad key", http_status=401)
            length = self.vector_length or kwargs["output_dimension"]
            embeddings = []
            for position, (piece,) in enumerate(kwargs["inputs"]):
                number = position
                if isinstance(piece, str) and piece.split()[-1].isdigit():
                    number = int(piece.split()[-1])
                embeddings.append([float(number)] * length)
            return SimpleNamespace(embeddings=embeddings)
        finally:
            with self.lock:
                self.in_flight -= 1


class StubClients:
    """Stands in for VoyageClients: hands out one stub client and records each timeout asked for."""

    def __init__(self, client: StubClient):
        self.client = client
        self.timeouts: list[float] = []

    def for_timeout(self, seconds: float) -> StubClient:
        self.timeouts.append(seconds)
        return self.client


@pytest.fixture
def sleeps(monkeypatch):
    # The backoff sleeps through time.sleep; recording instead keeps the tests instant.
    requested = []
    monkeypatch.setattr(time, "sleep", requested.append)
    return requested


def small_jpeg() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(buffer, format="JPEG")
    return buffer.getvalue()


def positions(vectors: list[list[float]]) -> list[int]:
    return [int(vector[0]) for vector in vectors]


def test_texts_and_images_go_in_one_call_in_order(sleeps):
    client = StubClient()
    embedder = VoyageEmbedder(StubClients(client), MODEL, DIMS, PARALLEL_CALLS)
    vectors = embedder.embed(["a note", small_jpeg()], "document", BACKGROUND_POLICY)

    (call,) = client.calls
    text_input, image_input = call["inputs"]
    assert text_input == ["a note"]
    assert len(image_input) == 1
    assert isinstance(image_input[0], Image.Image)
    assert call["model"] == MODEL
    assert call["input_type"] == "document"
    assert call["output_dimension"] == DIMS
    assert positions(vectors) == [0, 1]
    assert all(len(vector) == DIMS for vector in vectors)


def test_more_inputs_than_one_call_takes_are_split_in_order(sleeps):
    client = StubClient()
    texts = [f"note {number}" for number in range(250)]
    vectors = VoyageEmbedder(StubClients(client), MODEL, DIMS, PARALLEL_CALLS).embed(
        texts, "document", BACKGROUND_POLICY
    )

    # The calls may reach the client in any order.
    assert sorted(len(call["inputs"]) for call in client.calls) == [50, 100, 100]
    sent = [piece for call in client.calls for (piece,) in call["inputs"]]
    assert sorted(sent) == sorted(texts)
    assert positions(vectors) == list(range(250))


def test_query_input_type_is_passed_through(sleeps):
    client = StubClient()
    VoyageEmbedder(StubClients(client), MODEL, DIMS, PARALLEL_CALLS).embed(
        ["red car"], "query", BACKGROUND_POLICY
    )
    assert client.calls[0]["input_type"] == "query"


def test_a_transient_error_is_retried(sleeps):
    client = StubClient(errors=[voyage_errors.RateLimitError("slow down", http_status=429)])
    vectors = VoyageEmbedder(StubClients(client), MODEL, DIMS, PARALLEL_CALLS).embed(
        ["a note"], "document", BACKGROUND_POLICY
    )
    assert len(client.calls) == 2
    assert len(sleeps) == 1
    assert len(vectors) == 1
    assert len(vectors[0]) == DIMS


def test_wrong_vector_length_is_an_error(sleeps):
    client = StubClient(vector_length=512)
    with pytest.raises(ValueError, match="length 512"):
        VoyageEmbedder(StubClients(client), MODEL, DIMS, PARALLEL_CALLS).embed(
            ["a note"], "document", BACKGROUND_POLICY
        )


def test_empty_input_makes_no_call(sleeps):
    client = StubClient()
    assert (
        VoyageEmbedder(StubClients(client), MODEL, DIMS, PARALLEL_CALLS).embed(
            [], "document", BACKGROUND_POLICY
        )
        == []
    )
    assert client.calls == []


def test_batches_run_at_the_same_time(sleeps):
    # Three batches meet at the barrier; sent one after another, the first would wait alone
    # until the timeout breaks the barrier and the call fails.
    client = StubClient(barrier=threading.Barrier(3, timeout=5))
    texts = [f"note {number}" for number in range(250)]
    vectors = VoyageEmbedder(StubClients(client), MODEL, DIMS, PARALLEL_CALLS).embed(
        texts, "document", BACKGROUND_POLICY
    )
    assert len(client.calls) == 3
    assert positions(vectors) == list(range(250))


def test_parallel_calls_never_exceed_the_setting(sleeps):
    client = StubClient(hold_seconds=0.05)
    texts = [f"note {number}" for number in range(500)]
    vectors = VoyageEmbedder(StubClients(client), MODEL, DIMS, 2).embed(
        texts, "document", BACKGROUND_POLICY
    )
    assert len(client.calls) == 5
    assert client.most_in_flight == 2
    assert positions(vectors) == list(range(500))


def test_a_failed_batch_fails_the_whole_call(sleeps):
    client = StubClient(fail_on="note 150")
    texts = [f"note {number}" for number in range(250)]
    with pytest.raises(voyage_errors.AuthenticationError):
        VoyageEmbedder(StubClients(client), MODEL, DIMS, PARALLEL_CALLS).embed(
            texts, "document", BACKGROUND_POLICY
        )
    # A permanent error is not retried: one call per batch.
    assert len(client.calls) == 3


def test_real_provider_builds_the_voyage_embedder(real_provider, monkeypatch):
    # A dummy key: building the client makes no call.
    monkeypatch.setenv("VOYAGE_API_KEY", "test-key")
    get_settings.cache_clear()
    embedder = get_embedder()
    assert isinstance(embedder, VoyageEmbedder)
    assert embedder.model == get_settings().embedding_model
    assert embedder.dims == get_settings().embedding_dims
    assert embedder.parallel_calls == get_settings().embed_parallel_calls


def test_real_provider_without_a_key_raises(real_provider, monkeypatch):
    # Empty in the environment, so a key in .env cannot fill it in.
    monkeypatch.setenv("VOYAGE_API_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="VOYAGE_API_KEY"):
        get_embedder()


def test_client_timeout_follows_the_policy(sleeps):
    clients = StubClients(StubClient())
    quick = RetryPolicy(
        max_attempts=1, first_wait_seconds=0.0, max_server_wait_seconds=0.0, timeout_seconds=3.0
    )

    VoyageEmbedder(clients, MODEL, DIMS, PARALLEL_CALLS).embed(["a note"], "query", quick)

    assert clients.timeouts == [3.0]


def test_one_client_per_timeout():
    clients = VoyageClients("test-key")

    five_seconds = clients.for_timeout(5.0)
    three_seconds = clients.for_timeout(3.0)

    assert clients.for_timeout(5.0) is five_seconds
    assert three_seconds is not five_seconds
    # The SDK keeps the timeout among its request settings; its own retries stay off.
    assert three_seconds._params["request_timeout"] == 3.0
    assert three_seconds.max_retries == 0


# --- reading Voyage's errors ---------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        voyage_errors.RateLimitError("slow down", http_status=429),
        voyage_errors.ServerError("broken", http_status=500),
        voyage_errors.APIError("bad gateway", http_status=502),
        voyage_errors.Timeout("timed out"),
        voyage_errors.APIConnectionError("no connection"),
    ],
)
def test_voyage_rate_limit_server_and_network_errors_are_retryable(error):
    verdict = classify_voyage_error(error)

    assert verdict.retryable is True
    assert verdict.server_wait_seconds is None


@pytest.mark.parametrize(
    "error",
    [
        voyage_errors.AuthenticationError("bad key", http_status=401),
        voyage_errors.InvalidRequestError("bad input", http_status=400),
        voyage_errors.MalformedRequestError("unreadable", http_status=422),
        ValueError("not from Voyage"),
    ],
)
def test_voyage_auth_bad_request_and_unknown_errors_are_not_retryable(error):
    assert classify_voyage_error(error).retryable is False
