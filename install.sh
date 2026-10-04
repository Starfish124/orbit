#!/bin/sh
# orbit installer. Run from the repo: ./install.sh
#
# Makes a venv for the viewer (the indexer itself needs no packages), an
# `orbit` command in ~/.local/bin, and a launchd job that refreshes the index
# every 15 minutes. It never touches your Claude Code settings: the hook for
# the sessions tab is printed for you to paste.
set -eu

ROOT=$(cd "$(dirname "$0")" && pwd)
DATA="$HOME/.local/share/orbit"
BIN="$HOME/.local/bin/orbit"
LABEL="dev.orbit.refresh"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/.local/state/orbit/refresh.log"

echo "1/4  venv + textual  ($DATA/.venv)"
mkdir -p "$DATA" "$(dirname "$LOG")" "$HOME/.local/bin" "$(dirname "$PLIST")"
python3 -m venv "$DATA/.venv"
"$DATA/.venv/bin/pip" install --quiet --upgrade pip "textual[syntax]"

echo "2/4  the orbit command  ($BIN)"
if [ -e "$BIN" ] && ! grep -qF "$ROOT" "$BIN"; then
  echo "     $BIN already exists and is not this checkout's: left alone"
else
  cat > "$BIN" <<WRAP
#!/bin/sh
# orbit wrapper for $ROOT
export PYTHONPATH="$ROOT"
exec "$DATA/.venv/bin/python" -m orbit "\$@"
WRAP
  chmod +x "$BIN"
fi

echo "3/4  launchd refresh every 15 min  ($PLIST)"
cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$DATA/.venv/bin/python</string>
    <string>-m</string><string>orbit</string><string>refresh</string>
  </array>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONPATH</key><string>$ROOT</string>
    <!-- launchd gives no login shell: gh lives in /opt/homebrew/bin -->
    <key>PATH</key><string>$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>StartInterval</key><integer>900</integer>
  <key>Nice</key><integer>5</integer>
  <key>LowPriorityIO</key><true/>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
PLIST
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load -w "$PLIST"

echo "4/4  optional: the sessions tab needs one Claude Code hook."
echo "     Merge this into the \"hooks\" object of ~/.claude/settings.json:"
echo
/usr/bin/python3 - "$ROOT/hooks/pulse.py" <<'PY'
import json, shlex, sys
cmd = "/usr/bin/python3 " + shlex.quote(sys.argv[1])
events = ["SessionStart", "UserPromptSubmit", "PostToolUse", "PostToolUseFailure",
          "Notification", "Stop", "StopFailure", "SubagentStop", "PreCompact", "SessionEnd"]
hook = [{"hooks": [{"type": "command", "command": cmd, "timeout": 5, "async": True}]}]
print(json.dumps({e: hook for e in events}, indent=2))
PY
echo
echo "Done. The first index builds in the background now; 'orbit status' shows"
echo "when it lands, 'orbit' opens the viewer. Settings: $ROOT/config.example.json"
echo "-> ~/.config/orbit/config.json. Is ~/.local/bin on your PATH?"
