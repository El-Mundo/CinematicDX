#!/bin/sh
set -eu
. "$(dirname -- "$0")/desktop-env.sh"
exec "$cdx_mvn" -f "$cdx_root/cinematic/pom.xml" compile javafx:run "$@"
