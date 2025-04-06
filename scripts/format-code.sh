#!/bin/sh

echo ""
echo "Formatting code..."
black .

echo ""
echo "Sorting imports..."
isort .
