#!/usr/bin/env bash

#set -x

echo "  " >> benchmark.log
echo "  Benchmark run at $(date) " >> benchmark.log
echo " ======================================================= " >> benchmark.log

# Test the encryption with benchmarking
function benchmark_encrypt() {
  mode=$1
  key=$2
  outputExtension=$3
  blockSize=$4
  nonceSize=$5
  deterministicNonce=$6
  file="test-file.src"

  deterministic_flag=$([[ $deterministicNonce -eq 1 ]] && echo "--deterministic-nonce" || echo "")

  total_time=0
  for i in {1..4}; do
    echo "Running $mode test: blockSize=$blockSize, nonceSize=$nonceSize, outputExtension=$outputExtension, deterministicNonce=$deterministicNonce (Iteration $i of 4)" >&2
    start_time=$(gdate +%s.%N 2>/dev/null || date +%s.%N)
    ./rainsum -m $mode --password $key --output-extension $outputExtension \
      --block-size $blockSize --nonce-size $nonceSize $deterministic_flag $file &>> benchmark.log
    end_time=$(gdate +%s.%N 2>/dev/null || date +%s.%N)

    if [[ $start_time =~ N$ ]]; then
      start_time=${start_time%N}
    fi
    if [[ $end_time =~ N$ ]]; then
      end_time=${end_time%N}
    fi

    duration=$(awk "BEGIN {print ($end_time - $start_time) * 1000}")
    total_time=$(awk "BEGIN {print $total_time + $duration}")
  done

  avg_time=$(awk "BEGIN {print $total_time / 4}")

  echo "$mode: blockSize=$blockSize, nonceSize=$nonceSize, outputExtension=$outputExtension, deterministicNonce=$deterministicNonce, avg_time=${avg_time}ms" >> results.log

  echo "$mode,$blockSize,$nonceSize,$outputExtension,$deterministicNonce,$avg_time" >> raw_results.csv

  echo $avg_time
}

# Generate the test file
function generate_test_file() {
  local test_file="test-file.src"
  head -c 1M /dev/urandom | base64 > $test_file
}

# Find optimal parameters
function find_optimal_parameters() {
  local mode=$1
  generate_test_file

  best_time=999999999
  best_params=""

  for blockSize in {6..64..16}; do
    for nonceSize in {2..82..20}; do
      for outputExtension in {512..4096..512}; do
        for deterministicNonce in {0..1}; do
          password=$(head -c 10 /dev/urandom | base64 | tr -d '\n' | cut -c1-10)
          echo "Testing $mode: blockSize=$blockSize, nonceSize=$nonceSize, outputExtension=$outputExtension, deterministicNonce=$deterministicNonce"
          avg_time=$(benchmark_encrypt $mode $password $outputExtension $blockSize $nonceSize $deterministicNonce)

          if (( $(echo "$avg_time < $best_time" | bc -l) )); then
            best_time=$avg_time
            best_params="blockSize=$blockSize, nonceSize=$nonceSize, outputExtension=$outputExtension, deterministicNonce=$deterministicNonce"
          fi
        done
      done
    done
  done

  echo "Optimal parameters for $mode: $best_params, avg_time=${best_time}ms" >> results.log
  echo "Optimal parameters for $mode: $best_params, avg_time=${best_time}ms"
}

# Display sorted results in a table
function display_sorted_results() {
  local mode=$1
  echo "Sorted results for $mode (Top 25):" >> sorted_results.log
  echo "blockSize,nonceSize,outputExtension,deterministicNonce,avg_time" >> sorted_results.log
  grep "^$mode" raw_results.csv | sort -t, -k6 -n | head -25 >> sorted_results.log

  echo "Sorted results for $mode (Top 25):"
  echo "blockSize,nonceSize,outputExtension,deterministicNonce,avg_time"
  grep "^$mode" raw_results.csv | sort -t, -k6 -n | head -25
}

# Run optimization for both modes
find_optimal_parameters "stream-enc"
find_optimal_parameters "block-enc"

display_sorted_results "stream-enc"
display_sorted_results "block-enc"

