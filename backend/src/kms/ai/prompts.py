"""What the vision model is asked, for an image, for a text file, and to fix a bad answer.

The answer's shape is enforced by the schema sent with each call; the prompts say what goes in
each field.
"""

from kms.ai.interfaces import PhotoDetails

# Raised whenever a prompt changes, so a stored answer to the old wording is never replayed
# for the new one.
PROMPT_VERSION = 1

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
    "tags: 10 to 20 lowercase words or short phrases: objects, attributes, and the kind of image "
    "(photo, screenshot, document, diagram).\n"
    "visible_text: every readable word in the image, verbatim and complete, in reading order; an "
    "empty string if there is none.\n"
    "image_type: one of photo, screenshot, document, diagram, other."
)

TEXT_PROMPT = PREAMBLE + (
    "Summarise the document that follows.\n"
    "title: a short name for the document.\n"
    "description: a 2 to 4 sentence summary.\n"
    "tags: 5 to 15 lowercase words or short phrases: topics and named entities.\n"
    "visible_text: an empty string.\n"
    "image_type: null."
)

# Filled with the validation error, so the model sees exactly what was wrong with its answer.
REPAIR_PROMPT = (
    "Your answer did not match the schema. The validation error was:\n"
    "{error}\n\n"
    "Answer again with the complete metadata as JSON that matches the schema."
)


def build_image_prompt(photo_details: PhotoDetails | None) -> str:
    """Return the image prompt, with the photo's date and position when it has them.

    The model is told to use them only when they help, since a date or a position says
    little about a screenshot or a scanned page.

    Args:
        photo_details: When and where the photo was taken, or None when it carries neither.

    Returns:
        IMAGE_PROMPT alone, or followed by a line for the date taken and a line for the
        position, each only when known. Never raises.
    """
    if photo_details is None:
        return IMAGE_PROMPT

    lines = []
    if photo_details.taken_at is not None:
        lines.append(f"The photo was taken on {photo_details.taken_at} (local time).")
    if photo_details.latitude is not None and photo_details.longitude is not None:
        lines.append(
            f"The photo was taken at latitude {photo_details.latitude}, "
            f"longitude {photo_details.longitude}."
        )
    if not lines:
        return IMAGE_PROMPT

    lines.append(
        "Use this only when it helps: name the place and the time of day, season or year in "
        "the description and the tags."
    )
    return IMAGE_PROMPT + "\n\n" + "\n".join(lines)
