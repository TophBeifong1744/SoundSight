#!/bin/sh
# Linux offline suite for enrollment and its shared capture/permission paths.
set -eu
repo=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$repo"
e="$repo/document/evidence/speaker-enrollment-20261029"
mkdir -p "$e"
for name in test_speaker_enrollment test_speaker_follow test_speaker_process test_pcm_capture test_three_d_launcher; do
    if sh software/tests/run_stream_python.sh -B "software/tests/$name.py" -v > "$e/$name.log" 2>&1; then
        tail -n 4 "$e/$name.log"
    else
        tail -n 40 "$e/$name.log"
        exit 1
    fi
done
