"""
SSE (Server-Sent Events) — 实时事件流

端点: GET /api/events/

事件类型:
  agent-update  — Agent 在线状态变化
  task-update   — 任务状态变化
  worker-pulse  — Worker cron 心跳
  heartbeat     — 连接存活信号
"""
import json, time
from datetime import timedelta
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

from .models import Agent, Task, CronJob


@api_view(['GET'])
@permission_classes([AllowAny])
def event_stream(request):
    def generate():
        last_check = timezone.now() - timedelta(seconds=10)
        cycle = 0

        while True:
            cycle += 1

            # Agent 状态变化
            changed_agents = Agent.objects.filter(
                updated_at__gt=last_check
            ).values('id', 'name', 'status', 'last_heartbeat')
            for agent in changed_agents:
                data = {
                    'type': 'agent-update',
                    'agent_id': agent['id'],
                    'name': agent['name'],
                    'status': agent['status'],
                    'last_heartbeat': agent['last_heartbeat'].isoformat() if agent['last_heartbeat'] else None,
                }
                yield f"event: agent-update\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

            # 任务状态变化
            changed_tasks = Task.objects.filter(
                updated_at__gt=last_check
            ).select_related('agent').values(
                'id', 'title', 'status', 'priority', 'agent__name', 'updated_at',
            )
            for task in changed_tasks:
                data = {
                    'type': 'task-update',
                    'task_id': task['id'],
                    'title': task['title'],
                    'status': task['status'],
                    'priority': task['priority'],
                    'agent_name': task['agent__name'],
                }
                yield f"event: task-update\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

            # Worker 心跳：每 30 秒推送一次
            if cycle % 15 == 0:
                workers = CronJob.objects.filter(name__icontains='Worker').values(
                    'job_id', 'name', 'schedule', 'agent__name',
                    'last_run_at', 'last_status', 'next_run_at', 'enabled',
                )
                for w in workers:
                    data = {
                        'type': 'worker-pulse',
                        'job_id': w['job_id'],
                        'name': w['name'],
                        'agent_name': w['agent__name'],
                        'schedule': w['schedule'],
                        'last_run_at': w['last_run_at'].isoformat() if w['last_run_at'] else None,
                        'last_status': w['last_status'],
                        'next_run_at': w['next_run_at'].isoformat() if w['next_run_at'] else None,
                        'enabled': w['enabled'],
                    }
                    yield f"event: worker-pulse\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

            # 心跳
            yield f"event: heartbeat\ndata: {{\"ts\":\"{timezone.now().isoformat()}\",\"cycle\":{cycle}}}\n\n"

            last_check = timezone.now()
            time.sleep(2)

    response = StreamingHttpResponse(generate(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    response['Access-Control-Allow-Origin'] = '*'
    return response
