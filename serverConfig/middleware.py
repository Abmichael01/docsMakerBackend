class MediaCorsMiddleware:
    """
    Middleware to add CORS headers specifically for media files in development
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Check if this is a media file request
        if request.path.startswith('/media/'):
            response["Access-Control-Allow-Origin"] = "*"
            response["Cross-Origin-Resource-Policy"] = "cross-origin"
            response["Cross-Origin-Embedder-Policy"] = "credentialless"
        
        return response
