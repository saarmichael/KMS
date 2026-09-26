"""Spike: describe files with Gemini through response_schema. See README.md."""

import mimetypes
import sys
import time
from pathlib import Path
from typing import Literal

from google import genai
from google.genai import types
from pydantic import BaseModel

from kms.config import get_settings

OUT_DIR = Path(__file__).parent / "out"

PREAMBLE = (
    "You produce search metadata for one file in a knowledge base. People will find this file by "
    "searching for what it shows or says, so be concrete and complete. Return only JSON that "
    "matches the schema.\n\n"
)

IMAGE_PROMPT = PREAMBLE + (
    "Describe this image.\n"
    "title: a short name for the scene.\n"
    "description: 2 to 4 sentences covering people and their visible features (hair colour and "
    "style, clothing), objects, documents or screens, colours and setting.\n"
    "tags: 10 to 20 lowercase single words: objects, attributes, and the kind of image "
    "(photo, screenshot, document, diagram).\n"
    "visible_text: every readable word in the image, verbatim and complete, in reading order; an "
    "empty string if there is none.\n"
    "image_type: one of photo, screenshot, document, diagram, other."
)

TEXT_PROMPT = PREAMBLE + (
    "Summarise this document.\n"
    "title: a short name for the document.\n"
    "description: a 2 to 4 sentence summary.\n"
    "tags: 5 to 15 lowercase topics and named entities.\n"
    "visible_text: an empty string.\n"
    "image_type: null.\n\n"
    "Document:\n"
)


class Metadata(BaseModel):
    """Draft of the design's five fields; the kept model is ai/schema.py, written after this."""

    title: str
    description: str
    tags: list[str]
    visible_text: str
    image_type: Literal["photo", "screenshot", "document", "diagram", "other"] | None


def list_flash_models(client: genai.Client) -> None:
    """Answers the 'exact model id' decision: prints every Flash model the key can see."""
    for model in client.models.list():
        if "flash" in model.name:
            print(f"  {model.name}")


def build_contents(path: Path) -> list:
    mime_type, _ = mimetypes.guess_type(path.name)
    if mime_type and mime_type.startswith("image/"):
        image_part = types.Part.from_bytes(data=path.read_bytes(), mime_type=mime_type)
        return [IMAGE_PROMPT, image_part]
    if path.suffix in (".txt", ".md"):
        return [TEXT_PROMPT + path.read_text(encoding="utf-8")]
    raise SystemExit(f"{path}: not an image or a .txt/.md file")


def describe(client: genai.Client, model: str, path: Path) -> Metadata:
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=Metadata,
    )
    started = time.perf_counter()
    response = client.models.generate_content(
        model=model, contents=build_contents(path), config=config
    )
    elapsed = time.perf_counter() - started
    usage = response.usage_metadata
    print(
        f"--- {path.name}: {elapsed:.2f}s, prompt tokens {usage.prompt_token_count}, "
        f"output tokens {usage.candidates_token_count}, total {usage.total_token_count}"
    )
    print("raw text:")
    print(response.text)
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / f"describe-{path.name}.json").write_text(response.text or "")
    return Metadata.model_validate_json(response.text)


def main() -> None:
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)
    print("flash models available to this key:")
    list_flash_models(client)
    print(f"using: {settings.vision_model}")
    for argument in sys.argv[1:]:
        try:
            metadata = describe(client, settings.vision_model, Path(argument))
        except Exception as error:
            print(f"ERROR {type(error).__module__}.{type(error).__name__}: {vars(error) or error}")
            raise SystemExit(1) from error
        print("validated:")
        print(metadata.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
