// lib/api.mjs

export let rain = { loaded: false };

const STORM_TV = [
  [ "bf6aa062a4c6ccf8b69697494100743f24da78e0e0140af278f3156772734b49", "" ],
  [ "a3eeff6dbbf8213dd3b3b00a7ad813a76dc20f9c8ddb4424ee906bca3616e7b9", "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" ],
  [ "2343e4baabecf8be423ab643fcdfa113e14bf75e7a5f8a6a37f02a260282ac45", "The quick brown fox jumps over the lazy dog" ],
  [ "336f151a152a50930cf47ac8a787f55bc37e711945cc1845ec1aa4c4fdb257d4", "The quick brown fox jumps over the lazy cog" ],
  [ "638cce058cae9895f61c5c03a6d75e8c56a8d4a138a01d6bf60038d076e12177", "The quick brown fox jumps over the lazy dog." ],
  [ "3ca3ed36a2503b5908d5deb596951a57b7dad37fc7d2dda756c91124acafdfd1", "After the rainstorm comes the rainbow." ],
  [ "3cb0c1d4fd07567910057bf9a884651da54ae2117619b3c143e96870032eb5e3", "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@" ],
];

const BOW_TV = [
  [ "91fc76841e1431f6d58871e4c981fb37e3c0ac0f9f141c3e99b78f46c727c454", "" ],
  [ "5440efa52854703021a894a61ad25690515347014a9723880ed86854ecf2247f", "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" ],
  [ "9c72cf9f50d0f3145ad0f45cf97c09afa6f7555562358dc15c4f4bb14cf2aa85", "The quick brown fox jumps over the lazy dog" ],
  [ "d75f220dc093a669b235ae713a8ce0f7ff33a8c40357bd66f89e885d7fbcb1c9", "The quick brown fox jumps over the lazy cog" ],
  [ "6af5f348167fe18ca480b952e4ce7ed05de4bc25bdfd68a2929b7025ad784280", "The quick brown fox jumps over the lazy dog." ],
  [ "c43f32b0730fefc3a97acfbed163c649744e5a167c681bd561da15d2385425cf", "After the rainstorm comes the rainbow." ],
  [ "49b4f0ad1df0e644296592dfa55d4ad6243e746b6ffe4ece343c41102a2c7507", "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@" ],
];

export async function testVectors() {
  if (!rain.loaded) {
    await loadRain();
  }
  let comment;

  console.log(`Rainstorm test vectors:`);
  for (const [expectedHash, message] of STORM_TV) {
    const calculatedHash = await rainstormHash(256, 0, message);
    if (calculatedHash !== expectedHash) {
      comment = "MISMATCH!";
      console.error(`Expected: ${expectedHash}, but got: ${calculatedHash}`);
    } else {
      comment = "";
    }
    console.log(`${calculatedHash} "${message}" ${comment}`);
  }

  console.log(`Rainbow test vectors:`);
  for (const [expectedHash, message] of BOW_TV) {
    const calculatedHash = await rainbowHash(256, 0, message);
    if (calculatedHash !== expectedHash) {
      comment = "MISMATCH!";
      console.error(`Expected: ${expectedHash}, but got: ${calculatedHash}`);
    } else {
      comment = "";
    }
    console.log(`${calculatedHash} "${message}" ${comment}`);
  }
}

export async function rainstormHash(hashSize, seed, input) {
  if (!rain.loaded) {
    await loadRain();
  }
  const { stringToUTF8, lengthBytesUTF8 } = rain;
  const { malloc: _malloc, free: _free } = rain.wasmExports;

  const hashLength = hashSize / 8;
  const hashPtr = _malloc(hashLength);

  let inputPtr;
  let inputLength;

  if (typeof input === "string") {
    inputLength = lengthBytesUTF8(input);
    inputPtr = _malloc(inputLength);
    stringToUTF8(input, inputPtr, inputLength + 1);
  } else {
    inputLength = input.length;
    inputPtr = _malloc(inputLength);
    rain.HEAPU8.set(input, inputPtr);
  }

  // Select the appropriate hash function based on hashSize
  let hashFunc;
  switch (hashSize) {
    case 64:
      hashFunc = rain.rainstormHash64;
      break;
    case 128:
      hashFunc = rain.rainstormHash128;
      break;
    case 256:
      hashFunc = rain.rainstormHash256;
      break;
    case 512:
      hashFunc = rain.rainstormHash512;
      break;
    default:
      throw new Error(`Unsupported hash size for rainstorm: ${hashSize}`);
  }

  // Call the WASM hash function
  hashFunc(inputPtr, inputLength, BigInt(seed), hashPtr);

  // Retrieve the hash from WASM memory
  const hash = new Uint8Array(rain.HEAPU8.buffer, hashPtr, hashLength);
  const hashHex = Array.from(hash).map(x => x.toString(16).padStart(2, '0')).join('');

  // Free allocated memory
  _free(hashPtr);
  _free(inputPtr);

  return hashHex;
}

