#!/bin/sh
set -eu
. "$(dirname -- "$0")/desktop-env.sh"
if [ "$(uname -s)" != Darwin ]; then
    echo "This packaging script creates a macOS application. Use run-desktop.sh elsewhere." >&2
    exit 1
fi
if [ -z "${JAVA_HOME:-}" ] || [ ! -x "$JAVA_HOME/bin/jpackage" ]; then
    echo "A JDK with jpackage is required. Set JAVA_HOME to an installed JDK 17 or newer." >&2
    exit 1
fi
cdx_destination="$cdx_root/cinematic/target/desktop"
if [ -e "$cdx_destination/CinematicDX.app" ]; then
    echo "An app already exists at $cdx_destination/CinematicDX.app; move it before packaging again." >&2
    exit 1
fi
cdx_input=$(mktemp -d "$cdx_root/cinematic/target/desktop-input.XXXXXX")
"$cdx_mvn" -f "$cdx_root/cinematic/pom.xml" package dependency:copy-dependencies \
    -DincludeScope=runtime -DoutputDirectory="$cdx_input" "$@"
cp "$cdx_root/cinematic/target/cinematic-1.jar" "$cdx_input/"
"$JAVA_HOME/bin/jpackage" --type app-image --name CinematicDX --app-version 1.0 \
    --input "$cdx_input" --main-jar cinematic-1.jar --main-class com.elmundo.DesktopLauncher \
    --runtime-image "$JAVA_HOME" --dest "$cdx_destination" \
    --mac-package-identifier com.elmundo.CinematicDX \
    --java-options "-Dcinematicdx.workspace=$cdx_root" \
    --java-options "-Dcinematicdx.config=${CINEMATICDX_CONFIG:-}"
echo "Built $cdx_destination/CinematicDX.app"
