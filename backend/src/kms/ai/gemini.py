"""The real vision adapter: Gemini describes an image or a text file as search metadata.

Each call asks for JSON in the shape of `Metadata`, checks the answer against it and asks the
same model once to fix an answer that does not match. When a model is overloaded the next one
in the list is tried at once; only when every model is overloaded does the caller wait.
"""

import logging
import time
from http import HTTPStatus

import httpx
from google import genai
from google.genai import errors as gemini_errors
from google.genai import types
from pydantic import ValidationError

from kms.ai.errors import ErrorVerdict, RetryPolicy, call_with_retries
from kms.ai.interfaces import Description, PhotoDetails, Vision
from kms.ai.prompts import REPAIR_PROMPT, TEXT_PROMPT, build_image_prompt
from kms.ai.schema import Metadata

logger = logging.getLogger(__name__)

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

    Asking again would get the same refusal, so it is not retryable.
    """


def is_overloaded(error: Exception) -> bool:
    """True when a Gemini model is out of capacity or quota, so the next model may answer now.

    Every Gemini quota is per model, so a model out of quota does not stop the next one.

    Args:
        error: Whatever the Gemini call raised.

    Returns:
        True for a Gemini 429 or 503. Never raises.
    """
    if not isinstance(error, gemini_errors.APIError):
        return False
    return error.code in (HTTPStatus.TOO_MANY_REQUESTS, HTTPStatus.SERVICE_UNAVAILABLE)


def classify_gemini_error(error: Exception) -> ErrorVerdict:
    """Say whether a failed Gemini call is worth trying again, and how long Gemini asked to wait.

    Args:
        error: Whatever the Gemini call raised.

    Returns:
        Retryable for a Gemini 429, 500, 502, 503 or 504 and for a timeout or dropped connection;
        not retryable for anything else, a blocked answer or an invalid one included. The wait
        is Gemini's own when it gave one. Never raises.
    """
    if isinstance(error, gemini_errors.APIError):
        retryable_codes = (
            HTTPStatus.TOO_MANY_REQUESTS,
            HTTPStatus.INTERNAL_SERVER_ERROR,
            HTTPStatus.BAD_GATEWAY,
            HTTPStatus.SERVICE_UNAVAILABLE,
            HTTPStatus.GATEWAY_TIMEOUT,
        )
        if error.code not in retryable_codes:
            return ErrorVerdict(retryable=False, server_wait_seconds=None)
        # Gemini puts the wait in a RetryInfo entry of the error body, as a string like "33s".
        # A body in another shape just means no wait was given.
        wait = None
        try:
            for detail in error.details["error"]["details"]:
                if detail["@type"] == "type.googleapis.com/google.rpc.RetryInfo":
                    wait = float(detail["retryDelay"].removesuffix("s"))
        except (KeyError, TypeError, AttributeError, ValueError):
            wait = None
        return ErrorVerdict(retryable=True, server_wait_seconds=wait)
    # The Gemini SDK lets timeouts and dropped connections through as raw httpx errors.
    if isinstance(error, httpx.TransportError):
        return ErrorVerdict(retryable=True, server_wait_seconds=None)
    return ErrorVerdict(retryable=False, server_wait_seconds=None)


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
        policy: RetryPolicy,
    ) -> Description:
        """Describe one file, falling back through the models and retrying after a wait.

        Args:
            content: The prepared JPEG bytes for an image, the summary text for a text file.
            asset_type: "image" or "text".
            filename: Not sent; the model judges the content, not the name.
            photo_details: When and where the photo was taken, added to the image prompt.
            policy: How hard to try, and how long each request may take.

        Returns:
            The metadata, validated but not normalised, and the model that answered.

        Raises:
            pydantic.ValidationError: The answer still did not match the schema after the
                repair call.
            ContentBlockedError: Gemini refused to answer.
            Exception: A vendor error, unchanged, when it is not retryable or the retries ran out.
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
            lambda: self._describe_with_fallback(contents, policy.timeout_seconds),
            f"gemini_describe {filename}",
            classify_gemini_error,
            policy,
        )

    def _describe_with_fallback(
        self, contents: list[types.Content], timeout_seconds: float
    ) -> Description:
        """Ask each model in turn, moving to the next only when one is overloaded.

        Args:
            contents: The request: the prompt and the image or text.
            timeout_seconds: How long each request may take.

        Returns:
            The first valid answer and the model that gave it.

        Raises:
            Exception: The first error that is not an overload, or the last model's overload
                error when every model was overloaded.
        """
        last_error: Exception | None = None
        for model in self.models:
            try:
                metadata = self._describe_with_model(model, contents, timeout_seconds)
            except Exception as error:
                if not is_overloaded(error):
                    raise
                logger.warning("vision_model_overloaded model=%s error=%r", model, error)
                last_error = error
                continue
            return Description(metadata=metadata, model=model)
        raise last_error

    def _describe_with_model(
        self, model: str, contents: list[types.Content], timeout_seconds: float
    ) -> Metadata:
        """Ask one model, and ask it once more to fix an answer that does not validate.

        The repair call re-sends the whole conversation, image included, so the model can
        correct its answer against what it was shown.

        Args:
            model: The model id.
            contents: The request: the prompt and the image or text.
            timeout_seconds: How long each request may take.

        Returns:
            The validated answer.

        Raises:
            pydantic.ValidationError: The repaired answer is still invalid.
            ContentBlockedError: Gemini refused to answer.
            Exception: A vendor error, unchanged.
        """
        answer = self._generate(model, contents, timeout_seconds)
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
        repaired_answer = self._generate(model, conversation, timeout_seconds)
        return Metadata.model_validate_json(repaired_answer)

    def _generate(self, model: str, contents: list[types.Content], timeout_seconds: float) -> str:
        """Make one Gemini call and return the answer's text.

        Args:
            model: The model id.
            contents: The conversation to send.
            timeout_seconds: How long the request may take; a slower one is lost and raises.

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
            # We pass no tools, so the SDK's automatic function calling has nothing to do; it is
            # on by default and warns on every call unless switched off.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            # The SDK takes the timeout in milliseconds.
            http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000)),
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
