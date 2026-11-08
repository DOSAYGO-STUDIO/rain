// src/daviesMeyer.js
import crypto from 'crypto';
import { pmcEncrypt } from './pmc.js';
/**
 * Serialize nonce/indices into a fixed-length binary representation.
 * @param {object} block - The block containing nonce and indices.
 * @returns {Buffer} Serialized binary representation of the block.
 */
function serializeBlockToBinary(block) {
  const { nonce, indices } = block;

  // Convert nonce to a Buffer
  const nonceBuffer = Buffer.from(nonce, 'hex');

  // Convert indices to a fixed-length Buffer (e.g., 32 bytes)
  const indicesBuffer = Buffer.alloc(32);
  indices.forEach((index, i) => {
    if (i < indicesBuffer.length) {
      indicesBuffer.writeUInt8(index, i);
    }
  });

  // Concatenate nonce and indices buffers
  return Buffer.concat([nonceBuffer, indicesBuffer]);
}

/**
 * Davies-Meyer Hash Construction
 * @param {object[]} cipherBlocks - Array of cipher blocks from PMC (nonce/indices).
 * @param {string} chainingValue - The current chaining value (initially IV).
 * @returns {string} The updated chaining value (hash).
 */
export async function daviesMeyer(cipherBlocks, chainingValue) {
  for (const block of cipherBlocks) {
    // Serialize the block into binary
    const blockBinary = serializeBlockToBinary(block);

    // Convert chaining value to Buffer
    const chainingBuffer = Buffer.from(chainingValue, 'hex');

    // Ensure both are the same length (pad or trim chainingBuffer if needed)
    const xorLength = Math.min(chainingBuffer.length, blockBinary.length);
    const xorResult = Buffer.alloc(xorLength);
    for (let i = 0; i < xorLength; i++) {
      xorResult[i] = chainingBuffer[i] ^ blockBinary[i];
    }

    // Update chaining value
    chainingValue = xorResult.toString('hex').padStart(64, '0');
  }

  return chainingValue;
}
