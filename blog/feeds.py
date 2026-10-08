from django.conf import settings
from django.contrib.syndication.views import Feed
from django.urls import reverse_lazy

from .models import Post
from .templatetags.markdown_extras import markdown_format


class LatestPostsFeed(Feed):
    title = settings.BLOG_TITLE
    description = settings.BLOG_DESCRIPTION
    link = reverse_lazy("blog:post_list")

    def items(self):
        return Post.published.select_related("author").prefetch_related("tags")[:20]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        # Full post as HTML, so readers can read it right inside their RSS app.
        return markdown_format(item.body)

    def item_pubdate(self, item):
        return item.published_at

    def item_updateddate(self, item):
        return item.updated_at

    def item_author_name(self, item):
        return item.author.get_full_name() or item.author.username

    def item_categories(self, item):
        return [tag.name for tag in item.tags.all()]
