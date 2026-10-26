#!/bin/sh
# Shared environment discovery; no downloads or persistent preference changes.
cdx_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cdx_mvn=$(command -v mvn || true)
if [ -z "$cdx_mvn" ]; then
    for cdx_candidate in "$HOME"/.m2/wrapper/dists/*/*/*/bin/mvn; do
        if [ -x "$cdx_candidate" ]; then cdx_mvn=$cdx_candidate; break; fi
    done
fi
if [ -z "$cdx_mvn" ]; then
    echo "Maven is required. Install Maven or add an existing installation to PATH." >&2
    exit 1
fi
if [ -z "${JAVA_HOME:-}" ] && [ "$(uname -s)" = Darwin ]; then
    cdx_java_home=$(/usr/libexec/java_home -v 17 2>/dev/null || true)
    if [ -n "$cdx_java_home" ]; then export JAVA_HOME="$cdx_java_home"; fi
fi