export async function rainbowHash(hashSize, seed, input) {
  if (!rain.loaded) {
    await loadRain();
  }
  const { stringToUTF8, lengthBytesUTF8 } = rain;
  const { malloc: _malloc, free: _free } = rain.wasmExports;

  const hashLength = hashSize / 8;
  const hashPtr = _malloc(hashLength);

  let inputPtr;
  let inputLength;

  if (typeof input === "string") {
    inputLength = lengthBytesUTF8(input);
    inputPtr = _malloc(inputLength);
    stringToUTF8(input, inputPtr, inputLength + 1);
  } else {
    inputLength = input.length;
    inputPtr = _malloc(inputLength);
    rain.HEAPU8.set(input, inputPtr);
  }

  // Select the appropriate hash function based on hashSize
  let hashFunc;
  switch (hashSize) {
    case 64:
      hashFunc = rain._rainbowHash64;
      break;
    case 128:
      hashFunc = rain._rainbowHash128;
      break;
    case 256:
      hashFunc = rain._rainbowHash256;
      break;
    default:
      throw new Error(`Unsupported hash size for rainbow: ${hashSize}`);
  }

  // Call the WASM hash function
  hashFunc(inputPtr, inputLength, BigInt(seed), hashPtr);

  // Retrieve the hash from WASM memory
  const hash = new Uint8Array(rain.HEAPU8.buffer, hashPtr, hashLength);
  const hashHex = Array.from(hash).map(x => x.toString(16).padStart(2, '0')).join('');

  // Free allocated memory
  _free(hashPtr);
  _free(inputPtr);

  return hashHex;
}

export async function getFileHeaderInfo(buffer) {
  if (!rain.loaded) {
    await loadRain();
  }
  const { UTF8ToString } = rain;
  const { wasmGetFileHeaderInfo, wasmFree, malloc: _malloc, free: _free } = rain.wasmExports;

  // Allocate memory in WASM for the buffer
  const bufferPtr = _malloc(buffer.length);
  rain.HEAPU8.set(buffer, bufferPtr);

  // Call the WASM function to get header info
  const infoPtr = wasmGetFileHeaderInfo(bufferPtr, buffer.length);

  // Retrieve the string from WASM memory
  const info = UTF8ToString(infoPtr);

  // Free the allocated memory in WASM
  wasmFree(infoPtr);
  _free(bufferPtr);

  return info;
}

export async function updateHeaderHMAC(encryptedBuffer, key) {
  if (!rain.loaded) {
    await loadRain();
  }
  const { HEAPU8, wasmExports: { malloc: _malloc, free: _free, wasmSerializeHeader, wasmWriteHMACToBuffer, wasmFreeBuffer } } = rain;
  // Allocate space for entire encryptedBuffer in WASM memory.
  const bufPtr = _malloc(encryptedBuffer.length);
  rain.HEAPU8.set(encryptedBuffer, bufPtr);

  // Allocate pointer for the header size (4 bytes)
  const outHeaderSizePtr = _malloc(4);
  // Call wasmSerializeHeader on the encrypted data.
  const headerPtr = wasmSerializeHeader(bufPtr, encryptedBuffer.length, outHeaderSizePtr);
  const headerSize = rain.getValue(outHeaderSizePtr, 'i32');

  // Create a JS Uint8Array view of the header.
  const headerBytes = new Uint8Array(HEAPU8.buffer, headerPtr, headerSize);
  // The ciphertext is the remainder.
  const ciphertextBuffer = encryptedBuffer.slice(headerSize);
  // Compute new HMAC using the header bytes, ciphertext, and key.
  const newHMAC = await createHMAC(headerBytes, ciphertextBuffer, key);

  // Allocate WASM memory for the new HMAC.
  const hmacPtr = _malloc(newHMAC.length);
  rain.HEAPU8.set(newHMAC, hmacPtr);

  // Call wasmWriteHMACToBuffer to update the header's HMAC field.
  const ret = wasmWriteHMACToBuffer(headerPtr, headerSize, hmacPtr);
  if (ret !== 0) {
    throw new Error("wasmWriteHMACToBuffer failed");
  }
  // Get the updated header from WASM memory.
  const updatedHeader = new Uint8Array(HEAPU8.buffer, headerPtr, headerSize);
  // Copy updated header back into the encryptedBuffer.
  encryptedBuffer.set(updatedHeader, 0);

  // Free allocated WASM memory.
  _free(bufPtr);
  _free(outHeaderSizePtr);
  _free(hmacPtr);
  wasmFreeBuffer(headerPtr);

  return encryptedBuffer;
}

