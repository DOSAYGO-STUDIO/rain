#!/usr/bin/env bash

echo "Make it Rain!" | ./rainsum -a storm -s 256 -l 400000000 -m stream | xxd -b -c 256 | grep -o '[01]' | tr -d '\n'\
  | tr '0' ' ' | tr '1' "${1:-1}"

