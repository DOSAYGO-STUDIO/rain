#!/bin/bash

if [ ! -f src/cxxopts.hpp ]; then
  curl -L https://raw.githubusercontent.com/jarro2783/cxxopts/4bf61f08697b110d9e3991864650a405b3dd515d/include/cxxopts.hpp -o src/cxxopts.hpp
fi

export PATH="/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin:${PATH}"
echo "You need emsdk to build wasm"
cd ../emsdk
source ./emsdk_env.sh

cd ../rain

make

