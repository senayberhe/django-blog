from django.urls import path

from . import views
from .feeds import LatestPostsFeed

app_name = "blog"

urlpatterns = [
    path("", views.post_list, name="post_list"),
    path("search/", views.search, name="search"),
    path("feed/", LatestPostsFeed(), name="post_feed"),
    path("tag/<slug:tag_slug>/", views.post_list, name="post_list_by_tag"),
    path("post/<slug:slug>/", views.post_detail, name="post_detail"),
]
