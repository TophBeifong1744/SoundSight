#!/bin/sh
# Product panel: explicit touch START, initial axes OFF, no prepare/download.
set -eu
cd -- "$(dirname -- "$0")"
exec sh ./soundsight-screen.sh --control --enable-motion "$@"
