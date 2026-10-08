from django.conf import settings


def blog_settings(request):
    """Make the blog's name and tagline available in every template."""
    return {
        "BLOG_TITLE": settings.BLOG_TITLE,
        "BLOG_DESCRIPTION": settings.BLOG_DESCRIPTION,
    }
