#!/bin/bash
# Unpack downloaded Debian host tools locally, without package installation.
set -euo pipefail
cd "$1"
mkdir -p host-tools
for package in *.deb; do
    dpkg-deb -x "$package" host-tools
done
