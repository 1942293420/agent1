"""
统一错误码体系 — 对标 api-design-doc 标准

所有 API 错误返回格式：
  {
    "code": 40001,
    "message": "参数校验失败",
    "detail": {...}
  }

错误码分段：
  40001-40099  客户端请求错误（校验、格式）
  40100-40199  认证错误（401）
  40300-40399  权限错误（403）
  40400-40499  资源不存在（404）
  42900-42999  限流（429）
  50001-50099  服务器内部错误（500）
"""

from rest_framework.views import exception_handler
from rest_framework import status
from rest_framework.response import Response


# ─── 错误码注册表 ───

ERROR_CODES = {
    # 400 — 客户端错误
    'validation_failed':         {'code': 40001, 'message': '参数校验失败'},
    'invalid_format':            {'code': 40002, 'message': '数据格式错误'},
    'missing_required':          {'code': 40003, 'message': '缺少必要字段'},
    'duplicate_entry':           {'code': 40004, 'message': '数据重复'},
    'invalid_status':            {'code': 40005, 'message': '无效的状态值'},

    # 401 — 认证错误
    'unauthorized':              {'code': 40100, 'message': '未认证，请提供有效凭证'},
    'hmac_signature_failed':     {'code': 40101, 'message': 'HMAC 签名验证失败'},
    'hmac_timestamp_expired':    {'code': 40102, 'message': '请求时间戳过期'},
    'hmac_missing_headers':      {'code': 40103, 'message': '缺少认证头'},

    # 403 — 权限错误
    'forbidden':                 {'code': 40300, 'message': '无权限访问'},
    'agent_only_endpoint':       {'code': 40301, 'message': '仅 Agent 可访问此端点'},

    # 404 — 资源不存在
    'not_found':                 {'code': 40400, 'message': '资源不存在'},

    # 429 — 限流
    'rate_limited':              {'code': 42900, 'message': '请求过于频繁，请稍后重试'},

    # 500 — 服务器错误
    'internal_error':            {'code': 50000, 'message': '服务器内部错误'},
    'database_error':            {'code': 50001, 'message': '数据库错误'},
}


def custom_exception_handler(exc, context):
    """
    DRF 自定义异常处理器。

    将 DRF 标准异常转为统一错误码格式。
    """
    # 先调用 DRF 默认处理器
    response = exception_handler(exc, context)

    if response is not None:
        # 根据状态码和异常类型映射错误码
        error_key = _map_exception_to_key(exc, response.status_code)
        error_def = ERROR_CODES.get(error_key, ERROR_CODES['internal_error'])

        # 提取详细错误信息
        detail = _extract_detail(exc, response)

        response.data = {
            'code': error_def['code'],
            'message': error_def['message'],
            'detail': detail,
        }

    return response


def _map_exception_to_key(exc, status_code: int) -> str:
    """将异常映射到错误码 key"""
    from rest_framework.exceptions import (
        ValidationError, AuthenticationFailed, NotAuthenticated,
        PermissionDenied, NotFound, Throttled,
    )
    from django.db import IntegrityError

    exc_class = exc.__class__

    if status_code == 400:
        if 'status' in str(exc).lower() or 'invalid' in str(exc).lower():
            return 'invalid_status'
        return 'validation_failed'
    elif status_code == 401:
        msg = str(exc)
        if '签名' in msg or 'signature' in msg.lower():
            return 'hmac_signature_failed'
        elif '时间戳' in msg or 'skew' in msg.lower() or 'timestamp' in msg.lower():
            return 'hmac_timestamp_expired'
        elif '缺少' in msg:
            return 'hmac_missing_headers'
        return 'unauthorized'
    elif status_code == 403:
        msg = str(exc)
        if 'Agent' in msg or 'agent_only' in msg:
            return 'agent_only_endpoint'
        return 'forbidden'
    elif status_code == 404:
        return 'not_found'
    elif status_code == 429:
        return 'rate_limited'
    elif status_code >= 500:
        if isinstance(exc, IntegrityError):
            return 'database_error'
        return 'internal_error'

    return 'internal_error'


def _extract_detail(exc, response) -> dict:
    """提取错误详情"""
    detail = {}

    # DRF 的 ValidationError 包含字段级错误
    if hasattr(exc, 'detail'):
        if isinstance(exc.detail, dict):
            detail = exc.detail
        elif isinstance(exc.detail, list):
            detail = {'errors': exc.detail}
        else:
            detail = {'error': str(exc.detail)}
    elif response.data and isinstance(response.data, dict):
        detail = response.data

    return detail
