#!/usr/bin/env node
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import {
  blockDecryptBuffer,
  blockEncryptBuffer,
  rainstormHash,
  rainbowHash,
  streamDecryptBuffer,
  streamEncryptBuffer,
  testVectors,
} from './lib/api.mjs';

await testVectors();
const { vectors } = JSON.parse(await readFile(new URL('./test-vectors.json', import.meta.url), 'utf8'));
for (const vector of vectors) {
  const hash = vector.algorithm === 'rainstorm' ? rainstormHash : rainbowHash;
  const actual = await hash(vector.bits, BigInt(vector.seed), vector.message);
  assert.equal(actual, vector.hex, `${vector.algorithm}-${vector.bits}: ${JSON.stringify(vector.message)}`);
}
console.log(`PASS: ${vectors.length} native/WASM vectors across all digest sizes.`);

// HMAC calculation allocates after encryption: ciphertext must own its bytes,
// rather than retain a view into the result buffer freed by the WASM wrapper.
const plaintext = Buffer.from(Array.from({ length: 286 }, (_, i) => i & 255));
const password = 'public-test-password';
const ciphertext = await streamEncryptBuffer(plaintext, password, 'rainstorm', 512,
  0n, Buffer.from('release-fixture'), 128, false);
const originalCiphertext = Buffer.from(ciphertext);
for (let i = 0; i < 16; i++) await rainstormHash(512, 0n, plaintext);
assert.deepEqual(ciphertext, originalCiphertext);
assert.deepEqual(await streamDecryptBuffer(ciphertext, password, false), plaintext);
console.log('PASS: WASM stream-cipher buffer ownership and round trip.');

const blockKey = Buffer.from(password);
const blockCiphertext = await blockEncryptBuffer(
  plaintext,
  blockKey,
  'rainstorm',
  'scatter',
  512,
  9,
  9,
  0n,
  Buffer.from('release-fixture'),
  256,
  false,
  false,
);
const originalBlockCiphertext = Buffer.from(blockCiphertext);
for (let i = 0; i < 16; i++) await rainstormHash(512, 0n, plaintext);
assert.deepEqual(blockCiphertext, originalBlockCiphertext);

const blockPlaintext = await blockDecryptBuffer(blockCiphertext, blockKey);
for (let i = 0; i < 16; i++) await rainstormHash(512, 0n, plaintext);
assert.deepEqual(blockPlaintext, plaintext);
console.log('PASS: WASM block-cipher buffer ownership and round trip.');
