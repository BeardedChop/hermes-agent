#!/usr/bin/env bash
# Prove a recorded lazy feature is restored into a replacement venv.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
if [ -n "${UV:-}" ]; then
    UV="$UV"
elif command -v uv >/dev/null 2>&1; then
    UV="$(command -v uv)"
else
    UV="$HOME/.hermes/bin/uv"
fi

WORK=$(mktemp -d)
FEATURE_HOME="$WORK/home"
WHEELS="$WORK/wheels"
V1="$WORK/v1"
V2="$WORK/v2"
mkdir -p "$FEATURE_HOME/state" "$WHEELS"
trap 'rm -rf "$WORK"' EXIT

python3 - "$WHEELS" <<'PY'
import base64
import csv
import hashlib
import io
import pathlib
import zipfile

root = pathlib.Path(__import__('sys').argv[1])
wheel = root / 'edge_tts-7.2.7-py3-none-any.whl'
files = {
    'edge_tts/__init__.py': b'E2E_MARKER = "ledger-restored"\n',
    'edge_tts-7.2.7.dist-info/METADATA': b'Metadata-Version: 2.1\nName: edge-tts\nVersion: 7.2.7\n',
    'edge_tts-7.2.7.dist-info/WHEEL': b'Wheel-Version: 1.0\nGenerator: hermes-e2e\nRoot-Is-Purelib: true\nTag: py3-none-any\n',
}
rows = []
for path, body in files.items():
    digest = base64.urlsafe_b64encode(hashlib.sha256(body).digest()).rstrip(b'=').decode()
    rows.append((path, f'sha256={digest}', str(len(body))))
record = 'edge_tts-7.2.7.dist-info/RECORD'
rows.append((record, '', ''))
out = io.StringIO(); csv.writer(out, lineterminator='\n').writerows(rows)
files[record] = out.getvalue().encode()
with zipfile.ZipFile(wheel, 'w', zipfile.ZIP_DEFLATED) as archive:
    for path, body in files.items(): archive.writestr(path, body)
PY

"$UV" venv "$V1" >/dev/null
"$UV" venv "$V2" >/dev/null
"$UV" pip install --python "$V1/bin/python" --no-deps -e "$REPO_ROOT" >/dev/null
"$UV" pip install --python "$V2/bin/python" --no-deps -e "$REPO_ROOT" >/dev/null

export HERMES_HOME="$FEATURE_HOME"
export PIP_FIND_LINKS="$WHEELS"
export PIP_NO_INDEX=1
export UV_FIND_LINKS="$WHEELS"
export UV_NO_INDEX=1
SYSTEM_PYTHON=$(command -v python3)
"$V1/bin/python" - <<'PY'
from tools.lazy_deps import ensure
ensure('tts.edge', prompt=False)
import edge_tts
assert edge_tts.E2E_MARKER == 'ledger-restored'
PY
"$V1/bin/python" -c 'import edge_tts'
if "$V2/bin/python" -c 'import edge_tts' 2>/dev/null; then
    echo 'replacement venv unexpectedly already contains the feature' >&2
    exit 1
fi
# Hide uv for replay so ensure() exercises the target venv's pip/ensurepip
# ladder. This avoids CI project-environment discovery influencing the test.
PATH=/usr/bin:/bin PYTHONPATH="$REPO_ROOT" "$SYSTEM_PYTHON" - "$V2/bin/python" <<'PY'
import json
import sys
from tools.lazy_deps import apply_ledger
result = apply_ledger(sys.argv[1])
assert result.get('tts.edge') == 'refreshed', json.dumps(result, sort_keys=True)
PY
"$V2/bin/python" - <<'PY'
import edge_tts
assert edge_tts.E2E_MARKER == 'ledger-restored'
PY
printf 'E2E_PASS: lazy feature restored into replacement venv\n'