export async function createHMAC(headerData, ciphertext, key) {
    if (!rain.loaded) {
      await loadRain();
    }

    const { malloc: _malloc, free: _free } = rain.wasmExports;
    const headerDataPtr = _malloc(headerData.length);
    rain.HEAPU8.set(headerData, headerDataPtr);

    const ciphertextPtr = _malloc(ciphertext.length);
    rain.HEAPU8.set(ciphertext, ciphertextPtr);

    const keyPtr = _malloc(key.length);
    rain.HEAPU8.set(key, keyPtr);

    const outHMACLenPtr = _malloc(4);
    const hmacPtr = rain.wasmExports.wasmCreateHMAC(headerDataPtr, headerData.length, ciphertextPtr, ciphertext.length, keyPtr, key.length, outHMACLenPtr);

    const outHMACLen = rain.getValue(outHMACLenPtr, 'i32');
    const hmac = new Uint8Array(rain.HEAPU8.buffer, hmacPtr, outHMACLen);

    // Cleanup
    _free(headerDataPtr);
    _free(ciphertextPtr);
    _free(keyPtr);
    _free(outHMACLenPtr);

    return hmac.slice(); // Copy result to avoid memory issues
}

export async function verifyHMAC(headerData, ciphertext, key, hmacToCheck) {
    if (!rain.loaded) {
      await loadRain();
    }
    const { malloc: _malloc, free: _free } = rain.wasmExports;

    const headerDataPtr = _malloc(headerData.length);
    rain.HEAPU8.set(headerData, headerDataPtr);

    const ciphertextPtr = _malloc(ciphertext.length);
    rain.HEAPU8.set(ciphertext, ciphertextPtr);

    const keyPtr = _malloc(key.length);
    rain.HEAPU8.set(key, keyPtr);

    const hmacToCheckPtr = _malloc(hmacToCheck.length);
    rain.HEAPU8.set(hmacToCheck, hmacToCheckPtr);

    const result = rain.wasmExports.wasmVerifyHMAC(headerDataPtr, headerData.length, ciphertextPtr, ciphertext.length, keyPtr, key.length, hmacToCheckPtr, hmacToCheck.length);

    // Cleanup
    _free(headerDataPtr);
    _free(ciphertextPtr);
    _free(keyPtr);
    _free(hmacToCheckPtr);

    return result;
}


/**
 * Decrypts a buffer using the WASM buffer-based decryption function.
 * @param {Buffer} encryptedData - The encrypted data [FileHeader + XOR'd data].
 * @param {string} password - User password.
 * @param {boolean} verbose - Verbose flag.
 * @returns {Buffer} - The decrypted plaintext data.
 */
