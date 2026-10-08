from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from .models import Comment, MediaFile, Post, Tag


def media_preview(file, is_video, height):
    if not file:
        return "—"
    if is_video:
        return format_html(
            '<video src="{}" style="max-height:{}px" controls preload="metadata"></video>',
            file.url,
            height,
        )
    return format_html('<img src="{}" style="max-height:{}px;border-radius:4px">', file.url, height)


@admin.register(MediaFile)
class MediaFileAdmin(admin.ModelAdmin):
    list_display = ["thumbnail", "title", "markdown_snippet", "uploaded_at"]
    list_display_links = ["thumbnail", "title"]
    search_fields = ["title"]
    readonly_fields = ["preview", "markdown_snippet"]
    fields = ["title", "file", "preview", "markdown_snippet"]

    @admin.display(description="")
    def thumbnail(self, obj):
        return media_preview(obj.file, obj.is_video, 60)

    @admin.display(description="Preview")
    def preview(self, obj):
        return media_preview(obj.file, obj.is_video, 300)

    @admin.display(description="Paste into a post")
    def markdown_snippet(self, obj):
        if not obj.file:
            return "Save first to get the Markdown snippet."
        return format_html(
            '<input type="text" value="{}" readonly onclick="this.select()" '
            'style="width:28rem;max-width:100%;font-family:monospace">',
            obj.markdown,
        )


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["name", "short_body", "post", "created_at", "approved"]
    list_filter = ["approved", "created_at"]
    list_editable = ["approved"]
    search_fields = ["name", "email", "body"]
    list_select_related = ["post"]
    actions = ["approve", "unapprove"]

    @admin.display(description="Comment")
    def short_body(self, obj):
        return obj.body[:60] + ("…" if len(obj.body) > 60 else "")

    @admin.action(description="Approve selected comments")
    def approve(self, request, queryset):
        updated = queryset.update(approved=True)
        self.message_user(request, f"{updated} comment(s) approved.")

    @admin.action(description="Unapprove selected comments")
    def unapprove(self, request, queryset):
        updated = queryset.update(approved=False)
        self.message_user(request, f"{updated} comment(s) hidden.")


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    fields = ["name", "email", "body", "approved", "created_at"]
    readonly_fields = ["created_at"]


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "post_count"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(post_count=Count("posts"))

    @admin.display(ordering="post_count", description="Posts")
    def post_count(self, obj):
        return obj.post_count


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ["title", "status", "published_at", "author"]
    list_filter = ["status", "published_at", "tags"]
    search_fields = ["title", "body"]
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ["tags"]
    inlines = [CommentInline]
    readonly_fields = ["cover_preview"]
    fieldsets = [
        (None, {"fields": ["title", "slug", "author", "status", "published_at", "tags"]}),
        ("Cover image", {"fields": ["cover_image", "cover_preview", "cover_alt"]}),
        ("Content", {"fields": ["excerpt", "body"]}),
    ]

    @admin.display(description="Current cover")
    def cover_preview(self, obj):
        return media_preview(obj.cover_image, False, 200)
    date_hierarchy = "published_at"
    ordering = ["status", "-published_at"]

    def get_changeform_initial_data(self, request):
        # New posts default to the logged-in user as author.
        return {"author": request.user.pk}
