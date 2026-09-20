#!/usr/bin/env bash
# Поставить задачу ИИ-агенту на VPS через HTTP-канал gateway.
#
#   scripts/vps/agent_task.sh "текст задачи"
#   echo "текст" | scripts/vps/agent_task.sh
#
# Токен gateway остаётся на сервере и не проходит через локальную машину.
set -euo pipefail

KEY="${AGENT_VPS_KEY:-$HOME/.ssh/id_ed25519_agentvps}"
HOST="${AGENT_VPS_HOST:-root@5.35.91.122}"
MODEL="${AGENT_MODEL:-openclaw/default}"
TIMEOUT="${AGENT_TIMEOUT:-600}"

TASK="${1:-}"
[ -z "$TASK" ] && TASK="$(cat)"
[ -z "$TASK" ] && { echo "Нужен текст задачи" >&2; exit 1; }

printf '%s' "$TASK" | ssh -i "$KEY" -o StrictHostKeyChecking=no "$HOST" \
  "cat > /tmp/agent_task.txt && node -e '
const fs=require(\"fs\");
const cfg=JSON.parse(fs.readFileSync(\"/root/.openclaw/openclaw.json\",\"utf8\"));
const token=cfg.gateway.auth.token;
const task=fs.readFileSync(\"/tmp/agent_task.txt\",\"utf8\");
const body=JSON.stringify({model:\"$MODEL\",messages:[{role:\"user\",content:task}]});
const req=require(\"http\").request({host:\"127.0.0.1\",port:18789,path:\"/v1/chat/completions\",method:\"POST\",
  headers:{\"Authorization\":\"Bearer \"+token,\"Content-Type\":\"application/json\",\"Content-Length\":Buffer.byteLength(body)},
  timeout:$TIMEOUT*1000},res=>{
  let d=\"\"; res.on(\"data\",c=>d+=c); res.on(\"end\",()=>{
    try{const j=JSON.parse(d); process.stdout.write((j.choices&&j.choices[0]&&j.choices[0].message&&j.choices[0].message.content)||d);}
    catch(e){process.stdout.write(d);}
  });
});
req.on(\"error\",e=>{console.error(\"Ошибка:\",e.message);process.exit(1);});
req.on(\"timeout\",()=>{console.error(\"Таймаут\");req.destroy();process.exit(1);});
req.end(body);
' ; rm -f /tmp/agent_task.txt"
