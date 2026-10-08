from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CommentForm
from .models import Post, Tag


def post_list(request, tag_slug=None):
    posts = Post.published.select_related("author").prefetch_related("tags")
    tag = None
    if tag_slug:
        tag = get_object_or_404(Tag, slug=tag_slug)
        posts = posts.filter(tags=tag)

    paginator = Paginator(posts, 5)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "blog/post_list.html", {"page_obj": page_obj, "tag": tag})


def search(request):
    query = request.GET.get("q", "").strip()[:100]
    page_obj = None

    if query:
        posts = Post.published.all()
        # Every word must appear somewhere: "django tags" finds posts mentioning both.
        for term in query.split()[:10]:
            posts = posts.filter(
                Q(title__icontains=term)
                | Q(excerpt__icontains=term)
                | Q(body__icontains=term)
                | Q(tags__name__icontains=term)
            )
        posts = (
            posts.distinct()
            .annotate(
                title_match=Case(
                    When(title__icontains=query, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            )
            .order_by("-title_match", "-published_at")
            .select_related("author")
            .prefetch_related("tags")
        )
        page_obj = Paginator(posts, 10).get_page(request.GET.get("page"))

    return render(request, "blog/search.html", {"query": query, "page_obj": page_obj})


def post_detail(request, slug):
    post = get_object_or_404(
        Post.published.select_related("author").prefetch_related("tags"), slug=slug
    )

    if request.method == "POST":
        form = CommentForm(request.POST)
        if form.is_valid():
            if not form.is_spam():
                comment = form.save(commit=False)
                comment.post = post
                comment.save()
            # Bots get the same success message so they can't tell they were caught.
            messages.success(request, "Thanks! Your comment will appear once it's approved.")
            return redirect(post)
    else:
        form = CommentForm()

    comments = post.comments.filter(approved=True)

    # Related posts: other published posts ranked by how many tags they share with this one.
    related_posts = (
        Post.published.filter(tags__in=post.tags.all())
        .exclude(pk=post.pk)
        .annotate(shared_tags=Count("tags"))
        .order_by("-shared_tags", "-published_at")[:3]
    )
    return render(
        request,
        "blog/post_detail.html",
        {"post": post, "related_posts": related_posts, "comments": comments, "form": form},
    )
