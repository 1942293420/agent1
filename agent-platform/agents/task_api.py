"""多Agent协同 API — 任务状态机"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.utils import timezone

from .models import ParentTask, ChildTask, Message


@api_view(['POST'])
@permission_classes([AllowAny])
def parent_task_create(request):
    """创建父任务（用户消息到达时调用）"""
    conversation_id = request.data.get('conversation_id')
    user_message = request.data.get('user_message', '')
    source = request.data.get('source', 'web')

    pt = ParentTask.objects.create(
        conversation_id=conversation_id,
        user_message=user_message,
        source=source,
        status=ParentTask.Status.PENDING,
        expires_at=timezone.now() + timezone.timedelta(minutes=30),
    )
    return Response({'id': pt.id, 'status': pt.status})


@api_view(['POST', 'PATCH'])
@permission_classes([AllowAny])
def parent_task_update(request, pk):
    """更新父任务状态 / dispatch_plan / final_reply"""
    try:
        pt = ParentTask.objects.get(pk=pk)
    except ParentTask.DoesNotExist:
        return Response({'error': 'not found'}, status=404)

    for field in ['status', 'dispatch_plan', 'final_reply']:
        if field in request.data:
            setattr(pt, field, request.data[field])

    if request.data.get('status') == ParentTask.Status.REPLY:
        pt.completed_at = timezone.now()

    pt.yunshu_call_count = pt.yunshu_call_count + 1
    pt.save()
    return Response({'id': pt.id, 'status': pt.status})


@api_view(['POST'])
@permission_classes([AllowAny])
def child_task_create(request):
    """创建子任务"""
    pt = ParentTask.objects.get(pk=request.data['parent_id'])
    ct = ChildTask.objects.create(
        parent=pt,
        agent_name=request.data['agent_name'],
        agent_profile=request.data['agent_profile'],
        task_prompt=request.data['task_prompt'],
        status=ChildTask.Status.PENDING,
    )
    return Response({'id': ct.id, 'status': ct.status})


@api_view(['POST', 'PATCH'])
@permission_classes([AllowAny])
def child_task_update(request, pk):
    """更新子任务状态 / result / heartbeat"""
    try:
        ct = ChildTask.objects.get(pk=pk)
    except ChildTask.DoesNotExist:
        return Response({'error': 'not found'}, status=404)

    for field in ['status', 'result', 'pid', 'hermes_session_id', 'error_info']:
        if field in request.data:
            setattr(ct, field, request.data[field])

    if request.data.get('status') == ChildTask.Status.RUNNING and not ct.started_at:
        ct.started_at = timezone.now()

    if request.data.get('status') in ('DONE', 'FAILED', 'TIMED_OUT'):
        ct.finished_at = timezone.now()

    ct.heartbeat_at = timezone.now()
    ct.save()
    return Response({'id': ct.id, 'status': ct.status})


@api_view(['GET'])
@permission_classes([AllowAny])
def child_task_heartbeat(request, pk):
    """子进程心跳（简单版：只更新 heartbeat_at）"""
    ChildTask.objects.filter(pk=pk).update(heartbeat_at=timezone.now())
    return Response({'ok': True})
