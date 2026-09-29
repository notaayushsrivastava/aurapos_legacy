import os
import sys

# Ensure the root directory is on Python path so all modules can be imported
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app import app

class VercelPathFixMiddleware:
    """WSGI middleware to normalize PATH_INFO when Vercel rewrites routes to /api/index.py or /api/index."""
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        
        # Candidate headers where edge proxies and Vercel preserve the original URL path
        candidate_headers = [
            'HTTP_X_MATCHED_PATH',
            'HTTP_X_INVOKE_PATH',
            'HTTP_X_FORWARDED_URI',
            'HTTP_X_ORIGINAL_URI',
            'HTTP_X_ORIGINAL_URL',
            'HTTP_X_REWRITE_URL',
            'REQUEST_URI',
            'RAW_URI',
        ]
        
        # Check if the incoming request path was rewritten to the serverless function handler
        if path in ('/api/index.py', '/api/index', '/api', '/api/index.py/', '/api/index/'):
            resolved_path = None
            for hdr in candidate_headers:
                val = environ.get(hdr)
                if val:
                    # Strip query strings if present in URI headers
                    clean_val = val.split('?')[0]
                    if clean_val and clean_val not in ('/api/index.py', '/api/index', '/api', '/api/index.py/', '/api/index/'):
                        resolved_path = clean_val
                        break
            
            environ['PATH_INFO'] = resolved_path if resolved_path else '/'
        
        return self.wsgi_app(environ, start_response)

# Apply WSGI middleware
app.wsgi_app = VercelPathFixMiddleware(app.wsgi_app)