export async function streamDecryptBuffer(
  encryptedData,
  password,
  verbose
) {
  try {
    if (!rain.loaded) {
      await loadRain();
    }

    const { wasmExports: { wasmStreamDecryptBuffer, wasmFreeBuffer, wasmFreeString, malloc: _malloc, free: _free }, HEAPU8, HEAPU32, UTF8ToString } = rain;

    // Allocate memory for encrypted buffer
    const encryptedPtr = _malloc(encryptedData.length);
    HEAPU8.set(encryptedData, encryptedPtr);

    // Allocate memory for password string (+1 for null-terminator)
    const passwordLength = Buffer.byteLength(password, 'utf-8');
    const passwordPtr = _malloc(passwordLength + 1);
    HEAPU8.set(Buffer.from(password, 'utf-8'), passwordPtr);
    HEAPU8[passwordPtr + passwordLength] = 0; // Null-terminate

    // Allocate memory for output pointers (uint8_t** outBufferPtr and size_t* outBufferSizePtr)
    const outBufferPtr = _malloc(4); // Assuming 32-bit pointers; adjust if using 64-bit
    const outBufferSizePtr = _malloc(4); // Assuming 32-bit size_t; adjust if using 64-bit

    // Allocate memory for error message pointer (char** errorPtr)
    const errorPtr = _malloc(4); // Pointer to error message string

    // Debug logs
    if (verbose) {
      console.log({
        encryptedPtr,
        length: encryptedData.length,
        passwordPtr,
        passwordLength,
        verbose,
        outBufferPtr,
        outBufferSizePtr,
        errorPtr
      });
    }

    // Call the WASM decryption function
    wasmStreamDecryptBuffer(
      encryptedPtr,
      encryptedData.length,
      passwordPtr,
      passwordLength,
      verbose ? 1 : 0,
      outBufferPtr,
      outBufferSizePtr,
      errorPtr // Pass the error pointer
    );

    // Retrieve the decrypted buffer pointer and size from WASM memory
    const decryptedPtr = HEAPU8.length >= (outBufferPtr >> 2) + 1 ? HEAPU32[outBufferPtr >> 2] : 0;
    const decryptedSize = HEAPU32[outBufferSizePtr >> 2];
    const errorMessageAddress = HEAPU32[errorPtr >> 2];

    // Read the error message if present
    let errorMessage = null;
    if (errorMessageAddress !== 0) {
      errorMessage = UTF8ToString(errorMessageAddress);
      // Free the error message string after reading
      wasmFreeString(errorMessageAddress);
    }

    // Free allocated memory for error pointer
    _free(errorPtr);

    // Check for errors
    if (!decryptedPtr || !decryptedSize) {
      // If an error message exists, throw it; otherwise, use a generic message
      throw new Error(errorMessage || "Decryption failed or returned empty buffer.");
    }

     // Safer approach: copy from subarray
    const decryptedCopy = new Uint8Array(
      rain.HEAPU8.subarray(decryptedPtr, decryptedPtr + decryptedSize)
    );
    const decryptedData = Buffer.from(decryptedCopy);

    // Free allocated memory in WASM
    wasmFreeBuffer(decryptedPtr);
    _free(encryptedPtr);
    _free(passwordPtr);
    _free(outBufferPtr);
    _free(outBufferSizePtr);

    // Return the decrypted data
    return decryptedData;
  } catch(e) {
    console.warn("Error", e);
  }
}

/**
 * Encrypts a buffer using the WASM buffer-based encryption function.
 * @param {Buffer} plainData - The plaintext data (already compressed).
 * @param {string} password - User password/IKM.
 * @param {string} algorithm - 'rainbow' or 'rainstorm'.
 * @param {number} hashBits - Hash size in bits.
 * @param {BigInt} seed - 64-bit seed (IV).
 * @param {Buffer} salt - Additional salt.
 * @param {number} outputExtension - Extra bytes of keystream offset.
 * @param {boolean} verbose - Verbose flag.
 * @returns {Buffer} - The encrypted data [FileHeader + XOR'd data].
 */
