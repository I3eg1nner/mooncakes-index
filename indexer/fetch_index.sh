#!/usr/bin/env bash
# 下载语义索引快照到 index/（从 GitHub Releases 资产，匿名可访问）。
# 用法：bash indexer/fetch_index.sh [tag]   # 默认 latest
set -euo pipefail
cd "$(dirname "$0")/.."
TAG="${1:-latest}"
mkdir -p index
echo "downloading index snapshot: ${TAG}"
gh release download "${TAG}" --repo I3eg1nner/mooncakes-index --pattern "vectors.npy" --pattern "chunks.db" --pattern "packages.jsonl" --dir index --clobber
echo "restored:"
ls -lh index/vectors.npy index/chunks.db index/packages.jsonl
echo "verify: python3 -m indexer.search \"jmes\" -n 3   # 需要 ZHIPUAI_API_KEY 嵌入查询"
