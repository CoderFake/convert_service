#!/bin/bash

TOTAL_RAM=$(cat /sys/fs/cgroup/memory/memory.limit_in_bytes 2>/dev/null || echo "0")
TOTAL_CPU=$(cat /sys/fs/cgroup/cpu/cpu.cfs_quota_us 2>/dev/null || echo "0")
CPU_PERIOD=$(cat /sys/fs/cgroup/cpu/cpu.cfs_period_us 2>/dev/null || echo "100000")

if [ "$TOTAL_RAM" -eq "0" ]; then
    TOTAL_RAM=$(free -b | awk '/Mem:/ {print $2}' || echo "0")
fi

if [ "$TOTAL_CPU" -eq "0" ]; then
    TOTAL_CPU_CORES=$(grep -c ^processor /proc/cpuinfo || echo "1")
else
    TOTAL_CPU_CORES=$(($TOTAL_CPU / $CPU_PERIOD))
fi

if [ "$TOTAL_RAM" -gt "0" ]; then
    TOTAL_RAM_MB=$(($TOTAL_RAM / 1024 / 1024))
    CONCURRENCY=$(($TOTAL_RAM_MB / 100))
else
    CONCURRENCY=1
fi

if [ "$CONCURRENCY" -gt "$TOTAL_CPU_CORES" ]; then
    CONCURRENCY=$TOTAL_CPU_CORES
fi

if [ "$CONCURRENCY" -lt 1 ]; then
    CONCURRENCY=1
fi

echo "Detected RAM: ${TOTAL_RAM_MB:-unknown} MB"
echo "Detected CPUs: ${TOTAL_CPU_CORES:-unknown}"
echo "Calculated Celery Concurrency: ${CONCURRENCY}"

exec celery -A ConvertService worker --concurrency=$CONCURRENCY --loglevel=info
