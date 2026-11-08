#!/usr/bin/env bash

#set -x

echo "  " >> test.log
echo "  Test run at $(date) " >> test.log
echo " ======================================================= " >> test.log

# Test the encryption and decryption given the parameters using both cpp and js/wasm.
# If an optional 9th parameter is provided and equals "km", then use --key-material.
function encrypt() {
  mode=$1
  key=$2
  outputExtension=$3
  blockSize=$4
  nonceSize=$5
  searchMode=$6
  entropyMode=$7
  deterministicNonce=$8
  keyMode=$9

  # Decide whether to use --password or --key-material
  if [[ "$keyMode" == "km" ]]; then
    keyArg="--key-material $key"
  else
    keyArg="--password $key"
  fi

  success=True

  rm test-file.src.rc* &>> test.log

  set -x
  ./rainsum -m $mode $keyArg --output-extension $outputExtension --block-size $blockSize --nonce-size $nonceSize --search-mode $searchMode --entropy-mode $entropyMode $deterministicNonce test-file.src &>> test.log
  set +x
  mv test-file.src.rc test-file.src.rc.cpp &>> test.log

  if [[ "$searchMode" != "parascatter" ]]; then
    set -x 
    ./js/rainsum.mjs -m $mode $keyArg --output-extension $outputExtension --block-size $blockSize --nonce-size $nonceSize --search-mode $searchMode --entropy-mode $entropyMode $deterministicNonce test-file.src &>> test.log
    set +x
    mv test-file.src.rc test-file.src.rc.js &>> test.log

    ./rainsum -m dec $keyArg test-file.src.rc.js &>> test.log
    if ! diff test-file.src test-file.src.rc.js.dec &>> test.log; then
      echo "JS encrypt (CPP decrypt) failed" >&2
      success=False
    fi

    ./js/rainsum.mjs -m dec $keyArg test-file.src.rc.js &>> test.log
    if ! diff test-file.src test-file.src.rc.js.dec &>> test.log; then
      echo "JS encrypt (JS decrypt) failed" >&2
      success=False
    fi
  fi

  ./rainsum -m dec $keyArg test-file.src.rc.cpp &>> test.log
  if ! diff test-file.src test-file.src.rc.cpp.dec &>> test.log; then
    echo "CPP encrypt (CPP decrypt) failed" >&2
    success=False
  fi

  ./js/rainsum.mjs -m dec $keyArg test-file.src.rc.cpp &>> test.log
  if ! diff test-file.src test-file.src.rc.cpp.dec &>> test.log; then
    echo "CPP encrypt (JS decrypt) failed" >&2
    success=False
  fi

  if $success; then
    return 0
  else
    exit 1
  fi
}

# Generate the short test file.
function generate_short_test_file() {
  local test_file="test-file.src"
  echo -n -e "\x00RCTEST" > $test_file
  return 0
  # Append lorem ipsum text (512 bytes)
  head -c 512 /dev/urandom | base64 >> $test_file
  # Append random integers in ASCII (512 bytes)
  head -c 512 /dev/urandom | od -An -tu1 | tr -d '\n' | head -c 512 >> $test_file
  # Append random base64url (1024 bytes)
  head -c 1024 /dev/urandom | base64 >> $test_file
  # Append random binary (1024 bytes)
  head -c 1024 /dev/urandom >> $test_file
}

# Generate the standard test file.
function generate_test_file() {
  local test_file="test-file.src"
  echo -n -e "\x00RCTEST" > $test_file
  # Append lorem ipsum text (512 bytes)
  head -c 512 /dev/urandom | base64 >> $test_file
  # Append random integers in ASCII (512 bytes)
  head -c 512 /dev/urandom | od -An -tu1 | tr -d '\n' | head -c 512 >> $test_file
  # Append random base64url (1024 bytes)
  head -c 1024 /dev/urandom | base64 >> $test_file
  # Append random binary (1024 bytes)
  head -c 1024 /dev/urandom >> $test_file
}

