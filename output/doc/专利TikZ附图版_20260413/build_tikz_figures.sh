#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

for f in 图*.tex; do
  xelatex -interaction=nonstopmode -halt-on-error "$f" >/tmp/"$f".log
done
