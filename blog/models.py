from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "gif", "webp"]
VIDEO_EXTENSIONS = ["mp4", "webm", "mov"]

MAX_IMAGE_MB = 10
MAX_VIDEO_MB = 200


def validate_image_size(file):
    if file.size > MAX_IMAGE_MB * 1024 * 1024:
        raise ValidationError(f"Images must be under {MAX_IMAGE_MB} MB.")


def validate_media_size(file):
    is_video = Path(file.name).suffix.lower().lstrip(".") in VIDEO_EXTENSIONS
    limit = MAX_VIDEO_MB if is_video else MAX_IMAGE_MB
    if file.size > limit * 1024 * 1024:
        kind = "Videos" if is_video else "Images"
        raise ValidationError(f"{kind} must be under {limit} MB.")


class PublishedManager(models.Manager):
    """Only returns posts that are published and whose publish date has arrived."""

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(status=Post.Status.PUBLISHED, published_at__lte=timezone.now())
        )


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("blog:post_list_by_tag", args=[self.slug])


class Post(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="posts",
    )
    excerpt = models.CharField(
        max_length=300,
        blank=True,
        help_text="Short summary shown on the home page. Leave blank to auto-generate.",
    )
    cover_image = models.ImageField(
        upload_to="covers/%Y/%m/",
        blank=True,
        validators=[validate_image_size],
    )
    cover_alt = models.CharField(
        "cover image description",
        max_length=200,
        blank=True,
        help_text="Describe the image for screen readers and search engines.",
    )
    body = models.TextField(
        help_text=(
            "Supports Markdown: **bold**, ## headings, ```code```, tables, links. "
            "Images: ![alt](url). Videos: ![title](video.mp4) or ![title](YouTube link)."
        )
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.DRAFT
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="posts")
    published_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()  # all posts, including drafts
    published = PublishedManager()  # only live posts

    class Meta:
        ordering = ["-published_at"]
        indexes = [models.Index(fields=["-published_at"])]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("blog:post_detail", args=[self.slug])


class MediaFile(models.Model):
    """An image or video uploaded once and embedded in posts via Markdown."""

    title = models.CharField(max_length=200)
    file = models.FileField(
        upload_to="uploads/%Y/%m/",
        validators=[
            FileExtensionValidator(IMAGE_EXTENSIONS + VIDEO_EXTENSIONS),
            validate_media_size,
        ],
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "media file"

    def __str__(self):
        return self.title

    @property
    def is_video(self):
        return Path(self.file.name).suffix.lower().lstrip(".") in VIDEO_EXTENSIONS

    @property
    def markdown(self):
        return f"![{self.title}]({self.file.url})"


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    name = models.CharField(max_length=80)
    email = models.EmailField(help_text="Never shown publicly.")
    body = models.TextField(max_length=3000)
    approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["post", "approved", "created_at"])]

    def __str__(self):
        return f"{self.name} on {self.post}"
