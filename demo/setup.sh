#!/bin/sh
# Creates each demo project under $HANDOFF_PROJECTS (default ./projects) as a new git repository.
# Projects that already exist there are left alone.
set -e
cd "$(dirname "$0")/.."
[ -f .env ] && { set -a; . ./.env; set +a; }
dest="${HANDOFF_PROJECTS:-./projects}"
mkdir -p "$dest"
for src in demo/projects/*/; do
  name=$(basename "$src")
  [ -e "$dest/$name" ] && continue
  cp -r "$src" "$dest/$name"
  git -C "$dest/$name" init -q -b main
  git -C "$dest/$name" add -A
  git -C "$dest/$name" -c user.name=handoff -c user.email=handoff@localhost commit -qm "chore: demo project"
  echo "created $dest/$name"
done
