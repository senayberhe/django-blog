"""Markdown extension: turn ![title](url) into a video player when url is a video.

    ![Demo](/media/uploads/2026/10/demo.mp4)      -> <video controls>
    ![Talk](https://youtu.be/dQw4w9WgXcQ)          -> YouTube embed
    ![Cat](/media/uploads/2026/10/cat.jpg)         -> normal <img> (unchanged)
"""

import re
from pathlib import PurePosixPath
from urllib.parse import urlparse

from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor

from .models import VIDEO_EXTENSIONS

YOUTUBE_ID = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})"
)
YOUTUBE_EMBED_PREFIX = "https://www.youtube-nocookie.com/embed/"


class MediaTreeprocessor(Treeprocessor):
    def run(self, root):
        for el in root.iter("img"):
            src = el.get("src", "")
            title = el.get("alt", "")
            youtube = YOUTUBE_ID.search(src)

            if youtube:
                el.tag = "iframe"
                el.attrib.clear()
                el.set("src", YOUTUBE_EMBED_PREFIX + youtube.group(1))
                el.set("title", title or "YouTube video")
                el.set("allow", "accelerometer; encrypted-media; gyroscope; picture-in-picture")
                el.set("allowfullscreen", "")
                el.set("loading", "lazy")
                el.set("class", "embed")
            elif PurePosixPath(urlparse(src).path).suffix.lower().lstrip(".") in VIDEO_EXTENSIONS:
                el.tag = "video"
                el.attrib.clear()
                el.set("src", src)
                el.set("controls", "")
                el.set("preload", "metadata")
                el.set("playsinline", "")
                if title:
                    el.set("title", title)
            else:
                el.set("loading", "lazy")


class MediaExtension(Extension):
    def extendMarkdown(self, md):
        # Priority 15 runs after "inline" (20), which is what creates the <img> elements.
        md.treeprocessors.register(MediaTreeprocessor(md), "media", 15)
