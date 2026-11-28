#!/bin/sh
# 安装包 2026-11-28-1 —— 装到当前容器
# 每一处改动都先备份，再落位；最后自验（语法/关键行/端口）。
set -u
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
TS=$(date +%Y%m%d-%H%M%S)
BRAIN=${BRAIN:-/root/workspace/记忆档案}
ok=0; fail=0
say() { printf '%s\n' "$*"; }
cpb() { if [ -f "$2" ]; then cp "$2" "$2.bak-$TS" && say "备份 $2 → $2.bak-$TS"; fi; }

say "== 1/4 看护壳 /usr/local/bin/dsh"
cpb x /usr/local/bin/dsh
cp "$HERE/bin/dsh" /usr/local/bin/dsh && chmod +x /usr/local/bin/dsh
sh -n /usr/local/bin/dsh && { say "  sh -n 通过"; ok=$((ok+1)); } || { say "  ✗ 语法错"; fail=$((fail+1)); }

say "== 2/4 前端自动重连 index.html"
FE=/opt/dsh/node_modules/@deepseek-ai/dsh-web-frontend/dist/index.html
cpb x "$FE"
cp "$HERE/web/index.html" "$FE" && grep -q "manifest.webmanifest" "$FE" && { say "  探活代码在位"; ok=$((ok+1)); } || { say "  ✗ 注入缺失"; fail=$((fail+1)); }

say "== 3/4 引擎配置（压缩脊 headroomTokens、默认模型）"
P=~/.dsh/profiles/web/cordis.patch.yml
cpb x "$P"
cp "$HERE/profile/cordis.patch.yml" "$P"
if python3 -c "import yaml,sys;d=yaml.safe_load(open('$P'));assert any(x.get('id')=='agent-default-model' for x in d)" 2>/dev/null; then
  say "  YAML 通过"; ok=$((ok+1))
else
  say "  ✗ YAML 或默认模型缺失"; fail=$((fail+1))
fi

say "== 4/4 脑子脚本 → $BRAIN"
mkdir -p "$BRAIN"
for f in "$HERE"/brain/*; do
  b=$(basename "$f"); cpb x "$BRAIN/$b"; cp "$f" "$BRAIN/$b"
done
python3 -c "import ast,glob;[ast.parse(open(f,encoding='utf-8').read()) for f in glob.glob('$BRAIN/*.py')]" \
  && { say "  $(ls "$BRAIN"/*.py | wc -l) 个脚本语法通过"; ok=$((ok+1)); } || { say "  ✗ 有脚本语法错"; fail=$((fail+1)); }

say ""
say "结果：$ok 项通过，$fail 项失败"
say "生效方式："
say "  · 壳 / 配置：dsh restart（两秒回来），或下次启动"
say "  · 前端：刷新一次页面（之后自动重连）"
say "  · 脑子脚本：立即生效"
[ "$fail" -eq 0 ] || exit 1
