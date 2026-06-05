#!/bin/bash
# 儿童打卡任务 - 每日备份脚本
# 备份数据库 + 代码，保留最近 3 份

BACKUP_DIR="/www/backup/kids-tasks"
APP_DIR="/www/wwwroot/kids-tasks"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/kids-tasks_${DATE}.tar.gz"

mkdir -p "$BACKUP_DIR"

# 备份数据库、代码、配置（排除 __pycache__ 和 wheelhouse）
tar czf "$BACKUP_FILE" \
  -C "$APP_DIR" \
  --exclude='__pycache__' \
  --exclude='wheelhouse' \
  --exclude='*.tar.gz' \
  . 2>/dev/null

if [ $? -eq 0 ]; then
  echo "✅ 备份成功: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"
else
  echo "❌ 备份失败"
  exit 1
fi

# 保留最近 3 份，删除更早的
cd "$BACKUP_DIR"
ls -1t kids-tasks_*.tar.gz 2>/dev/null | tail -n +4 | xargs -r rm -f

echo "当前备份数: $(ls -1 kids-tasks_*.tar.gz 2>/dev/null | wc -l)"
