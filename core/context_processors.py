from django.conf import settings


def product_flags(request):
    return {
        "sales_demo_mode": getattr(settings, "SALES_DEMO_MODE", False),
        "show_social_in_sales_demo": getattr(settings, "SHOW_SOCIAL_IN_SALES_DEMO", False),
        "enable_chat": getattr(settings, "ENABLE_CHAT", True),
        "show_social_navigation": (
            getattr(settings, "SHOW_SOCIAL_IN_SALES_DEMO", False)
            or not getattr(settings, "SALES_DEMO_MODE", False)
        ),
    }
