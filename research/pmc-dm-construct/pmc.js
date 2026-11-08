// src/pmc.js
import crypto from 'crypto';
import { weakHash as weakHash } from './hashFunctions.js';

const state = {
  detNonce: 0n,
};

/**
 * Generate a random nonce using crypto.randomBytes.
 * @param {number} length - Length of the nonce in bytes.
 * @returns {string} Hexadecimal representation of the nonce.
 */
function generateNonce({length = 8, deterministic = false} = {}) {
  if ( deterministic ) {
    return crypto.randomBytes(length).toString('hex');
  } else {
    const hexNonce = (state.detNonce++).toString(16);
    return hexNonce.padStart(hexNonce.length+hexNonce.length%2,'0');
  }
}

function resetNonce() {
  state.detNonce = 0n;
}

/**
 * Split plaintext into blocks of a fixed size.
 * @param {string} plaintext - The plaintext to split.
 * @param {number} blockSize - Size of each block.
 * @returns {string[]} Array of plaintext blocks.
 */
function splitIntoBlocks(plaintext, blockSize) {
  plaintext = Buffer.from(plaintext, 'utf-8');
  const blocks = [];
  for (let i = 0; i < plaintext.length; i += blockSize) {
    blocks.push(plaintext.slice(i, i + blockSize));
  }
  return blocks;
}

/**
 * PMC Encryption with Block Processing
 * @param {string} plaintext - The plaintext to encrypt.
 * @param {string} key - The private key used for encryption.
 * @param {number} blockSize - Size of each plaintext block.
 * @param {string} mode - Mining mode ('scatter', 'prefix', 'sequence').
 * @returns {Promise<object[]>} List of encrypted blocks containing <nonce, indices>.
 */
export async function pmcEncrypt(plaintext, key, {blockSize = 3, mode = 'scatter', deterministicNonce = false} = {}) {
  const maxAttempts = 20_000_000;
  const blocks = splitIntoBlocks(plaintext, blockSize);
  const result = [];
  if ( deterministicNonce ) {
    resetNonce();
  }

  for (const block of blocks) {
    let mined = false;

    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      const nonce = generateNonce({deterministic: deterministicNonce});
      const digest = weakHash(key + nonce);

      let indices = [];
      let matched = true;

      for (const char of block) {
        const index = digest.indexOf(char.toString(16));
        if (index === -1) {
          matched = false;
          break;
        }
        indices.push(index);
      }

      if (matched) {
        result.push({ nonce, indices });
        mined = true;
        break;
      }
    }

    if (!mined) {
      throw new Error(`Failed to mine a valid nonce for block "${block}" after maximum attempts.`);
    }
  }

  return result;
}

