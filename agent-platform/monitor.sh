#!/bin/bash
# AgentOS 任务监控 — 实时追踪新建和状态变化
API="http://localhost:8001/api/tasks/?page_size=30&ordering=-created_at"
LAST_STATE="/tmp/agentos_monitor_state"

echo "🔍 AgentOS 任务监控已启动 (每5秒)"
echo "   符号: 🆕新建 ⚙️执行中 ✅完成 ❌失败 🎯云枢"
echo "=========================================="

# 初始状态快照
curl -s "$API" | python3 -c "
import json,sys
data = json.load(sys.stdin)
for t in data.get('results',[]):
    print(f\"{t['id']}|{t['status']}")
" > "$LAST_STATE"

echo "✅ 监控就绪，等待新任务/状态变化..."
echo ""

while true; do
    sleep 5
    curl -s "$API" | python3 -c "
import json,sys
data = json.load(sys.stdin)
tasks = data.get('results',[])
last = {}
try:
    with open('$LAST_STATE') as f:
        for line in f:
            line = line.strip()
            if '|' in line:
                tid, st = line.split('|',1)
                last[tid] = st
except: pass

with open('$LAST_STATE','w') as f:
    for t in tasks:
        tid = str(t['id'])
        status = t['status']
        title = t['title'][:50]
        is_orch = t.get('contract',{}).get('orchestrator',False)
        orchid = '🎯云枢' if is_orch else ''
        prev = last.get(tid)
        f.write(f\"{tid}|{status}\n\")
        if prev is None:
            print(f\"🆕 Task#{tid} [{status}] {orchid} {title}\")
        elif prev != status:
            emo = {'in_progress':'⚙️','completed':'✅','failed':'❌','pending':'⏳'}.get(status,'🔄')
            print(f\"{emo} Task#{tid} {prev}→{status} {orchid} {title}\")
" 2>/dev/null
done
