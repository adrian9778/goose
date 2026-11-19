#!/usr/bin/env bash
# sync.sh — 把 fork 的 main 严格对齐上游 upstream/main，再把工作分支的净变更
# squash 成一个提交套到最新 main 上，最后安全强推（--force-with-lease）。
#
# 用法：
#   ./sync.sh              # 真跑（会 fetch / reset / squash / push）
#   ./sync.sh --dry-run    # 只打印将做什么，不改任何状态
#
# 换项目只改下面「可配置项」5 个变量。

set -euo pipefail

# ── 可配置项（按项目改这里）──────────────────────────────────────
UPSTREAM_REMOTE="${UPSTREAM_REMOTE:-upstream}"   # 上游 remote 名
UPSTREAM_URL="${UPSTREAM_URL:-git@github.com:aaif-goose/goose.git}"  # 上游 URL
MAIN_REMOTE="${MAIN_REMOTE:-origin}"             # 推送目标 remote（fork）
MAIN_BRANCH="${MAIN_BRANCH:-main}"               # 主分支名
DOCS_BRANCH="${DOCS_BRANCH:-adrian}"             # 工作分支名（squash + force push）
# ──────────────────────────────────────────────────────────────

DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

log()  { printf '\033[1;34m[sync]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[sync]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[sync]\033[0m %s\n' "$*" >&2; exit 1; }

run() {
  if (( DRY_RUN )); then
    log "(dry-run) $*"
  else
    log "$*"
    "$@"
  fi
}

# ── 定位根目录（要求 1）────────────────────────────────────────
cd_to_git_root() {
  local toplevel
  toplevel="$(git rev-parse --show-toplevel 2>/dev/null)" \
    || die "不在 git 仓库里"
  cd "$toplevel"
}

# ── detached HEAD 守卫 ─────────────────────────────────────────
# detached HEAD 下 branch --show-current 为空，后续 checkout/回退逻辑会失效，fail-fast。

# ── 上游 remote 配置 ────────────────────────────────────────────
ensure_upstream_remote() {
  if git remote | grep -qx "$UPSTREAM_REMOTE"; then
    log "$UPSTREAM_REMOTE remote 已存在（$UPSTREAM_REMOTE）"
    return
  fi
  # 上游 remote 未配置：dry-run 只打印不真加（坑 6）；真跑必须拿到 URL
  if (( DRY_RUN )); then
    log "(dry-run) $UPSTREAM_REMOTE remote 未配置，将执行：git remote add $UPSTREAM_REMOTE $UPSTREAM_URL"
    return
  fi
  [[ -n "$UPSTREAM_URL" ]] || die "未配置 $UPSTREAM_REMOTE remote，且未提供 UPSTREAM_URL；请在脚本顶部或环境变量设置 UPSTREAM_URL"
  run git remote add "$UPSTREAM_REMOTE" "$UPSTREAM_URL"
}

# ── stash（要求 2，含未跟踪）───────────────────────────────────
STASHED=0
stash_workdir() {
  if [[ -z "$(git status --porcelain)" ]]; then
    STASHED=0
    return
  fi
  run git stash push --include-untracked -m "sync.sh auto-stash $(date '+%F %T')"
  STASHED=1
}

# ── 失败恢复 + 备份清理（要求 3 + 7）───────────────────────────
BACKUP_BRANCH=""

cleanup_backup() {
  if [[ -n "$BACKUP_BRANCH" ]] && git show-ref --verify -q "refs/heads/$BACKUP_BRANCH"; then
    run git branch -D "$BACKUP_BRANCH"
    BACKUP_BRANCH=""
  fi
}

restore_on_failure() {
  local rc=$?
  trap - EXIT
  git checkout -f "$START_BRANCH" >/dev/null 2>&1 || true
  # 必须先清 squash 冲突中间态，否则 stash pop 弹不回（坑 9）
  git merge --abort >/dev/null 2>&1 || true
  if [[ -n "$BACKUP_BRANCH" ]] && git show-ref --verify -q "refs/heads/$BACKUP_BRANCH"; then
    if [[ "$(git branch --show-current)" == "$DOCS_BRANCH" ]]; then
      git reset --hard "$BACKUP_BRANCH" >/dev/null 2>&1 || true
    else
      git reset --hard >/dev/null 2>&1 || true
      git branch -f "$DOCS_BRANCH" "$BACKUP_BRANCH" >/dev/null 2>&1 || true
    fi
  else
    git reset --hard >/dev/null 2>&1 || true
  fi
  if (( STASHED )) && [[ -n "$(git stash list | head -1 || true)" ]]; then
    warn "中途失败（rc=$rc），恢复现场与 stash 改动"
    git stash pop || warn "stash pop 仍有冲突，改动仍保留在 stash，请手动处理"
  fi
  if [[ -n "$BACKUP_BRANCH" ]]; then
    warn "$DOCS_BRANCH 已恢复到同步前状态，$BACKUP_BRANCH 保留作回滚锚点，确认后 git branch -D $BACKUP_BRANCH"
  fi
  exit "$rc"
}

