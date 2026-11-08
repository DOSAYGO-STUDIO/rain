#!/usr/bin/env bash

size=${1:-256}
alg=${2:-storm}
echo "Make it Rain!" | ./rainsum -a $alg -s $size -l 400000000 -m stream | xxd -b -c 256 | grep -o '[01]' | tr -d '\n'\
  | tr '0' ' ' | tr '1' '1'

