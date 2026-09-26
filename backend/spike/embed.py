"""Spike: one mixed text + image batch through Voyage, then a synonym check. See README.md."""

import json
import math
import time
from pathlib import Path

import voyageai
from PIL import Image

from kms.config import get_settings

SAMPLES = Path(__file__).parent / "samples"
OUT_DIR = Path(__file__).parent / "out"


def embed(client: voyageai.Client, model: str, inputs: list, input_type: str) -> list[list[float]]:
    started = time.perf_counter()
    result = client.multimodal_embed(inputs=inputs, model=model, input_type=input_type)
    elapsed = time.perf_counter() - started
    print(
        f"--- {input_type}: {len(result.embeddings)} vectors x {len(result.embeddings[0])} dims, "
        f"text tokens {result.text_tokens}, image pixels {result.image_pixels}, "
        f"total tokens {result.total_tokens}, {elapsed:.2f}s"
    )
    return result.embeddings


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    return dot / (norm_a * norm_b)


def main() -> None:
    settings = get_settings()
    client = voyageai.Client(api_key=settings.voyage_api_key)
    print(f"using: {settings.embedding_model}")

    documents = {
        "brunette sentence": "A brunette woman in a red coat waits at a bus stop.",
        "unrelated sentence": "Quarterly tax filing deadlines for small businesses.",
        "note.txt": (SAMPLES / "note.txt").read_text(encoding="utf-8"),
    }
    screenshot = Image.open(SAMPLES / "screenshot.png")
    inputs = [[text] for text in documents.values()] + [[screenshot]]
    labels = list(documents) + ["screenshot"]

    try:
        document_vectors = embed(client, settings.embedding_model, inputs, "document")
        [query_vector] = embed(client, settings.embedding_model, [["black hair"]], "query")
    except Exception as error:
        print(f"ERROR {type(error).__module__}.{type(error).__name__}: {vars(error) or error}")
        raise SystemExit(1) from error

    first_norm = math.sqrt(sum(x * x for x in document_vectors[0]))
    print(f"L2 norm of first document vector: {first_norm:.4f}")
    for label, vector in zip(labels, document_vectors, strict=True):
        print(f"cosine(black hair, {label}) = {cosine(query_vector, vector):.4f}")

    OUT_DIR.mkdir(exist_ok=True)
    recorded = {"query": query_vector, **dict(zip(labels, document_vectors, strict=True))}
    (OUT_DIR / "embed.json").write_text(json.dumps(recorded))


if __name__ == "__main__":
    main()