# ── main 严格对齐上游（要求 4）─────────────────────────────────
sync_main() {
  run git fetch "$UPSTREAM_REMOTE" --prune
  run git fetch "$MAIN_REMOTE" --prune
  if (( DRY_RUN )); then
    log "(dry-run) 跳过 main 与上游比对/硬重置（需真实 fetch 后的新 ref）"
    run git push --force-with-lease "$MAIN_REMOTE" "$MAIN_BRANCH"
    return
  fi
  local local_main upstream_main ahead
  local_main="$(git rev-parse "$MAIN_BRANCH")"
  upstream_main="$(git rev-parse "$UPSTREAM_REMOTE/$MAIN_BRANCH")"
  if [[ "$local_main" == "$upstream_main" ]]; then
    log "main 已与上游一致"
  else
    ahead="$(git rev-list --count "${UPSTREAM_REMOTE}/${MAIN_BRANCH}..${MAIN_BRANCH}")"
    if [[ "$ahead" -gt 0 ]]; then
      warn "本地 $MAIN_BRANCH 有 $ahead 个 fork 独有提交，将被 reset --hard 丢弃（reflog 可找回）"
    fi
    run git checkout "$MAIN_BRANCH"
    run git reset --hard "$UPSTREAM_REMOTE/$MAIN_BRANCH"
  fi
  run git push --force-with-lease "$MAIN_REMOTE" "$MAIN_BRANCH"
}

# ── 工作分支 squash 后套 main（要求 5 + 6 + 7）──────────────────
sync_work() {
  if ! git show-ref --verify -q "refs/heads/$DOCS_BRANCH"; then
    # 本地没有工作分支：fork 有则先跟远端，两边都没有则基于 main 新建
    if git ls-remote --exit-code --heads "$MAIN_REMOTE" "$DOCS_BRANCH" >/dev/null 2>&1; then
      run git checkout -b "$DOCS_BRANCH" "$MAIN_REMOTE/$DOCS_BRANCH"
    else
      run git checkout -b "$DOCS_BRANCH"
      run git push -u "$MAIN_REMOTE" "$DOCS_BRANCH"
    fi
    return
  fi

  run git checkout "$DOCS_BRANCH"
  if [[ "$(git rev-parse "$DOCS_BRANCH")" == "$(git rev-parse "$MAIN_BRANCH")" ]]; then
    log "工作分支已与 main 一致"
    return
  fi

  local backup="${DOCS_BRANCH}-backup"
  run git branch -f "$backup" "$DOCS_BRANCH"
  BACKUP_BRANCH="$backup"

  local base
  base="$(git merge-base "$DOCS_BRANCH" "$MAIN_BRANCH")"
  if [[ -z "$(git diff --name-only "$base" "$DOCS_BRANCH")" ]]; then
    run git reset --hard "$MAIN_BRANCH"
    cleanup_backup
    return
  fi

  run git reset --hard "$MAIN_BRANCH"
  run git merge --squash "$backup"
  run git commit -m "sync: $DOCS_BRANCH 工作内容（基于 $MAIN_BRANCH）"
  run git push --force-with-lease "$MAIN_REMOTE" "$DOCS_BRANCH"
  cleanup_backup
}

main() {
  cd_to_git_root

  [[ -n "$(git branch --show-current)" ]] || die "detached HEAD，先切到分支"

  ensure_upstream_remote

  START_BRANCH="$(git branch --show-current)"
  trap restore_on_failure EXIT

  stash_workdir
  sync_main
  sync_work

  trap - EXIT
  log "完成：main 已对齐 $UPSTREAM_REMOTE/$MAIN_BRANCH，$DOCS_BRANCH 已 squash 强推"
}

START_BRANCH=""
main
