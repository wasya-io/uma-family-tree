#!/usr/bin/env bash
#
# pedigree.sql を小さな塊に分割し、D1 に順番に投入するフォールバックスクリプト。
# `wrangler d1 execute --remote --file` が巨大 SQL で失敗する場合の代替
# (workers-sdk#4407 / #9503)。
#
# 使い方 (cwd = viewer):
#   ./db/split-and-import.sh remote   # 本番 D1 へ
#   ./db/split-and-import.sh local    # ローカル D1 へ (動作確認)
#
# 分割は「1 チャンク = N 個の SQL 文 (; 区切り)」単位。各チャンクは 100KB/文 の上限内に
# 収まる範囲でまとめる。
#
# 注意: Cloudflare D1 (remote) は SQL の BEGIN TRANSACTION / COMMIT / SAVEPOINT を
# 受け付けない (トランザクションは JS API 側で扱う設計)。よって各チャンクに
# トランザクション制御文は付けない。wrangler d1 execute --file が内部でまとめて送る。

set -euo pipefail

TARGET="${1:-}"
if [[ "$TARGET" != "remote" && "$TARGET" != "local" ]]; then
  echo "usage: $0 <remote|local>" >&2
  exit 1
fi

DB_NAME="uma-family-tree"
SRC="./db/pedigree.sql"
WORK="./db/.split"
# 1 チャンクあたりの SQL 文数。大きすぎると wrangler が不安定、小さすぎると回数が増える。
STMTS_PER_CHUNK="${STMTS_PER_CHUNK:-100}"

WRANGLER="./node_modules/.bin/wrangler"
FLAG="--remote"
[[ "$TARGET" == "local" ]] && FLAG="--local"

if [[ ! -f "$SRC" ]]; then
  echo "error: $SRC が見つかりません。先に pipeline で生成してください。" >&2
  exit 1
fi

echo "[1/3] $SRC を ${STMTS_PER_CHUNK} 文ごとに分割..."
rm -rf "$WORK"
mkdir -p "$WORK"

# awk で ; 区切りの文を数え、N 文ごとにファイルを分ける。トランザクション制御文
# (BEGIN/COMMIT/SAVEPOINT/ROLLBACK/PRAGMA) は remote D1 で弾かれるため、混じっていても除去する。
awk -v dir="$WORK" -v per="$STMTS_PER_CHUNK" '
  BEGIN { chunk=0; count=0; file=""; opened=0 }
  # トランザクション/PRAGMA 制御行はスキップ
  /^(BEGIN|COMMIT|SAVEPOINT|ROLLBACK|END TRANSACTION|PRAGMA)/ { next }
  {
    if (opened==0) {
      chunk++
      file=sprintf("%s/chunk_%05d.sql", dir, chunk)
      opened=1
    }
    print $0 >> file
    # 行末が ; なら 1 文の終わり
    if ($0 ~ /;[ \t]*$/) {
      count++
      if (count>=per) {
        close(file)
        opened=0
        count=0
      }
    }
  }
  END {
    if (opened==1) close(file)
  }
' "$SRC"

CHUNKS=$(ls "$WORK"/chunk_*.sql 2>/dev/null | wc -l | tr -d ' ')
echo "  ${CHUNKS} チャンクに分割しました。"

echo "[2/3] スキーマを投入..."
"$WRANGLER" d1 execute "$DB_NAME" $FLAG --file=./db/schema.sql

echo "[3/3] チャンクを順に投入 ($TARGET)..."
i=0
for f in "$WORK"/chunk_*.sql; do
  i=$((i+1))
  echo "  -> [$i/$CHUNKS] $(basename "$f")"
  "$WRANGLER" d1 execute "$DB_NAME" $FLAG --file="$f"
done

echo "完了。$CHUNKS チャンクを投入しました。"
echo "確認: $WRANGLER d1 execute $DB_NAME $FLAG --command=\"SELECT COUNT(*) FROM horses;\""
