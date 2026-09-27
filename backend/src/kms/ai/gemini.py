"""The real vision adapter: Gemini describes an image or a text file as search metadata.

Each call asks for JSON in the shape of `Metadata`, checks the answer against it and asks the
same model once to fix an answer that does not match. When a model is overloaded the next one
in the list is tried at once; only when every model is overloaded does the caller wait.
"""

import logging
import time

from google import genai
from google.genai import types
from pydantic import ValidationError

from kms.ai.errors import ErrorKind, call_with_retries, classify
from kms.ai.interfaces import Description, PhotoDetails, Vision
from kms.ai.prompts import REPAIR_PROMPT, TEXT_PROMPT, build_image_prompt
from kms.ai.schema import Metadata

logger = logging.getLogger(__name__)

# Long enough for a large image on a slow model; a call that takes longer is treated as lost
# and retried.
GEMINI_REQUEST_TIMEOUT_SECONDS = 120
# Covers the thinking and the JSON together; the long field is `visible_text` on a page full
# of words.
MAX_OUTPUT_TOKENS = 8192

# The finish reasons that mean Gemini refused to answer, rather than stopped normally.
BLOCKED_FINISH_REASONS = {
    types.FinishReason.SAFETY,
    types.FinishReason.PROHIBITED_CONTENT,
    types.FinishReason.BLOCKLIST,
    types.FinishReason.SPII,
    types.FinishReason.IMAGE_SAFETY,
    types.FinishReason.IMAGE_PROHIBITED_CONTENT,
}


class ContentBlockedError(Exception):
    """Gemini refused to describe the file for safety or policy reasons.

    Asking again would get the same refusal, so it counts as a permanent error.
    """


class GeminiVision(Vision):
    """Describes files with Gemini, walking an ordered list of models.

    Attributes:
        client: The Gemini client, built without the SDK's own retries.
        models: Model ids in the order they are tried; every call starts at the first.
    """

    def __init__(self, client: genai.Client, models: list[str]):
        """Create the adapter.

        Args:
            client: The Gemini client to call through.
            models: Model ids in the order they are tried.
        """
        self.client = client
        self.models = models

    def describe(
        self,
        content: bytes | str,
        asset_type: str,
        filename: str,
        photo_details: PhotoDetails | None,
    ) -> Description:
        """Describe one file, falling back through the models and retrying after a wait.

        Args:
            content: The prepared JPEG bytes for an image, the summary text for a text file.
            asset_type: "image" or "text".
            filename: Not sent; the model judges the content, not the name.
            photo_details: When and where the photo was taken, added to the image prompt.

        Returns:
            The metadata, validated but not normalised, and the model that answered.

        Raises:
            pydantic.ValidationError: The answer still did not match the schema after the
                repair call.
            ContentBlockedError: Gemini refused to answer.
            Exception: A vendor error, unchanged, when it is permanent or the retries ran out.
        """
        if asset_type == "image":
            parts = [
                types.Part.from_text(text=build_image_prompt(photo_details)),
                types.Part.from_bytes(data=content, mime_type="image/jpeg"),
            ]
        else:
            # The text goes in its own part, so the prompt stays the same for every file.
            parts = [
                types.Part.from_text(text=TEXT_PROMPT),
                types.Part.from_text(text=content),
            ]
        contents = [types.Content(role="user", parts=parts)]
        return call_with_retries(
            lambda: self._describe_with_fallback(contents), f"gemini_describe {filename}"
        )

    def _describe_with_fallback(self, contents: list[types.Content]) -> Description:
        """Ask each model in turn, moving to the next only when one is overloaded.

        Args:
            contents: The request: the prompt and the image or text.

        Returns:
            The first valid answer and the model that gave it.

        Raises:
            Exception: The first error that is not an overload, or the last model's overload
                error when every model was overloaded.
        """
        last_error: Exception | None = None
        for model in self.models:
            try:
                metadata = self._describe_with_model(model, contents)
            except Exception as error:
                if classify(error) != ErrorKind.OVERLOADED:
                    raise
                logger.warning("vision_model_overloaded model=%s error=%r", model, error)
                last_error = error
                continue
            return Description(metadata=metadata, model=model)
        raise last_error

    def _describe_with_model(self, model: str, contents: list[types.Content]) -> Metadata:
        """Ask one model, and ask it once more to fix an answer that does not validate.

        The repair call re-sends the whole conversation, image included, so the model can
        correct its answer against what it was shown.

        Args:
            model: The model id.
            contents: The request: the prompt and the image or text.

        Returns:
            The validated answer.

        Raises:
            pydantic.ValidationError: The repaired answer is still invalid.
            ContentBlockedError: Gemini refused to answer.
            Exception: A vendor error, unchanged.
        """
        answer = self._generate(model, contents)
        try:
            return Metadata.model_validate_json(answer)
        except ValidationError as error:
            logger.warning("vision_repair model=%s error=%r", model, error)
            conversation = [
                *contents,
                types.Content(role="model", parts=[types.Part.from_text(text=answer)]),
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=REPAIR_PROMPT.format(error=error))],
                ),
            ]
        repaired_answer = self._generate(model, conversation)
        return Metadata.model_validate_json(repaired_answer)

    def _generate(self, model: str, contents: list[types.Content]) -> str:
        """Make one Gemini call and return the answer's text.

        Args:
            model: The model id.
            contents: The conversation to send.

        Returns:
            The answer's text, or "" when the answer has none.

        Raises:
            ContentBlockedError: The prompt was blocked, or the answer stopped for a safety or
                prohibited-content reason.
            Exception: A vendor error, unchanged.
        """
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Metadata,
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.MINIMAL),
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )
        started = time.perf_counter()
        response = self.client.models.generate_content(
            model=model, contents=contents, config=config
        )
        seconds = time.perf_counter() - started

        # An answer without usage figures still counts; the log then shows None.
        usage = response.usage_metadata or types.GenerateContentResponseUsageMetadata()
        logger.info(
            "vision_call model=%s prompt_tokens=%s output_tokens=%s thinking_tokens=%s "
            "seconds=%.2f",
            model,
            usage.prompt_token_count,
            usage.candidates_token_count,
            usage.thoughts_token_count,
            seconds,
        )

        if response.prompt_feedback is not None and response.prompt_feedback.block_reason:
            reason = response.prompt_feedback.block_reason
            raise ContentBlockedError(f"Gemini blocked the answer: {reason.value}")
        for candidate in response.candidates or []:
            if candidate.finish_reason in BLOCKED_FINISH_REASONS:
                reason = candidate.finish_reason
                raise ContentBlockedError(f"Gemini blocked the answer: {reason.value}")
        return response.text or ""
