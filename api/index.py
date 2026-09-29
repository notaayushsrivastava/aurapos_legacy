import os
import sys
import urllib.parse

# Ensure the root directory is on Python path so all modules can be imported
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app import app

class VercelPathFixMiddleware:
    """WSGI middleware to normalize PATH_INFO and QUERY_STRING when Vercel rewrites routes to /api/index.py."""
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        qs = environ.get('QUERY_STRING', '')
        
        # 1. Primary path restoration: Read captured __vpath from Vercel rewrite destination
        if '__vpath=' in qs or '__vpath' in qs:
            qs_dict = urllib.parse.parse_qs(qs, keep_blank_values=True)
            vpath_list = qs_dict.pop('__vpath', None)
            if vpath_list is not None:
                raw_vpath = vpath_list[0] if vpath_list else ''
                target_path = '/' + raw_vpath.lstrip('/') if raw_vpath else '/'
                environ['PATH_INFO'] = target_path
                environ['QUERY_STRING'] = urllib.parse.urlencode(qs_dict, doseq=True)
                return self.wsgi_app(environ, start_response)
        
        # 2. Candidate headers fallback if edge proxy forwarded original URI
        candidate_headers = [
            'HTTP_X_MATCHED_PATH',
            'HTTP_X_INVOKE_PATH',
            'HTTP_X_FORWARDED_URI',
            'HTTP_X_ORIGINAL_URI',
            'HTTP_X_ORIGINAL_URL',
            'HTTP_X_REWRITE_URL',
        ]
        
        if path in ('/api/index.py', '/api/index', '/api', '/api/index.py/', '/api/index/'):
            resolved_path = None
            for hdr in candidate_headers:
                val = environ.get(hdr)
                if val:
                    clean_val = val.split('?')[0]
                    if clean_val and clean_val not in ('/api/index.py', '/api/index', '/api', '/api/index.py/', '/api/index/'):
                        resolved_path = clean_val
                        break
            
            environ['PATH_INFO'] = resolved_path if resolved_path else '/'
        
        return self.wsgi_app(environ, start_response)

# Apply WSGI middleware
app.wsgi_app = VercelPathFixMiddleware(app.wsgi_app)
