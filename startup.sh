#!/usr/bin/env bash

set -Eeuo pipefail

log() {
	printf '[startup] %s %s\n' "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "$*"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

resolve_python_bin() {
	if [[ -n "${PYTHON_BIN:-}" ]]; then
		printf '%s\n' "$PYTHON_BIN"
		return 0
	fi

	local candidates=(
		"$SCRIPT_DIR/venv/Scripts/python.exe"
		"$SCRIPT_DIR/../.venv/Scripts/python.exe"
		"$SCRIPT_DIR/.venv/Scripts/python.exe"
		"python"
		"python3"
	)

	local candidate
	local fallback_candidate=""
	for candidate in "${candidates[@]}"; do
		if command -v "$candidate" >/dev/null 2>&1 || [[ -x "$candidate" ]]; then
			if [[ -z "$fallback_candidate" ]]; then
				fallback_candidate="$candidate"
			fi

			if "$candidate" -c "import playwright" >/dev/null 2>&1; then
				printf '%s\n' "$candidate"
				return 0
			fi
		fi
	done

	if [[ -n "$fallback_candidate" ]]; then
		printf '%s\n' "$fallback_candidate"
		return 0
	fi

	return 1
}

PYTHON_BIN="$(resolve_python_bin)" || {
	log "Python executable was not found."
	exit 1
}

export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"
export PLAYWRIGHT_SKIP_BROWSER_GC="${PLAYWRIGHT_SKIP_BROWSER_GC:-1}"

if [[ "$(uname -s)" == "Linux" ]]; then
	export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-/home/site/wwwroot/.playwright}"
else
	export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$SCRIPT_DIR/.playwright}"
fi

mkdir -p "$PLAYWRIGHT_BROWSERS_PATH"

log "Startup script running from $SCRIPT_DIR"
log "Using Python executable: $PYTHON_BIN"
log "Using Playwright browsers path: $PLAYWRIGHT_BROWSERS_PATH"

install_linux_dependencies() {
	if [[ "$(uname -s)" != "Linux" ]]; then
		log "Skipping apt-get dependency installation on non-Linux host."
		return 0
	fi

	if ! command -v apt-get >/dev/null 2>&1; then
		log "Skipping apt-get dependency installation because apt-get is unavailable."
		return 0
	fi

	local packages=(
		libglib2.0-0
		libnss3
		libnspr4
		libatk1.0-0
		libatk-bridge2.0-0
		libcups2
		libdrm2
		libxkbcommon0
		libxcomposite1
		libxdamage1
		libxfixes3
		libxrandr2
		libgbm1
		libasound2
		libpango-1.0-0
		libcairo2
		libatspi2.0-0
		libgtk-3-0
	)

	export DEBIAN_FRONTEND=noninteractive
	log "Installing Playwright Linux dependencies with apt-get"
	apt-get update
	apt-get install -y --no-install-recommends "${packages[@]}"
	apt-get clean
	rm -rf /var/lib/apt/lists/*
}

install_playwright_chromium() {
	log "Installing Playwright Chromium browser"
	"$PYTHON_BIN" -m playwright install chromium
}

start_server() {
	local host="${HOST:-0.0.0.0}"
	local port="${PORT:-8000}"

	if [[ "$(uname -s)" == "Linux" ]]; then
		local workers="${GUNICORN_WORKERS:-4}"
		log "Launching Gunicorn on ${host}:${port} with ${workers} workers"
		exec "$PYTHON_BIN" -m gunicorn -w "$workers" -k uvicorn.workers.UvicornWorker --bind "${host}:${port}" main:app
	fi

	log "Launching local Uvicorn fallback on ${host}:${port}"
	exec "$PYTHON_BIN" -m uvicorn main:app --host "$host" --port "$port"
}

install_linux_dependencies
install_playwright_chromium

if [[ "${STARTUP_VALIDATE_ONLY:-0}" == "1" ]]; then
	log "Validation-only mode requested; skipping application launch."
	exit 0
fi

start_server