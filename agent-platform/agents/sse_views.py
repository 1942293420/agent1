"""
SSE (Server-Sent Events) 实时推送视图
"""
import json, time, redis
from django.http import StreamingHttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from .models import ParentTask, TaskNode, ChildTask, ProgressEvent


def _get_redis():
    return redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)


def _sse(event_type, data):
    return f"event: {event_type}\ndata: {json.dumps(data, default=str)}\n\n"


@api_view(['GET'])
@permission_classes([AllowAny])
def parent_task_progress_stream(request, pk):
    r = _get_redis()
    channel = f'task:progress:{pk}'

    def gen():
        pubsub = r.pubsub()
        pubsub.subscribe(channel)
        try:
            pt = ParentTask.objects.get(pk=pk)
            nodes = TaskNode.objects.filter(parent_task=pt).order_by('seq')
            nodes_data = [{
                'node_id': n.node_id, 'label': n.label, 'description': n.description,
                'agent_name': n.agent_name, 'depends_on': n.depends_on,
                'status': n.status, 'duration_ms': n.duration_ms,
                'is_bottleneck': n.is_bottleneck, 'bottleneck_reason': n.bottleneck_reason,
                'seq': n.seq, 'started_at': str(n.started_at) if n.started_at else None,
                'finished_at': str(n.finished_at) if n.finished_at else None,
            } for n in nodes]
            total = len(nodes_data)
            done = sum(1 for n in nodes if n.status == 'done')
            yield _sse('init', {
                'parentId': pk, 'parentStatus': pt.status,
                'nodes': nodes_data,
                'stats': {'total': total, 'done': done,
                    'running': sum(1 for n in nodes if n.status == 'running'),
                    'pending': sum(1 for n in nodes if n.status == 'pending'),
                    'failed': sum(1 for n in nodes if n.status in ('failed','timed_out')),
                    'bottleneckCount': sum(1 for n in nodes if n.is_bottleneck),
                    'progressPct': round(done/max(total,1)*100, 1)},
            })
        except ParentTask.DoesNotExist:
            yield _sse('error', {'message': f'Not found: {pk}'})
            return

        last_hb = time.time()
        try:
            while True:
                msg = pubsub.get_message(timeout=5.0)
                if msg and msg['type'] == 'message':
                    try:
                        data = json.loads(msg['data'])
                        yield _sse(data.get('event_type', 'node_status'), data)
                    except json.JSONDecodeError:
                        pass
                now = time.time()
                if now - last_hb >= 15:
                    try:
                        pt = ParentTask.objects.get(pk=pk)
                        nodes = TaskNode.objects.filter(parent_task=pt)
                        total = nodes.count()
                        done = nodes.filter(status='done').count()
                        yield _sse('stats_update', {
                            'parentStatus': pt.status,
                            'total': total, 'done': done,
                            'running': nodes.filter(status='running').count(),
                            'pending': nodes.filter(status='pending').count(),
                            'failed': nodes.filter(status__in=('failed','timed_out')).count(),
                            'bottleneckCount': nodes.filter(is_bottleneck=True).count(),
                            'progressPct': round(done/max(total,1)*100,1),
                        })
                        if pt.status in ('REPLY','FAILED'):
                            yield _sse('parent_done', {'status': pt.status, 'finalReply': pt.final_reply})
                            break
                    except ParentTask.DoesNotExist:
                        break
                    last_hb = now
        finally:
            pubsub.unsubscribe(channel)

    response = StreamingHttpResponse(gen(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    response['Access-Control-Allow-Origin'] = '*'
    return response


@api_view(['GET'])
@permission_classes([AllowAny])
def parent_task_progress_snapshot(request, pk):
    try:
        pt = ParentTask.objects.get(pk=pk)
        nodes = TaskNode.objects.filter(parent_task=pt).order_by('seq')
        nodes_data = [{
            'nodeId': n.node_id, 'label': n.label, 'description': n.description,
            'agentName': n.agent_name, 'dependsOn': n.depends_on,
            'status': n.status, 'durationMs': n.duration_ms,
            'isBottleneck': n.is_bottleneck, 'bottleneckReason': n.bottleneck_reason,
            'seq': n.seq,
            'startedAt': str(n.started_at) if n.started_at else None,
            'finishedAt': str(n.finished_at) if n.finished_at else None,
        } for n in nodes]
        total = len(nodes_data)
        done = sum(1 for n in nodes if n.status == 'done')
        from rest_framework.response import Response
        return Response({
            'parentId': pk, 'parentStatus': pt.status, 'nodes': nodes_data,
            'stats': {'total': total, 'done': done,
                'running': sum(1 for n in nodes if n.status == 'running'),
                'pending': sum(1 for n in nodes if n.status == 'pending'),
                'failed': sum(1 for n in nodes if n.status in ('failed','timed_out')),
                'bottleneckCount': sum(1 for n in nodes if n.is_bottleneck),
                'progressPct': round(done/max(total,1)*100,1)},
        })
    except ParentTask.DoesNotExist:
        from rest_framework.response import Response
        return Response({'error': 'Not found'}, status=404)
