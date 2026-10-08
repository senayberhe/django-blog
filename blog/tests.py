import shutil
import tempfile
from datetime import timedelta
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.forms import modelform_factory
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from PIL import Image

from .models import MAX_IMAGE_MB, Comment, MediaFile, Post, Tag, validate_image_size
from .templatetags.markdown_extras import markdown_format


class PostViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = get_user_model().objects.create_user("writer", password="pw")
        cls.live = Post.objects.create(
            title="Hello World", author=cls.author, body="First!", status=Post.Status.PUBLISHED
        )
        cls.draft = Post.objects.create(title="Secret Draft", author=cls.author, body="WIP")
        cls.scheduled = Post.objects.create(
            title="Future Post",
            author=cls.author,
            body="Soon",
            status=Post.Status.PUBLISHED,
            published_at=timezone.now() + timedelta(days=1),
        )

    def test_slug_is_generated_from_title(self):
        self.assertEqual(self.live.slug, "hello-world")

    def test_list_shows_only_live_posts(self):
        response = self.client.get("/")
        self.assertContains(response, "Hello World")
        self.assertNotContains(response, "Secret Draft")
        self.assertNotContains(response, "Future Post")

    def test_detail_page(self):
        response = self.client.get(self.live.get_absolute_url())
        self.assertContains(response, "First!")

    def test_draft_detail_returns_404(self):
        response = self.client.get(self.draft.get_absolute_url())
        self.assertEqual(response.status_code, 404)

    def test_custom_404_page(self):
        response = self.client.get("/post/no-such-post/")
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "This page doesn", status_code=404)


class TagTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        author = get_user_model().objects.create_user("writer", password="pw")
        cls.python = Tag.objects.create(name="Python")
        cls.django = Tag.objects.create(name="Django")
        cls.life = Tag.objects.create(name="Life")

        def publish(title, *tags):
            post = Post.objects.create(
                title=title, author=author, body="...", status=Post.Status.PUBLISHED
            )
            post.tags.set(tags)
            return post

        cls.main = publish("Main Post", cls.python, cls.django)
        cls.both = publish("Shares Both", cls.python, cls.django)
        cls.one = publish("Shares One", cls.python)
        cls.none = publish("Shares None", cls.life)

    def test_tag_slug_is_generated(self):
        self.assertEqual(self.python.slug, "python")

    def test_tag_page_filters_posts(self):
        response = self.client.get(self.life.get_absolute_url())
        self.assertContains(response, "Posts tagged")
        self.assertContains(response, "Shares None")
        self.assertNotContains(response, "Main Post")

    def test_unknown_tag_returns_404(self):
        response = self.client.get("/tag/does-not-exist/")
        self.assertEqual(response.status_code, 404)

    def test_related_posts_ranked_by_shared_tags(self):
        response = self.client.get(self.main.get_absolute_url())
        related = list(response.context["related_posts"])
        self.assertEqual(related, [self.both, self.one])

    def test_list_page_query_count(self):
        # 1 count for paginator + 1 for posts/authors + 1 prefetch for tags = 3,
        # no matter how many posts are on the page.
        with self.assertNumQueries(3):
            self.client.get("/")


class CommentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        author = get_user_model().objects.create_user("writer", password="pw")
        cls.post = Post.objects.create(
            title="Commentable", author=author, body="...", status=Post.Status.PUBLISHED
        )
        cls.url = cls.post.get_absolute_url()
        cls.valid = {"name": "Ana", "email": "ana@example.com", "body": "Great post!"}

    def test_valid_comment_is_saved_unapproved_and_redirects(self):
        response = self.client.post(self.url, self.valid, follow=True)
        self.assertRedirects(response, self.url)
        self.assertContains(response, "will appear once it")
        comment = Comment.objects.get()
        self.assertEqual(comment.post, self.post)
        self.assertFalse(comment.approved)
        self.assertNotContains(response, "Great post!")  # hidden until approved

    def test_approved_comment_is_shown(self):
        self.post.comments.create(**self.valid, approved=True)
        response = self.client.get(self.url)
        self.assertContains(response, "Great post!")
        self.assertContains(response, "1 comment")
        self.assertNotContains(response, "ana@example.com")  # email stays private

    def test_invalid_comment_shows_errors_and_keeps_input(self):
        response = self.client.post(self.url, {**self.valid, "email": "not-an-email"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a valid email address.")
        self.assertContains(response, "Great post!")  # user's text is preserved
        self.assertFalse(Comment.objects.exists())

    def test_honeypot_silently_drops_spam(self):
        response = self.client.post(self.url, {**self.valid, "website": "spam.biz"}, follow=True)
        self.assertContains(response, "will appear once it")
        self.assertFalse(Comment.objects.exists())

    def test_cannot_self_approve(self):
        self.client.post(self.url, {**self.valid, "approved": "on"})
        self.assertFalse(Comment.objects.get().approved)

    def test_comment_html_is_escaped(self):
        self.post.comments.create(**{**self.valid, "body": "<script>alert(1)</script>"}, approved=True)
        response = self.client.get(self.url)
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;")

    def test_post_without_csrf_token_is_rejected(self):
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post(self.url, self.valid)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Comment.objects.exists())


class DiscoveryTests(TestCase):
    """Search, RSS feed, sitemap and robots.txt."""

    @classmethod
    def setUpTestData(cls):
        author = get_user_model().objects.create_user("writer", password="pw")
        cls.django_tag = Tag.objects.create(name="Django")

        def publish(title, body, **kwargs):
            return Post.objects.create(
                title=title, author=author, body=body, status=Post.Status.PUBLISHED, **kwargs
            )

        cls.title_hit = publish("Learning Python", "Notes from week one.")
        cls.body_hit = publish("Weekend", "I spent the weekend with python and coffee.")
        cls.tagged = publish("Building a blog", "Models, views, templates.")
        cls.tagged.tags.add(cls.django_tag)
        cls.draft = Post.objects.create(title="Python draft", author=author, body="secret")

    def search(self, q):
        return list(self.client.get("/search/", {"q": q}).context["page_obj"])

    def test_search_matches_title_and_body_with_title_first(self):
        self.assertEqual(self.search("python"), [self.title_hit, self.body_hit])

    def test_search_matches_tag_names(self):
        self.assertEqual(self.search("django"), [self.tagged])

    def test_search_requires_every_word(self):
        self.assertEqual(self.search("python coffee"), [self.body_hit])

    def test_search_never_returns_drafts(self):
        self.assertNotIn(self.draft, self.search("draft"))

    def test_empty_search_shows_prompt(self):
        response = self.client.get("/search/")
        self.assertContains(response, "Type something")
        self.assertIsNone(response.context["page_obj"])

    def test_search_pagination_keeps_query(self):
        for i in range(11):
            Post.objects.create(
                title=f"Python {i}", author=self.title_hit.author, body="x",
                status=Post.Status.PUBLISHED,
            )
        response = self.client.get("/search/", {"q": "python"})
        self.assertContains(response, "?q=python&amp;page=2")

    def test_feed_contains_published_posts_only(self):
        response = self.client.get("/feed/")
        self.assertEqual(response["Content-Type"], "application/rss+xml; charset=utf-8")
        self.assertContains(response, "Learning Python")
        self.assertContains(response, "<category>Django</category>")
        self.assertNotContains(response, "Python draft")

    def test_sitemap_lists_posts_and_tags_but_not_drafts(self):
        response = self.client.get("/sitemap.xml")
        self.assertContains(response, self.title_hit.get_absolute_url())
        self.assertContains(response, self.django_tag.get_absolute_url())
        self.assertNotContains(response, self.draft.get_absolute_url())

    def test_robots_txt_points_to_sitemap(self):
        response = self.client.get("/robots.txt")
        self.assertContains(response, "Disallow: /admin/")
        self.assertContains(response, "Sitemap: http://testserver/sitemap.xml")

    def test_blog_title_comes_from_settings(self):
        with self.settings(BLOG_TITLE="Pat's Notes"):
            response = self.client.get("/")
        self.assertContains(response, "<title>Pat&#x27;s Notes</title>", html=False)


def make_image(name="cover.png"):
    buffer = BytesIO()
    Image.new("RGB", (10, 10), "blue").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class MediaTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def test_cover_image_is_shown(self):
        author = get_user_model().objects.create_user("writer", password="pw")
        post = Post.objects.create(
            title="With Cover",
            author=author,
            body="...",
            status=Post.Status.PUBLISHED,
            cover_image=make_image(),
            cover_alt="A blue square",
        )
        self.assertTrue(post.cover_image.name.startswith("covers/"))
        for url in ["/", post.get_absolute_url()]:
            response = self.client.get(url)
            self.assertContains(response, post.cover_image.url)
            self.assertContains(response, 'alt="A blue square"')

    def test_fake_image_is_rejected(self):
        PostCoverForm = modelform_factory(Post, fields=["cover_image"])
        fake = SimpleUploadedFile("cat.png", b"definitely not an image", content_type="image/png")
        form = PostCoverForm(files={"cover_image": fake})
        self.assertFalse(form.is_valid())
        self.assertIn("cover_image", form.errors)

    def test_media_file_rejects_wrong_extension(self):
        media = MediaFile(title="Bad", file=SimpleUploadedFile("script.exe", b"MZ"))
        with self.assertRaises(ValidationError):
            media.full_clean()

    def test_media_file_markdown_and_type(self):
        video = MediaFile.objects.create(
            title="Clip", file=SimpleUploadedFile("clip.mp4", b"\x00\x00\x00\x18ftypmp42")
        )
        self.assertTrue(video.is_video)
        self.assertEqual(video.markdown, f"![Clip]({video.file.url})")

    def test_oversized_image_is_rejected(self):
        big = SimpleUploadedFile("big.png", b"0" * (MAX_IMAGE_MB * 1024 * 1024 + 1))
        with self.assertRaises(ValidationError):
            validate_image_size(big)


class MarkdownFilterTests(TestCase):
    def test_video_file_becomes_player(self):
        html = markdown_format("![Demo](/media/uploads/demo.mp4)")
        self.assertIn('<video controls=""', html)
        self.assertIn('src="/media/uploads/demo.mp4"', html)

    def test_youtube_link_becomes_privacy_embed(self):
        for link in [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
        ]:
            html = markdown_format(f"![Talk]({link})")
            self.assertIn('src="https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"', html)

    def test_regular_image_stays_image_and_lazy(self):
        html = markdown_format("![Cat](/media/cat.jpg)")
        self.assertIn("<img", html)
        self.assertIn('loading="lazy"', html)

    def test_iframe_to_other_site_loses_src(self):
        html = markdown_format('<iframe src="https://evil.example/"></iframe>')
        self.assertNotIn("evil.example", html)

    def test_renders_markdown(self):
        html = markdown_format("## Title\n\n**bold** and `code`")
        self.assertIn('<h2 id="title">Title</h2>', html)
        self.assertIn("<strong>bold</strong>", html)
        self.assertIn("<code>code</code>", html)

    def test_highlights_fenced_code(self):
        html = markdown_format("```python\ndef hi():\n    pass\n```")
        self.assertIn('class="highlight"', html)
        self.assertIn('<span class="k">def</span>', html)

    def test_strips_dangerous_html(self):
        html = markdown_format(
            '<script>alert(1)</script>\n\n<a href="javascript:alert(1)" onclick="x()">click</a>'
        )
        self.assertNotIn("<script", html)
        self.assertNotIn("javascript:", html)
        self.assertNotIn("onclick", html)
