#!/usr/bin/env bash

wd="$(pwd)"
cd ../emsdk
source ./emsdk_env.sh
cd "$wd"
make clean && make && ./js/test.mjs
