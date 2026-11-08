// src/hashFunctions.js
export function weakHash(input) {
  // A simple non-cryptographic hash function
  let hash = 0;
  for (let i = 0; i < input.length; i++) {
    hash = (hash * 31 + input.charCodeAt(i)) & 0xffffffff;
  }
  const digest = hash.toString(16).padStart(8, '0');
  return digest.repeat(4).slice(0, 32); // Extend to 32 bytes for testing
}

export function weakHash1(input) {
  // Initialize state variables
  let state = new BigInt64Array([0x243F6A88n, 0x85A308D3n, 0x13198A2En, 0x03707344n]);
  const inputBytes = Buffer.from(input);

  // Process each byte in the input
  for (const byte of inputBytes) {
    state[0] ^= BigInt(byte);
    state[1] = (state[1] + state[0]) & 0xffffffffn;
    state[2] = (state[2] ^ (state[1] >> 5n)) & 0xffffffffn;
    state[3] = (state[3] + (state[2] << 7n)) & 0xffffffffn;

    // Shuffle state
    const tmp = state[0];
    state[0] = state[1];
    state[1] = state[2];
    state[2] = state[3];
    state[3] = tmp;
  }

  console.log({state});

  // Combine state into a hex digest
  const digest = Array.from(state)
    .map((word) => word.toString(16).padStart(8, '0'))
    .join('')
    .repeat(2) // Repeat to make a 32-byte digest
    .slice(0, 32); // Ensure exactly 32 bytes
  console.log({digest});
  return digest;
}

