import markdown as md
import nh3
from django import template
from django.utils.safestring import mark_safe

from blog.markdown_media import YOUTUBE_EMBED_PREFIX, MediaExtension

register = template.Library()

MARKDOWN_EXTENSIONS = [
    "fenced_code",  # ```python ... ``` code blocks
    "codehilite",  # syntax highlighting via Pygments
    "tables",  # | a | b | tables
    "toc",  # gives every heading an id so you can link to #sections
    "sane_lists",  # stricter, more predictable list handling
    MediaExtension(),  # ![title](video.mp4 or YouTube link) -> video player
]

EXTENSION_CONFIGS = {
    "codehilite": {"css_class": "highlight", "guess_lang": False},
}

ALLOWED_TAGS = nh3.ALLOWED_TAGS | {"video", "iframe"}

# Everything nh3 allows by default, plus class/id so highlighting and heading anchors survive.
ALLOWED_ATTRIBUTES = {tag: set(attrs) for tag, attrs in nh3.ALLOWED_ATTRIBUTES.items()}
ALLOWED_ATTRIBUTES.setdefault("*", set()).update({"class", "id"})
ALLOWED_ATTRIBUTES["a"].add("title")
ALLOWED_ATTRIBUTES["img"].update({"title", "loading"})
ALLOWED_ATTRIBUTES["video"] = {"src", "controls", "preload", "playsinline", "title", "poster"}
ALLOWED_ATTRIBUTES["iframe"] = {"src", "title", "allow", "allowfullscreen", "loading"}


def _only_youtube_iframes(tag, attribute, value):
    """Drop any iframe src that isn't a YouTube embed, so iframes can't load arbitrary sites."""
    if tag == "iframe" and attribute == "src" and not value.startswith(YOUTUBE_EMBED_PREFIX):
        return None
    return value


@register.filter(name="markdown")
def markdown_format(text):
    html = md.markdown(
        text,
        extensions=MARKDOWN_EXTENSIONS,
        extension_configs=EXTENSION_CONFIGS,
    )
    clean = nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        attribute_filter=_only_youtube_iframes,
    )
    return mark_safe(clean)