export async function streamEncryptBuffer(
  plainData,
  password,
  algorithm,
  hashBits,
  seed,
  salt,
  outputExtension,
  verbose
) {
  try {
    if (!rain.loaded) {
      await loadRain();
    }

    const { wasmExports: { wasmStreamEncryptBuffer, wasmFreeBuffer, malloc: _malloc, free: _free }, HEAPU8, HEAPU32 } = rain;

    // Allocate memory for input buffer (plainData)
    const plainDataPtr = _malloc(plainData.length);
    HEAPU8.set(plainData, plainDataPtr);

    // Allocate memory for password string
    const passwordLength = Buffer.byteLength(password, 'utf-8');
    const passwordPtr = _malloc(passwordLength + 1); // +1 for null-terminator
    HEAPU8.set(Buffer.from(password, 'utf-8'), passwordPtr);
    HEAPU8[passwordPtr + passwordLength] = 0; // Null-terminate

    // Allocate memory for algorithm string
    const algorithmLength = Buffer.byteLength(algorithm, 'utf-8');
    const algorithmPtr = _malloc(algorithmLength + 1); // +1 for null-terminator
    HEAPU8.set(Buffer.from(algorithm, 'utf-8'), algorithmPtr);
    HEAPU8[algorithmPtr + algorithmLength] = 0; // Null-terminate

    // Allocate memory for salt
    const saltLen = salt.length;
    const saltPtr = _malloc(saltLen);
    HEAPU8.set(salt, saltPtr);

    // Allocate memory for output pointers (uint8_t** outBufferPtr and size_t* outBufferSizePtr)
    const outBufferPtr = _malloc(4); // Assuming 32-bit pointers; adjust if using 64-bit
    const outBufferSizePtr = _malloc(4); // Assuming 32-bit size_t; adjust if using 64-bit

    // Debug logs
    if (verbose) {
      console.log({
        plainDataPtr,
        length: plainData.length,
        passwordPtr,
        passwordLength,
        algorithmPtr,
        algorithmLength,
        hashBits,
        seed,
        saltPtr,
        saltLen,
        outputExtension,
        verbose,
        outBufferPtr,
        outBufferSizePtr
      });
    }

    // Call the WASM encryption function
    wasmStreamEncryptBuffer(
      plainDataPtr,
      plainData.length,
      passwordPtr,
      passwordLength,
      algorithmPtr,
      algorithmLength,
      hashBits,
      seed,
      saltPtr,
      saltLen,
      outputExtension,
      verbose ? 1 : 0,
      outBufferPtr,
      outBufferSizePtr
    );

    // Retrieve the encrypted buffer pointer and size from WASM memory
    const encryptedPtr = HEAPU32[outBufferPtr >> 2];
    const encryptedSize = HEAPU32[outBufferSizePtr >> 2];

    if (!encryptedPtr || !encryptedSize) {
      throw new Error("Encryption failed or returned empty buffer.");
    }

    // Copy encrypted data from WASM memory to Node.js Buffer
    // Own the bytes before freeing WASM memory; HMAC calculation allocates again.
    const encryptedData = Buffer.from(rain.HEAPU8.subarray(encryptedPtr, encryptedPtr + encryptedSize));

    // Free allocated memory in WASM
    wasmFreeBuffer(encryptedPtr);
    _free(plainDataPtr);
    _free(passwordPtr);
    _free(algorithmPtr);
    _free(saltPtr);
    _free(outBufferPtr);
    _free(outBufferSizePtr);


    // Update the header HMAC using the same key (password)
    const updatedBuffer = await updateHeaderHMAC(encryptedData, Buffer.from(password, 'utf8'));
    return updatedBuffer;
  } catch (err) {
    console.warn("Wasm error", err);
    throw err; // Re-throw to be handled by higher-level functions
  }
}

// Just the snippet showing the new block-based API wrappers in api.mjs:

/**
 * Encrypts a buffer using the WASM block-based encryption function.
 */
export async function blockEncryptBuffer(
  plainText,
  key,
  algorithm,
  searchMode,
  hashBits,
  blockSize, 
  nonceSize,
  seed,
  salt,
  outputExtension,
  deterministicNonce,
  verbose
) {
  if (!rain.loaded) {
    await loadRain();
  }
  let result = await rain.encryptData({plainText, key, algorithm, searchMode, hashBits, blockSize, nonceSize, seed, salt, outputExtension, deterministicNonce, verbose});
  result = await updateHeaderHMAC(result, key);
  return result;

}

/**
 * Decrypts a buffer using the WASM block-based decryption function.
 */
