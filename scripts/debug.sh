#!/bin/bash

make clean && make
./scripts/bench.mjs
./js/rainsum.mjs --test-vectors
