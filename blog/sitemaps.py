from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Post, Tag


class PostSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.9

    def items(self):
        return Post.published.all()

    def lastmod(self, obj):
        return obj.updated_at


class TagSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.5

    def items(self):
        return Tag.objects.filter(posts__in=Post.published.all()).distinct()


class StaticSitemap(Sitemap):
    changefreq = "daily"
    priority = 1.0

    def items(self):
        return ["blog:post_list"]

    def location(self, item):
        return reverse(item)


sitemaps = {"static": StaticSitemap, "posts": PostSitemap, "tags": TagSitemap}
