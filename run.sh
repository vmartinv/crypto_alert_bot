#!/usr/bin/env bash

source .venv/bin/activate
pip install -r requirements.txt
python3 tg_bot_service.py
