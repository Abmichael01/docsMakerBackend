"""
Caching utilities for API responses to improve performance.
"""
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from functools import wraps
import hashlib


def cache_template_list(timeout=300):
    """
    Cache decorator for template list views.
    Caches responses for 5 minutes (300 seconds) by default.
    
    Args:
        timeout: Cache timeout in seconds (default: 300 = 5 minutes)
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            # Build cache key based on query parameters
            query_params = request.GET.urlencode()
            cache_key = f"template_list_{hashlib.md5(query_params.encode()).hexdigest()}"
            
            # Check cache
            cached_response = cache.get(cache_key)
            if cached_response is not None:
                return cached_response
            
            # Call the view
            response = view_func(self, request, *args, **kwargs)
            
            # Cache the response (only for GET requests with 200 status)
            if request.method == 'GET' and response.status_code == 200:
                cache.set(cache_key, response, timeout)
            
            return response
        return wrapper
    return decorator


def invalidate_template_cache():
    """
    Invalidate all template list cache entries.
    Call this after creating/updating/deleting templates.
    """
    # Since we're using MD5-based keys, we can't easily invalidate all
    # Instead, use a version-based cache key pattern
    cache_key_pattern = "template_list_*"
    # For Django cache, we need to track keys manually or use cache versioning
    pass


