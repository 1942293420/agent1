from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .manager import sandbox_manager


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sandbox_status(request):
    session = sandbox_manager.get_or_create(request.user.id)
    return Response({
        "status": session.status,
        "container_name": session.container_name,
        "active_conversations": session.active_conversations,
        "cpu_limit": session.cpu_limit,
        "memory_limit_mb": session.memory_limit_mb,
        "workspace_path": session.workspace_path,
        "created_at": session.created_at,
        "last_active_at": session.last_active_at,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sandbox_exec(request):
    command = request.data.get('command')
    timeout = request.data.get('timeout', 30)
    if not command:
        return Response({"error": "command is required"}, status=400)
    try:
        result = sandbox_manager.exec_cmd(request.user.id, command, int(timeout))
        return Response(result)
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sandbox_destroy(request):
    try:
        sandbox_manager.destroy(request.user.id)
        return Response({"ok": True})
    except Exception as e:
        return Response({"error": str(e)}, status=500)
