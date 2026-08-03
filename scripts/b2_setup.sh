#!/usr/bin/env bash
# b2_setup.sh — provision (or PLAN) the two Backblaze B2 buckets CastIron needs.
#
#   ci-media      run artifacts · Event Notifications -> webhook · Lifecycle 7d · SSE-B2
#   ci-published  finished episodes · Object Lock (governance) 30d · SSE-B2
#
# Usage:
#   scripts/b2_setup.sh --plan     # PRINT the exact real-mode commands, run nothing
#   scripts/b2_setup.sh            # execute (requires b2 CLI + B2 master key in env)
#
# --plan is the credential-free path: it emits every command a human (or a later
# session with keys) runs verbatim. No credentials are used and nothing mutates.
#
# NOTE: b2 CLI subcommand spelling shifts across major versions (v3 `b2 bucket
# create` vs older `b2 create-bucket`). Verify against `b2 version` before running.
set -euo pipefail

MODE="exec"
[[ "${1:-}" == "--plan" ]] && MODE="plan"

MEDIA_BUCKET="${B2_MEDIA_BUCKET:-ci-media}"
PUBLISHED_BUCKET="${B2_PUBLISHED_BUCKET:-ci-published}"
WEBHOOK_URL="${WEBHOOK_URL:-https://api.castiron.edycu.dev/webhooks/b2}"
WEBHOOK_HMAC_SECRET="${WEBHOOK_HMAC_SECRET:-<WEBHOOK_HMAC_SECRET>}"
LIFECYCLE_DAYS=7
RETENTION_DAYS=30

emit() {
  if [[ "$MODE" == "plan" ]]; then
    printf '  %s\n' "$*"
  else
    echo "+ $*"
    eval "$*"
  fi
}

section() { printf '\n# %s\n' "$*"; }

if [[ "$MODE" == "plan" ]]; then
  cat <<'BANNER'
================================================================
CastIron B2 provisioning PLAN (dry run — nothing executed)
Run `b2 account authorize <MASTER_KEY_ID> <MASTER_APP_KEY>` first,
then execute the commands below. Re-running is safe/idempotent
(create-* is a no-op if the bucket already exists).
================================================================
BANNER
fi

section "1) Buckets (private, SSE-B2 at rest)"
emit "b2 bucket create --default-server-side-encryption SSE-B2 ${MEDIA_BUCKET} allPrivate"
emit "b2 bucket create --file-lock-enabled --default-server-side-encryption SSE-B2 ${PUBLISHED_BUCKET} allPrivate"

section "2) Lifecycle — expire run intermediates after ${LIFECYCLE_DAYS}d (runs/ prefix on ${MEDIA_BUCKET})"
emit "b2 bucket update ${MEDIA_BUCKET} --lifecycle-rule '{\"fileNamePrefix\":\"runs/\",\"daysFromUploadingToHiding\":${LIFECYCLE_DAYS},\"daysFromHidingToDeleting\":1}'"

section "3) Object Lock — governance ${RETENTION_DAYS}d default on ${PUBLISHED_BUCKET}"
emit "b2 bucket update ${PUBLISHED_BUCKET} --default-retention-mode governance --default-retention-period '${RETENTION_DAYS} days'"

section "4) Event Notification — ${MEDIA_BUCKET} ObjectCreated -> webhook (HMAC signed)"
emit "b2 bucket notification-rule create ${MEDIA_BUCKET} ci-media-created \\
      --event-type 'b2:ObjectCreated:*' \\
      --webhook-url '${WEBHOOK_URL}' \\
      --sign-secret '${WEBHOOK_HMAC_SECRET}' \\
      --object-name-prefix 'runs/'"

section "5) Scoped application keys (least privilege — never in the frontend)"
emit "b2 key create --bucket ${MEDIA_BUCKET} ci-media-rw \\
      listBuckets,listFiles,readFiles,writeFiles,readBucketEncryption,readBucketNotifications"
emit "b2 key create --bucket ${PUBLISHED_BUCKET} ci-published-writer \\
      listBuckets,listFiles,readFiles,writeFiles,bypassGovernance"

if [[ "$MODE" == "plan" ]]; then
  cat <<'FOOT'

# After creating keys, put the ci-media-rw key into B2_KEY_ID / B2_APP_KEY (.env).
# The ci-published-writer key is used only by the publish path (server-side).
# Then drop OFFLINE=1 to run against real B2. Until then, OFFLINE mode is green.
FOOT
fi