# Nested loop harness.
function test_harness() {
  local mode block_size nonce_size output_extension search_mode deterministic_nonce entropy_mode

  # Generate the test file (this call might be overridden in inner loops)
  generate_test_file

  # Modes to test.
  modes=("block-enc" "stream-enc")

  # Search modes.
  search_modes=("prefix" "sequence" "series" "scatter" "mapscatter" "parascatter")

  # Entropy modes.
  entropy_modes=("default" "full")

  # Iterate through modes.
  for mode in "${modes[@]}"; do
    if [[ "$mode" == "stream-enc" ]]; then
      for output_extension in $(seq 0 5 1030); do
        for entropy_mode in "${entropy_modes[@]}"; do
          # New inner loop to test both key modes.
          for keyType in "password" "km"; do
            if [[ "$keyType" == "password" ]]; then
              key=$(head -c $((RANDOM % 10 + 1)) /dev/urandom | base64 | tr -d '\n' | cut -c1-10)
            else
              key_file="/tmp/key_material_$$_$RANDOM"
              head -c 1024 /dev/urandom | base64 | head -c 1024 > $key_file
              key=$key_file
            fi
            echo "Testing: mode=$mode, key_mode=$keyType, key=$key, output_extension=$output_extension, entropy_mode=$entropy_mode" 
            echo "Testing: mode=$mode, key_mode=$keyType, key=$key, output_extension=$output_extension, entropy_mode=$entropy_mode" &>> test.log
            encrypt $mode $key $output_extension 1 1 "scatter" $entropy_mode "" $keyType
            if [[ "$keyType" == "km" ]]; then rm $key_file; fi
          done
        done
      done
    elif [[ "$mode" == "block-enc" ]]; then
      for search_mode in "${search_modes[@]}"; do
        if [[ "$search_mode" == "prefix" ]]; then
          generate_short_test_file
          for block_size in $(seq 1 1 2); do
            for nonce_size in $(seq 4 2 6); do
              for deterministic_nonce in {0..1}; do
                for entropy_mode in "${entropy_modes[@]}"; do
                  for keyType in "password" "km"; do
                    if [[ "$keyType" == "password" ]]; then
                      key=$(head -c $((RANDOM % 10 + 1)) /dev/urandom | base64 | tr -d '\n' | cut -c1-10)
                    else
                      key_file="/tmp/key_material_$$_$RANDOM"
                      head -c 1024 /dev/urandom | base64 | head -c 1024 > $key_file
                      key=$key_file
                    fi
                    deterministic_flag=$([[ $deterministic_nonce -eq 1 ]] && echo "--deterministic-nonce" || echo "--noop")
                    echo "Testing: mode=$mode, key_mode=$keyType, key=$key, block_size=$block_size, output_extension=0, nonce_size=$nonce_size, search_mode=$search_mode, deterministic_nonce=$deterministic_flag, entropy_mode=$entropy_mode"
                    echo "Testing: mode=$mode, key_mode=$keyType, key=$key, block_size=$block_size, output_extension=0, nonce_size=$nonce_size, search_mode=$search_mode, deterministic_nonce=$deterministic_flag, entropy_mode=$entropy_mode" &>> test.log
                    encrypt $mode $key 0 $block_size $nonce_size $search_mode $entropy_mode $deterministic_flag $keyType
                    if [[ "$keyType" == "km" ]]; then rm $key_file; fi
                  done
                done
              done
            done
          done
        elif [[ "$search_mode" == "sequence" ]]; then
          generate_short_test_file 
          for block_size in $(seq 2 1 3); do
            for nonce_size in $(seq 6 2 8); do
              for deterministic_nonce in {0..1}; do
                for entropy_mode in "${entropy_modes[@]}"; do
                  for keyType in "password" "km"; do
                    if [[ "$keyType" == "password" ]]; then
                      key=$(head -c $((RANDOM % 10 + 1)) /dev/urandom | base64 | tr -d '\n' | cut -c1-10)
                    else
                      key_file="/tmp/key_material_$$_$RANDOM"
                      head -c 1024 /dev/urandom | base64 | head -c 1024 > $key_file
                      key=$key_file
                    fi
                    deterministic_flag=$([[ $deterministic_nonce -eq 1 ]] && echo "--deterministic-nonce" || echo "--noop")
                    echo "Testing: mode=$mode, key_mode=$keyType, key=$key, block_size=$block_size, output_extension=0, nonce_size=$nonce_size, search_mode=$search_mode, deterministic_nonce=$deterministic_flag, entropy_mode=$entropy_mode"
                    echo "Testing: mode=$mode, key_mode=$keyType, key=$key, block_size=$block_size, output_extension=0, nonce_size=$nonce_size, search_mode=$search_mode, deterministic_nonce=$deterministic_flag, entropy_mode=$entropy_mode" &>> test.log
                    encrypt $mode $key 0 $block_size $nonce_size $search_mode $entropy_mode $deterministic_flag $keyType
                    if [[ "$keyType" == "km" ]]; then rm $key_file; fi
                  done
                done
              done
            done
          done
        elif [[ "$search_mode" == "series" ]]; then
          generate_short_test_file 
          for block_size in $(seq 3 1 4); do
            for nonce_size in $(seq 6 2 8); do
              for deterministic_nonce in {0..1}; do
                for entropy_mode in "${entropy_modes[@]}"; do
                  for keyType in "password" "km"; do
                    if [[ "$keyType" == "password" ]]; then
                      key=$(head -c $((RANDOM % 10 + 1)) /dev/urandom | base64 | tr -d '\n' | cut -c1-10)
                    else
                      key_file="/tmp/key_material_$$_$RANDOM"
                      head -c 1024 /dev/urandom | base64 | head -c 1024 > $key_file
                      key=$key_file
                    fi
                    deterministic_flag=$([[ $deterministic_nonce -eq 1 ]] && echo "--deterministic-nonce" || echo "--noop")
                    echo "Testing: mode=$mode, key_mode=$keyType, key=$key, block_size=$block_size, output_extension=0, nonce_size=$nonce_size, search_mode=$search_mode, deterministic_nonce=$deterministic_flag, entropy_mode=$entropy_mode"
                    echo "Testing: mode=$mode, key_mode=$keyType, key=$key, block_size=$block_size, output_extension=0, nonce_size=$nonce_size, search_mode=$search_mode, deterministic_nonce=$deterministic_flag, entropy_mode=$entropy_mode" &>> test.log
                    encrypt $mode $key 0 $block_size $nonce_size $search_mode $entropy_mode $deterministic_flag $keyType
                    if [[ "$keyType" == "km" ]]; then rm $key_file; fi
                  done
                done
              done
            done
          done
        else
          generate_test_file
          for block_size in $(seq 4 1 10); do
            for output_extension in $(seq 128 128 1024); do
              # Calculate nonce_size start and stop based on block_size.
              for nonce_size in $(seq $((block_size * 3 / 4)) 2 $((block_size * 2))); do
                for deterministic_nonce in {0..1}; do
                  for entropy_mode in "${entropy_modes[@]}"; do
                    for keyType in "password" "km"; do
                      if [[ "$keyType" == "password" ]]; then
                        key=$(head -c $((RANDOM % 10 + 1)) /dev/urandom | base64 | tr -d '\n' | cut -c1-10)
                      else
                        key_file="/tmp/key_material_$$_$RANDOM"
                        head -c 1024 /dev/urandom | base64 | head -c 1024 > $key_file
                        key=$key_file
                      fi
                      deterministic_flag=$([[ $deterministic_nonce -eq 1 ]] && echo "--deterministic-nonce" || echo "--noop")
                      echo "Testing: mode=$mode, key_mode=$keyType, key=$key, block_size=$block_size, nonce_size=$nonce_size, output_extension=$output_extension, search_mode=$search_mode, deterministic_nonce=$deterministic_flag, entropy_mode=$entropy_mode" 
                      echo "Testing: mode=$mode, key_mode=$keyType, key=$key, block_size=$block_size, nonce_size=$nonce_size, output_extension=$output_extension, search_mode=$search_mode, deterministic_nonce=$deterministic_flag, entropy_mode=$entropy_mode" &>> test.log
                      encrypt $mode $key $output_extension $block_size $nonce_size $search_mode $entropy_mode $deterministic_flag $keyType
                      if [[ "$keyType" == "km" ]]; then rm $key_file; fi
                    done
                  done
                done
              done
            done
          done
        fi
      done
    fi
  done
}

# Run the test harness.
test_harness

