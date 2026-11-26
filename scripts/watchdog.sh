#!/bin/sh
# 引擎看门狗 —— 热重启前先放出去，负责在「没有人监听 3080」时把引擎拉起来。
# 设计参考安卓恢复模式：执行体要**最小、独立、不依赖上层**。
# 只用 sh + 基础命令；不 import 任何项目代码；由调用方 setsid + < /dev/null 放出。
LOG=/tmp/engine-watchdog.log
PORT=3080
say() { echo "$(date '+%F %T') $*" >> "$LOG"; }

# 判据用真 HTTP 连接：proot 里 awk 打不开 /proc/net/tcp（Permission denied，2026-11-27 实测过），
# 而 curl 连得上就是活的——这才是「用户能不能进来」那个判据。
listening() {
  code=$(curl -s -o /dev/null -m 3 -w '%{http_code}' "http://127.0.0.1:$PORT/" 2>/dev/null)
  [ -n "$code" ] && [ "$code" != "000" ]
}

launch() {
  say "拉起引擎（最小依赖路径）"
  cd /root/.dsh/profiles/web 2>/dev/null || cd /root
  /opt/node/bin/node --import=/opt/dsh-go/boot-cache.mjs \
    /opt/dsh/node_modules/@deepseek-ai/dsh/lib/bin.js web \
    --patch /etc/dsh-app/dsh-web.patch.yml \
    --patch /opt/dsh-app/speech.patch.yml \
    --patch /opt/dsh-app/auth/auth.patch.yml \
    --patch /opt/dsh-app/search.patch.yml \
    --patch /opt/dsh-app/phone/phone.patch.yml \
    --host 127.0.0.1 --port 3080 --no-open \
    >> /root/.dsh/engine-standby/launch.log 2>&1 &
  say "已发出拉起命令 child=$!"
}

say "看门狗启动 pid=$$ ppid=$PPID"
if listening; then say "启动时端口在听（不代表成功，继续盯）"; fi
i=0
while [ $i -lt 9 ]; do
  sleep 5; i=$((i+1))
  if listening; then say "第 ${i} 次检查：端口在听"; fi
done
if listening; then
  say "端口正常，看门狗退出（未干预）"
  exit 0
fi
say "45 秒无人监听 → 介入拉起"
launch
sleep 25
if listening; then
  say "看门狗拉起成功"
else
  say "看门狗拉起后仍无人监听 → 需要人工（恢复模式）"
fi
