#!/usr/bin/env bash
cd "$(dirname "${BASH_SOURCE[0]}")"
source .venv/bin/activate
python -m connect4_engine.main