export async function blockDecryptBuffer(
  cipherData,
  password,
  verbose = false
) {
  if (!rain.loaded) {
    await loadRain();
  }

  const {
    wasmExports: { wasmBlockDecryptBuffer, wasmFreeBuffer, malloc: _malloc, free: _free },
    HEAPU8,
    HEAPU32
  } = rain;

  // Allocate memory for ciphertext
  const cipherPtr = _malloc(cipherData.length);
  HEAPU8.set(cipherData, cipherPtr);

  // Allocate memory for password
  const passwordLength = Buffer.byteLength(password, 'utf-8');
  const passwordPtr = _malloc(passwordLength + 1);
  HEAPU8.set(Buffer.from(password, 'utf-8'), passwordPtr);
  HEAPU8[passwordPtr + passwordLength] = 0;

  // Allocate output pointer
  const outBufferPtr = _malloc(4);  // 32-bit
  const outBufferSizePtr = _malloc(4);

  try {
    // Call the WASM function
    wasmBlockDecryptBuffer(
      cipherPtr,
      cipherData.length,
      passwordPtr,
      passwordLength,
      outBufferPtr,
      outBufferSizePtr,
      verbose ? 1 : 0
    );

    // Grab the result
    const decryptedPtr = HEAPU32[outBufferPtr >> 2];
    const decryptedSize = HEAPU32[outBufferSizePtr >> 2];

    if (!decryptedPtr || !decryptedSize) {
      throw new Error("Block decryption returned empty buffer.");
    }

    // Own the result before releasing its WASM allocation. The three-argument
    // Buffer.from overload creates a view into the heap rather than a copy.
    const decryptedData = Buffer.from(
      HEAPU8.subarray(decryptedPtr, decryptedPtr + decryptedSize)
    );

    // Free the result buffer
    wasmFreeBuffer(decryptedPtr);

    return decryptedData;
  } finally {
    // Clean up
    _free(cipherPtr);
    _free(passwordPtr);
    _free(outBufferPtr);
    _free(outBufferSizePtr);
  }
}

export async function encrypt({data, key} = {}) {
  if ( ! data || ! key ) {
    throw new TypeError(`Both data and key must be provided`);
  }
  return blockEncryptBuffer(
    data, key,
    'rainstorm', 'scatter', 512, 9, 9,
    0n, '', 512, false, false
  );
}

export async function decrypt({data, key, verbose = false} = {}) {
  if ( ! data || ! key ) {
    throw new TypeError(`Both data and key must be provided`);
  }
  return blockDecryptBuffer(data, key, verbose);
}


/**
 * Loads the WASM module and wraps the necessary functions.
 */
