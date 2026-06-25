"""
Middleware: 豁免 /api/admin/ 路径的 CSRF 检查。
Django 的 csrf_exempt 与 DRF @api_view 存在兼容性问题，
URL 级别和装饰器方式均无法稳定豁免。
"""
from django.utils.deprecation import MiddlewareMixin


class AdminCSRFExemptMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.path.startswith('/api/admin/'):
            setattr(request, '_dont_enforce_csrf_checks', True)
