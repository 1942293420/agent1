"""
Middleware: 豁免所有 /api/ 路径的 CSRF 检查。
DRF @api_view 与 Django csrf_exempt 存在兼容性问题。
"""
from django.utils.deprecation import MiddlewareMixin


class APICSRFExemptMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.path.startswith('/api/'):
            setattr(request, '_dont_enforce_csrf_checks', True)