async function loadRain() {
  let resolve;
  const pr = new Promise(res => resolve = res);
  import('./../wasm/rain.cjs').then(async x => {
    await untilTrue(() => {
      return !!x?.default?.wasmExports?.memory;
    });
    rain = x.default;
    rain.loaded = true;

    // Note: HEAPU8, getValue, etc. should already be properties of the Module object
    // after WASM initialization. The Emscripten-generated code makes them available.

    const { cwrap } = rain;

    // Wrap rainstormHash functions
    rain.rainstormHash64 = cwrap('rainstormHash64', null, ['number', 'number', 'bigint', 'number']);
    rain.rainstormHash128 = cwrap('rainstormHash128', null, ['number', 'number', 'bigint', 'number']);
    rain.rainstormHash256 = cwrap('rainstormHash256', null, ['number', 'number', 'bigint', 'number']);
    rain.rainstormHash512 = cwrap('rainstormHash512', null, ['number', 'number', 'bigint', 'number']);

    // Wrap rainbowHash functions
    rain.rainbowHash64 = cwrap('rainbowHash64', null, ['number', 'number', 'bigint', 'number']);
    rain.rainbowHash128 = cwrap('rainbowHash128', null, ['number', 'number', 'bigint', 'number']);
    rain.rainbowHash256 = cwrap('rainbowHash256', null, ['number', 'number', 'bigint', 'number']);

    // Wrap WASM header info functions
    rain.wasmGetFileHeaderInfo = cwrap('wasmGetFileHeaderInfo', 'number', ['number', 'number']);
    rain.wasmFree = cwrap('wasmFree', null, ['number']);

    // Wrap buffer-based encryption/decryption functions with updated signatures
    // Note: Update the argument types to include the new errorPtr parameter
    rain.wasmStreamEncryptBuffer = cwrap('wasmStreamEncryptBuffer', null, [
      'number', 'number', 'number', 'number', 'number', 'number',
      'number', 'number', 'number', 'number',
      'number', 'number'
    ]);
    rain.wasmStreamDecryptBuffer = cwrap('wasmStreamDecryptBuffer', null, [
      'number', 'number', 'number', 'number',
      'number', 'number', 'number', 'number'
    ]);

    // Inside loadRain(), once the wasm is loaded:
    rain.wasmBlockEncryptBuffer = cwrap('wasmBlockEncryptBuffer', 'number', [
      'number', 'number', 'number', 'number', 'string', 'string', 
      'number', 'number', 'number', 'number', 'number', 'number',
      'number', 'number', 'number'
    ]);
    rain.wasmBlockDecryptBuffer = cwrap('wasmBlockDecryptBuffer', null, [
      'number','number','number','number','number','number', 'number'
    ]);
 
    rain.wasmFreeBuffer = cwrap('wasmFreeBuffer', null, ['number']);

    // Wrap the new wasmFreeString function
    rain.wasmFreeString = cwrap('wasmFreeString', null, ['number']);

    const toUint8Array = (data) => {
        const buffer = new Uint8Array(data.length);
        for (let i = 0; i < data.length; i++) buffer[i] = data[i];
        return buffer;
    };

    const fromUint8Array = (buffer) => String.fromCharCode.apply(null, buffer);

    // plaintext and key must be buffers (NOT strings otherwise lengths will not reflect bytes but codepoints)
    const encryptData = async ({plainText, key, algorithm, searchMode, hashBits, seed, salt, blockSize, nonceSize, outputExtension, deterministicNonce, verbose}) => {
      if (!rain.loaded) {
        await loadRain();
      }
        const dataPtr = rain._malloc(plainText.length);
        rain.HEAPU8.set(plainText, dataPtr);

        const keyPtr = rain._malloc(key.length);
        rain.HEAPU8.set(key, keyPtr);

        const saltPtr = rain._malloc(salt.length);
        rain.HEAPU8.set(salt, saltPtr);

        let outLenPtr;
        let resultPtr;
        try { 
          outLenPtr = rain._malloc(4); // Allocate space for size_t (4 bytes)
          resultPtr = rain.wasmBlockEncryptBuffer(dataPtr, plainText.length, keyPtr, key.length, algorithm, searchMode, hashBits, seed, saltPtr, salt.length, blockSize, nonceSize, outputExtension, deterministicNonce ? 1 : 0, verbose ? 1 : 0, outLenPtr);
        } catch(e) {
          console.warn(`Wasm err`, e);
        }

        const resultLen = rain.HEAPU32[outLenPtr >> 2]; // Read size_t value
        // Own the result before releasing its WASM allocation. Callers may
        // invoke more WASM work while retaining this ciphertext.
        const encrypted = Buffer.from(
          rain.HEAPU8.subarray(resultPtr, resultPtr + resultLen)
        );

        rain.wasmFreeBuffer(resultPtr);

        rain._free(dataPtr);
        rain._free(keyPtr);
        rain._free(saltPtr);
        rain._free(outLenPtr);

        return encrypted;
    };

    rain.encryptData = encryptData;

    resolve();
  }).catch(err => {
    console.error('Failed to load WASM module:', err);
    process.exit(1);
  });
  return pr;
}

/**
 * Utility function to wait until a condition is true, polling periodically.
 * @param {Function} pred - The predicate function to evaluate.
 * @param {number} MAX - Maximum number of attempts.
 * @param {number} MS_BETWEEN - Milliseconds between attempts.
 */
async function untilTrue(pred, MAX = 1000, MS_BETWEEN = 50) {
  let resolve, reject, abort = false;
  const oPred = pred;
  pred = async () => {
    try {
      return await oPred();
    } catch (e) {
      console.log(`untilTrue predicate errored: ${e}`, oPred, e);
      reject();
      abort = true;
    }
  };
  const pr = new Promise((res, rej) => (resolve = res, reject = () => {
    rej();
    abort = true;
  }));
  if (await pred()) {
    return resolve();
  }
  setTimeout(async () => {
    let tries = 0;
    while (tries++ < MAX) {
      await sleep(MS_BETWEEN);
      if (await pred()) {
        return resolve();
      }
      if (abort) break;
    }
    return reject();
  }, 0);
  return pr;
}

/**
 * Sleeps for a given number of milliseconds.
 * @param {number} ms - Milliseconds to sleep.
 */
async function sleep(ms) {
  let resolve;
  const pr = new Promise(res => resolve = res);
  setTimeout(resolve, ms);
  return pr;
}


