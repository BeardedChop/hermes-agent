#!/usr/bin/env bash
# Real legacy -> current -> managed adoption funnel gate.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OLD_TAG="${1:-v2026.6.19}"

# Historical installers may invoke sudo on NixOS. Run the entire fixture in a
# disposable Linux environment instead of allowing root-owned host temp state.
if [ -z "${HERMES_ADOPTION_E2E_CONTAINER:-}" ] && grep -qi '^ID=nixos' /etc/os-release 2>/dev/null; then
    GIT_BUNDLE=$(mktemp --suffix=.bundle)
    CURRENT_REF=$(git -C "$REPO_ROOT" branch --show-current)
    git -C "$REPO_ROOT" bundle create "$GIT_BUNDLE" --all
    if docker run --rm \
        -e HERMES_ADOPTION_E2E_CONTAINER=1 \
        -e HERMES_ADOPTION_GIT_SOURCE=/tmp/hermes-current.bundle \
        -e HERMES_ADOPTION_CURRENT_REF="$CURRENT_REF" \
        -e CARGO_TARGET_DIR=/tmp/cargo-target \
        -v "$REPO_ROOT:$REPO_ROOT:ro" \
        -v "$GIT_BUNDLE:/tmp/hermes-current.bundle:ro" \
        -w "$REPO_ROOT" \
        rust:1.88-bookworm \
        bash -c 'for attempt in 1 2 3; do apt-get update -qq && apt-get -o Acquire::Retries=3 install -y -qq git curl python3 python3-venv python3-pip nodejs npm zstd util-linux pkg-config libssl-dev >/dev/null && break; [ "$attempt" -lt 3 ] || exit 1; rm -rf /var/lib/apt/lists/*; done && python3 -m pip install --break-system-packages -q pynacl==1.5.0 && bash scripts/e2e/test-adoption.sh "$1"' -- "$OLD_TAG"; then
        STATUS=0
    else
        STATUS=$?
    fi
    rm -f "$GIT_BUNDLE"
    exit "$STATUS"
fi

WORK=$(mktemp -d)
ORIGINAL_HOME="$HOME"
export CARGO_HOME="${CARGO_HOME:-$ORIGINAL_HOME/.cargo}"
export RUSTUP_HOME="${RUSTUP_HOME:-$ORIGINAL_HOME/.rustup}"
export HOME="$WORK/user"
export HERMES_HOME="$WORK/hermes-home"
LEGACY_SOURCE="$WORK/legacy-source"
LEGACY_CHECKOUT="$HERMES_HOME/hermes-agent"
RELEASES="$WORK/releases"
GIT_SOURCE="${HERMES_ADOPTION_GIT_SOURCE:-$REPO_ROOT}"
CURRENT_REF="${HERMES_ADOPTION_CURRENT_REF:-$(git -C "$REPO_ROOT" branch --show-current)}"
mkdir -p "$HOME/.local/bin" "$HERMES_HOME" "$RELEASES"
trap 'rm -rf "$WORK"' EXIT

printf '==> cloning historical cohort %s\n' "$OLD_TAG"
git clone --branch "$OLD_TAG" "$GIT_SOURCE" "$LEGACY_SOURCE" >/dev/null
[ -f "$LEGACY_SOURCE/scripts/install.sh" ]

printf '==> installing with the historical installer\n'
HELP=$(bash "$LEGACY_SOURCE/scripts/install.sh" --help)
ARGS=(--skip-setup --dir "$LEGACY_CHECKOUT")
grep -q -- '--branch' <<<"$HELP" && ARGS+=(--branch "$OLD_TAG")
grep -q -- '--hermes-home' <<<"$HELP" && ARGS+=(--hermes-home "$HERMES_HOME")
grep -q -- '--skip-browser' <<<"$HELP" && ARGS+=(--skip-browser)
INSTALL_LOG="$WORK/historical-install.log"
if ! HERMES_HOME="$HERMES_HOME" bash "$LEGACY_SOURCE/scripts/install.sh" "${ARGS[@]}" >"$INSTALL_LOG" 2>&1; then
    echo "historical installer failed:" >&2
    tail -80 "$INSTALL_LOG" >&2
    exit 1
fi
for candidate in "$LEGACY_CHECKOUT/.venv/bin/hermes" "$LEGACY_CHECKOUT/venv/bin/hermes"; do
    [ -x "$candidate" ] && HERMES_BIN="$candidate" && break
done
[ -n "${HERMES_BIN:-}" ] || { echo 'historical installer produced no Hermes executable' >&2; exit 1; }
"$HERMES_BIN" --version >/dev/null || { echo 'historical Hermes executable does not boot' >&2; exit 1; }
# Old installers used a wrapper file here; adoption's undo contract records a
# link target, so normalize the equivalent command entry to a symlink first.
rm -f "$HOME/.local/bin/hermes"
ln -s "$HERMES_BIN" "$HOME/.local/bin/hermes"
OLD_TARGET=$(readlink "$HOME/.local/bin/hermes")

printf '==> hop 1: historical updater reaches current source\n'
git -C "$LEGACY_CHECKOUT" remote set-url origin "$GIT_SOURCE"
git -C "$LEGACY_CHECKOUT" fetch origin \
    "$CURRENT_REF:refs/remotes/origin/main"
if ! HERMES_HOME="$HERMES_HOME" "$HERMES_BIN" update --yes; then
    HERMES_HOME="$HERMES_HOME" "$HERMES_BIN" update --yes
fi

# The update may replace the venv entry point; resolve it again.
for candidate in "$LEGACY_CHECKOUT/.venv/bin/hermes" "$LEGACY_CHECKOUT/venv/bin/hermes"; do
    [ -x "$candidate" ] && HERMES_BIN="$candidate" && break
done

