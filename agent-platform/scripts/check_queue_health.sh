#!/bin/bash
# AgentOS 队列积压告警脚本
# 用法: ./check_queue_health.sh
# 建议 cron: */1 * * * * /home/jiangli/projects/agent-platform/scripts/check_queue_health.sh

REDIS_CLI="redis-cli"
QUEUE_KEY="msg_queue"
WARN_THRESHOLD=100
CRIT_THRESHOLD=500
LOG_FILE="$HOME/.hermes/profiles/Banni/logs/queue-health.log"

QUEUE_LEN=$($REDIS_CLI LLEN "$QUEUE_KEY" 2>/dev/null)
if [ -z "$QUEUE_LEN" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Redis 不可达" >> "$LOG_FILE"
    exit 1
fi

if [ "$QUEUE_LEN" -gt "$CRIT_THRESHOLD" ]; then
    LEVEL="CRITICAL"
    MSG="🚨 msg_queue 严重积压: $QUEUE_LEN 条 (阈值=$CRIT_THRESHOLD)"
elif [ "$QUEUE_LEN" -gt "$WARN_THRESHOLD" ]; then
    LEVEL="WARNING"
    MSG="⚠️ msg_queue 积压告警: $QUEUE_LEN 条 (阈值=$WARN_THRESHOLD)"
else
    # 正常，静默
    exit 0
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] $LEVEL: $MSG" >> "$LOG_FILE"

# Worker 状态检查
WORKER_STATUS=$(systemctl --user is-active agent-worker 2>/dev/null)
if [ "$WORKER_STATUS" != "active" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Worker 未运行 (status=$WORKER_STATUS)" >> "$LOG_FILE"
fi

# 活跃线程数（从 Worker 日志提取）
ACTIVE=$(journalctl --user -u agent-worker --since "2 min ago" --no-pager 2>/dev/null | \
    grep "活跃线程" | tail -1 | grep -oP '活跃线程=\K\d+')
if [ -n "$ACTIVE" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] INFO: 活跃线程=$ACTIVE/20" >> "$LOG_FILE"
fi

# 日志轮转（保留最近 1000 行）
tail -1000 "$LOG_FILE" > "$LOG_FILE.tmp" 2>/dev/null && mv "$LOG_FILE.tmp" "$LOG_FILE"
