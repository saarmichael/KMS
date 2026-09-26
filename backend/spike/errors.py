"""Spike: what each SDK does with a bad key and with a burst of requests. See README.md."""

import sys
import time

import voyageai
from google import genai
from google.genai import types

from kms.config import get_settings

SETTINGS = get_settings()
TRANSIENT_STATUSES = [429, 500, 502, 503, 504]


def report(error: Exception) -> None:
    print(f"  {type(error).__module__}.{type(error).__name__}: {vars(error) or error}")


def bad_key(vendor: str) -> None:
    print(f"== {vendor}: bad key")
    started = time.perf_counter()
    try:
        if vendor == "gemini":
            client = genai.Client(api_key="invalid")
            client.models.generate_content(model=SETTINGS.vision_model, contents="hi")
        else:
            client = voyageai.Client(api_key="invalid")
            client.multimodal_embed(inputs=[["hi"]], model=SETTINGS.embedding_model)
        print("  no error raised")
    except Exception as error:
        report(error)
    print(f"  {time.perf_counter() - started:.2f}s")


def burst(vendor: str, count: int, sdk_retries: bool) -> None:
    print(f"== {vendor}: burst of {count}, SDK retries {'on' if sdk_retries else 'off'}")
    if vendor == "gemini":
        retry_options = None
        if sdk_retries:
            retry_options = types.HttpRetryOptions(
                attempts=4,
                initial_delay=1.0,
                max_delay=16.0,
                exp_base=2.0,
                jitter=0.5,
                http_status_codes=TRANSIENT_STATUSES,
            )
        client = genai.Client(
            api_key=SETTINGS.gemini_api_key,
            http_options=types.HttpOptions(retry_options=retry_options),
        )

        def call() -> None:
            client.models.generate_content(
                model=SETTINGS.vision_model, contents="Reply with the single word ok."
            )

    else:
        client = voyageai.Client(
            api_key=SETTINGS.voyage_api_key, max_retries=3 if sdk_retries else 0
        )

        def call() -> None:
            client.multimodal_embed(
                inputs=[["ok"]], model=SETTINGS.embedding_model, input_type="document"
            )

    for index in range(count):
        started = time.perf_counter()
        try:
            call()
            outcome = "ok"
        except Exception as error:
            status = getattr(error, "code", None) or getattr(error, "http_status", None)
            outcome = f"{type(error).__name__} {status or ''} {getattr(error, 'message', '')}"[:160]
        print(f"  {index + 1:2d} {time.perf_counter() - started:6.2f}s {outcome}")


def main() -> None:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    bad_key("gemini")
    bad_key("voyage")
    burst("gemini", count, sdk_retries=False)
    burst("gemini", count, sdk_retries=True)
    burst("voyage", count, sdk_retries=False)
    burst("voyage", count, sdk_retries=True)


if __name__ == "__main__":
    main()
