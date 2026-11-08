#!/usr/bin/env bash
set -euo pipefail

# Log file for this test run
LOGFILE="test.log"
echo "" >> "${LOGFILE}"
echo "Test run at $(date)" >> "${LOGFILE}"
echo "=======================================================" >> "${LOGFILE}"

# --- Helper functions ---

# Generate a simple test file
function generate_test_file() {
  local test_file="test-file.src"
  echo "This is a test file for HMAC tampering." > "$test_file"
  # Append some random data
  head -c 256 /dev/urandom | base64 >> "$test_file"
}

# Encrypt the test file using the CLI encryption tool
# We use the block-enc mode as an example.
function encrypt_file() {
  local infile=$1
  local outfile=$2
  local password=$3
  # Remove any previous encrypted file
  rm -f "$outfile"
  # Encrypt the file using the C++ CLI tool (adjust parameters as desired)
  ./rainsum -m block-enc "$infile" --seed 0 --salt hello --nonce-size 14 --block-size 7 --password "$password" >> "${LOGFILE}" 2>&1
  # Our tool is expected to write the encrypted file as infile.rc
  mv "$infile.rc" "$outfile"
}

# Create a tampered version of the encrypted file
# $1: Original encrypted file
# $2: Output file name for tampered file
# $3: offset (in bytes) to tamper
# $4: new byte value (in hex, e.g. "00" or "FF")
function tamper_file_at_offset() {
  local origfile=$1
  local outfile=$2
  local offset=$3
  local newbyte=$4
  # Copy the file first
  cp "$origfile" "$outfile"
  # Use dd to write one byte at the given offset (seek value in bytes) without truncating the file.
  dd if=<(echo -n -e "\x${newbyte}") of="$outfile" bs=1 count=1 seek="$offset" conv=notrunc status=none
}

# Try to decrypt a file with a given tool and check that it fails HMAC verification.
# $1: Tool command (e.g. "./rainsum -m dec --password $password" or "./js/rainsum.mjs -m dec --password $password")
# $2: Encrypted filename
# $3: Expected failure message substring (e.g. "HMAC verification failed")
function test_decryption_failure() {
  local cmd=$1
  local infile=$2
  local expected_msg=$3

  # Capture the decryption output (stderr and stdout)
  local output
  output=$($cmd "$infile" 2>&1 || true)
  echo "$output" >> "${LOGFILE}"
  if ! echo "$output" | grep -qi "$expected_msg"; then
    echo "Test failed: Expected message '$expected_msg' not found in decryption output for file $infile" >&2
    return 1
  fi
  echo "Test passed: Decryption of tampered file $infile failed as expected." >> "${LOGFILE}"
  return 0
}

# --- Main test harness ---

# Clean up previous test artifacts
rm -f test-file.src test-file.src.rc* test-file.src.rc.tampered*

# Generate test file
generate_test_file

# Use a fixed password for testing
PASSWORD="abc123"

# Encrypt the file (we choose block-enc mode as in your example)
ENCRYPTED_FILE="test-file.src.rc"
echo "Encrypting file using block-enc..." >> "${LOGFILE}"
encrypt_file "test-file.src" "$ENCRYPTED_FILE" "$PASSWORD"

# --- Tamper with the header HMAC field ---
# We know from our header implementation that the HMAC is written starting at offset 33.
# For example, we change the byte at offset 33.
TAMPERED_HEADER_FILE="test-file.src.rc.tampered.header"
echo "Tampering with header HMAC (offset 33) in $ENCRYPTED_FILE ..." >> "${LOGFILE}"
tamper_file_at_offset "$ENCRYPTED_FILE" "$TAMPERED_HEADER_FILE" 33 "00"

# Now try to decrypt the tampered file using both C++ and JS tools.
# We expect the decryption output to include a message indicating HMAC verification failure.
echo "Testing decryption failure for tampered header (CPP)..." >> "${LOGFILE}"
test_decryption_failure "./rainsum -m dec --password $PASSWORD" "$TAMPERED_HEADER_FILE" "HMAC verification failed" || exit 1

echo "Testing decryption failure for tampered header (JS)..." >> "${LOGFILE}"
test_decryption_failure "./js/rainsum.mjs -m dec --password $PASSWORD" "$TAMPERED_HEADER_FILE" "HMAC verification failed" || exit 1

# --- Tamper with the ciphertext portion ---
# To tamper with ciphertext, we assume that the header occupies the first N bytes.
# For simplicity, we use the same header size as before (we assume at least 50 bytes in header).
# Change one byte at offset 50.
TAMPERED_CIPHERTEXT_FILE="test-file.src.rc.tampered.ciphertext"
echo "Tampering with ciphertext (offset 50) in $ENCRYPTED_FILE ..." >> "${LOGFILE}"
tamper_file_at_offset "$ENCRYPTED_FILE" "$TAMPERED_CIPHERTEXT_FILE" 50 "FF"

echo "Testing decryption failure for tampered ciphertext (CPP)..." >> "${LOGFILE}"
test_decryption_failure "./rainsum -m dec --password $PASSWORD" "$TAMPERED_CIPHERTEXT_FILE" "HMAC verification failed" || exit 1

echo "Testing decryption failure for tampered ciphertext (JS)..." >> "${LOGFILE}"
test_decryption_failure "./js/rainsum.mjs -m dec --password $PASSWORD" "$TAMPERED_CIPHERTEXT_FILE" "HMAC verification failed" || exit 1

echo "All HMAC tampering tests passed."

