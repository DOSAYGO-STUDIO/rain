#!/usr/bin/env node
import assert from 'node:assert/strict';
import {
  blockDecryptBuffer,
  blockEncryptBuffer,
  rainstormHash,
  streamDecryptBuffer,
  streamEncryptBuffer,
  testVectors,
} from './lib/api.mjs';

await testVectors();

const plaintext = Buffer.from(Array.from({ length: 286 }, (_, i) => i & 255));
const password = 'public-test-password';
const salt = Buffer.from('release-fixture');

const streamCiphertext = await streamEncryptBuffer(
  plaintext,
  password,
  'rainstorm',
  512,
  0n,
  salt,
  128,
  false,
);
const originalStreamCiphertext = Buffer.from(streamCiphertext);
for (let i = 0; i < 16; i++) await rainstormHash(512, 0n, plaintext);
assert.deepEqual(streamCiphertext, originalStreamCiphertext);
assert.deepEqual(await streamDecryptBuffer(streamCiphertext, password, false), plaintext);
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
  salt,
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
