import os
import sys

# Ensure the root directory is on Python path so all modules can be imported
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app import app

class VercelPathFixMiddleware:
    """WSGI middleware to normalize PATH_INFO when Vercel rewrites routes to /api/index.py."""
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        # When Vercel rewrites all incoming routes (e.g. /, /login, /dashboard) to /api/index.py,
        # restore the original requested path so Flask's URL routing matches correctly.
        if path.startswith('/api/index.py') or path.startswith('/api/index'):
            orig_path = (
                environ.get('HTTP_X_MATCHED_PATH')
                or environ.get('HTTP_X_INVOKE_PATH')
                or environ.get('HTTP_X_FORWARDED_URI')
            )
            if orig_path and not (orig_path.startswith('/api/index.py') or orig_path.startswith('/api/index')):
                environ['PATH_INFO'] = orig_path
            else:
                suffix = path.replace('/api/index.py', '').replace('/api/index', '')
                environ['PATH_INFO'] = suffix if suffix else '/'
        return self.wsgi_app(environ, start_response)

# Apply WSGI middleware
app.wsgi_app = VercelPathFixMiddleware(app.wsgi_app)