printf '==> hop 2: prompt appears exactly once\n'
mkdir -p "$HERMES_HOME"
printf 'updates:\n  adopt: prompt\n' > "$HERMES_HOME/config.yaml"
rm -f "$HERMES_HOME/state/adoption-snooze"
FIRST=$(script -qec "HERMES_HOME='$HERMES_HOME' '$HERMES_BIN' --version" /dev/null)
SECOND=$(script -qec "HERMES_HOME='$HERMES_HOME' '$HERMES_BIN' --version" /dev/null)
COUNT=$(printf '%s\n%s\n' "$FIRST" "$SECOND" | grep -c 'Hermes can switch this install to managed releases' || true)
[ "$COUNT" -eq 1 ] || { echo "expected one adoption offer, got $COUNT" >&2; exit 1; }

printf '==> building trusted updater and signed bundle fixture\n'
KEYS=$(python3 - <<'PY'
import base64
from nacl.signing import SigningKey
key = SigningKey.generate()
print(base64.b64encode(bytes(key)).decode())
print(base64.b64encode(bytes(key.verify_key)).decode())
PY
)
SIGNING_KEY=$(printf '%s\n' "$KEYS" | sed -n '1p')
PUBLIC_KEY=$(printf '%s\n' "$KEYS" | sed -n '2p')
TARGET_DIR="${CARGO_TARGET_DIR:-$REPO_ROOT/apps/hermes-launcher/target}"
(
    cd "$REPO_ROOT/apps/hermes-launcher"
    HERMES_RELEASE_PUBLIC_KEY="$PUBLIC_KEY" cargo build --locked --quiet
)
LAUNCHER="$TARGET_DIR/debug/hermes"
[ -x "$LAUNCHER" ]
PLATFORM=$(case "$(uname -s)-$(uname -m)" in Linux-x86_64) echo linux-x64;; Linux-aarch64) echo linux-arm64;; Darwin-arm64) echo darwin-arm64;; *) exit 1;; esac)
VERSION=1.0.0
TREE="$WORK/bundle"
mkdir -p "$TREE/bin" "$TREE/runtime/venv/bin" "$TREE/runtime/node/bin" "$TREE/runtime/tools" "$TREE/runtime/python/bin" "$TREE/app/skills/demo" "$TREE/ui/tui/dist" "$TREE/ui/web/dist" "$RELEASES/$VERSION"
cp "$LAUNCHER" "$TREE/bin/hermes"
chmod +x "$TREE/bin/hermes"
printf 'demo\n' > "$TREE/app/skills/demo/SKILL.md"
printf 'tui\n' > "$TREE/ui/tui/dist/entry.js"
printf 'web\n' > "$TREE/ui/web/dist/index.html"
printf '%s\n' "$VERSION" > "$TREE/VERSION"
cat > "$TREE/runtime/venv/bin/python" <<'PY'
#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/../../.." && pwd)
[ "${1:-}" = "-c" ] && exit 0
if [ "${1:-}" = "-m" ] && [ "${2:-}" = "hermes_cli.main" ]; then shift 2; fi
[ "${1:-}" = "doctor" ] && [ "${2:-}" = "--preflight" ] && exit 0
[ "${1:-}" = "version-probe" ] && cat "$ROOT/VERSION" && exit 0
exit 0
PY
chmod +x "$TREE/runtime/venv/bin/python"
python3 "$REPO_ROOT/scripts/release/write-manifest.py" --bundle-dir "$TREE" --version "$VERSION" --channel stable --git-sha "$(printf 'a%.0s' {1..40})" --platform "$PLATFORM" --signing-key "$SIGNING_KEY" >/dev/null
mkdir -p "$WORK/archive/bundle"
cp -a "$TREE/." "$WORK/archive/bundle/"
tar --zstd -cf "$RELEASES/$VERSION/hermes-$VERSION-$PLATFORM.tar.zst" -C "$WORK/archive" bundle
printf '%s\n' "$VERSION" > "$RELEASES/latest-stable.txt"
UPDATER_ASSET="$RELEASES/hermes-updater-$PLATFORM"
cp "$LAUNCHER" "$UPDATER_ASSET"
python3 - "$UPDATER_ASSET" <<'PY'
import hashlib, pathlib, sys
p=pathlib.Path(sys.argv[1]); p.with_name(p.name+'.sha256').write_text(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n')
PY

printf '==> hop 3: invoke adoption through the updated Python CLI\n'
BEFORE_HEAD=$(git -C "$LEGACY_CHECKOUT" rev-parse HEAD)
BEFORE_STATUS=$(git -C "$LEGACY_CHECKOUT" status --porcelain=v1 --untracked-files=all)
HERMES_HOME="$HERMES_HOME" "$HERMES_BIN" adopt --yes --yes-dirty --source "file://$RELEASES"
[ "$(cat "$HERMES_HOME/current.txt")" = "$VERSION" ]
[ "$(readlink "$HOME/.local/bin/hermes")" = "$HERMES_HOME/bin/hermes" ]
[ "$(cd "$HOME" && "$HERMES_HOME/bin/hermes" launch version-probe)" = "$VERSION" ]
[ "$(git -C "$LEGACY_CHECKOUT" rev-parse HEAD)" = "$BEFORE_HEAD" ]
[ "$(git -C "$LEGACY_CHECKOUT" status --porcelain=v1 --untracked-files=all)" = "$BEFORE_STATUS" ]

printf '==> undo restores the historical launcher\n'
HERMES_HOME="$HERMES_HOME" "$HERMES_HOME/bin/hermes-updater" adopt --undo
[ "$(readlink "$HOME/.local/bin/hermes")" = "$OLD_TARGET" ]
"$HERMES_BIN" --version >/dev/null
printf 'E2E_PASS: real historical adoption funnel\n'
