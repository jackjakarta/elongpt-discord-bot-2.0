#!/bin/sh

ENVIRONMENT=development op run --env-file=".env.op" --no-masking -- python main.py
