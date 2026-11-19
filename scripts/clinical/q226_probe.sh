#!/bin/bash
# restage the current imaging files into a build/q226 page dir and probe it (dev helper)
set -e; cd "$(dirname "$0")/../.."
python3 scripts/clinical/stage_clinical_files.py --imaging-only "$1" >/dev/null
shift; python3 scripts/clinical/q226_probe.py "$@"
