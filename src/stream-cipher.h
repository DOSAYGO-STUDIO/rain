#pragma once

#include "file-header.h"
#include "common.h"
#include "tool.h" // for compressData, decompressData, derivePRK, extendOutputKDF, etc.

/**
 * @brief Buffer-based stream encryption. Produces a buffer containing:
 *        1) FileHeader (serialized)
 *        2) XOR'd (compressed) plaintext
 *
 * @param plainData       The *already compressed* plaintext bytes to encrypt
 * @param key             User password/IKM
 * @param algot           HashAlgorithm for PRK derivation (rainbow or rainstorm)
 * @param hash_bits       Hash size in bits
 * @param seed            64-bit seed (used as IV in the header)
 * @param salt            Additional salt
 * @param outputExtension Extra bytes of keystream offset
 * @param verbose         Whether to print debugging info
 * @return std::vector<uint8_t>  The final output: [FileHeader bytes][XOR'd bytes]
 */
static std::vector<uint8_t> streamEncryptBuffer(
  const std::vector<uint8_t> &plainData,
  std::vector<uint8_t> &key,
  HashAlgorithm algot,
  uint32_t hash_bits,
  uint64_t seed,
  const std::vector<uint8_t> &salt,
  uint32_t outputExtension,
  bool verbose
) {
  // 2) Compress the plaintext
  auto compressed = compressData(plainData);

  // 1) Prepare the FileHeader in memory
  FileHeader hdr{};
  hdr.magic          = MagicNumber;
  hdr.version        = 0x02;        // Example version
  hdr.cipherMode     = 0x10;        // Stream Cipher
  hdr.blockSize      = 0;           // Not used in stream cipher
  hdr.nonceSize      = 0;           // Not used in stream cipher
  hdr.outputExtension= outputExtension;
  hdr.hashSizeBits   = hash_bits;
  hdr.hashName       = (algot == HashAlgorithm::Rainbow) ? "rainbow" : "rainstorm";
  hdr.iv             = seed;        // seed as IV
  hdr.saltLen        = static_cast<uint8_t>(salt.size());
  hdr.salt           = salt;
  hdr.originalSize   = compressed.size();

  // 2) Serialize header to a buffer
  std::vector<uint8_t> headerBytes = serializeFileHeader(hdr);

  // 3) Derive PRK
  std::vector<uint8_t> seed_vec(8);
  for (size_t i = 0; i < 8; ++i) {
    seed_vec[i] = static_cast<uint8_t>((seed >> (i * 8)) & 0xFF);
  }
  std::vector<uint8_t> ikm(key.begin(), key.end());
  std::vector<uint8_t> prk = derivePRK(seed_vec, salt, ikm, algot, hash_bits, verbose);

  // 4) Generate Keystream
  size_t needed   = compressed.size() + outputExtension;
  auto keystream  = extendOutputKDF(prk, needed, algot, hash_bits);

  if (verbose) {
    std::cerr << "\n[BufferEnc] headerBytes.size(): " << headerBytes.size() << "\n";
    std::cerr << "[BufferEnc] plaintext size: " << compressed.size() << "\n";
    std::cerr << "[BufferEnc] needed (with extension): " << needed << "\n";
    std::cerr << "[BufferEnc] keystream.size(): " << keystream.size() << "\n";
  }

  // 5) Allocate final output buffer = [header][ciphertext]
  std::vector<uint8_t> output;
  output.reserve(headerBytes.size() + compressed.size());

  // 6) Append header
  output.insert(output.end(), headerBytes.begin(), headerBytes.end());

  // 7) XOR plaintext with keystream (skipping first outputExtension bytes)
  std::vector<uint8_t> cipherData(compressed);
  for (size_t i = 0; i < cipherData.size(); ++i) {
    cipherData[i] ^= keystream[i + outputExtension];
  }

  // 8) Append the XOR'd data
  output.insert(output.end(), cipherData.begin(), cipherData.end());

  return output;
}

static std::vector<uint8_t> streamDecryptBuffer(
  const std::vector<uint8_t> &input,
  std::vector<uint8_t> &key,
  bool verbose
) {
  // 1) Confirm we have enough data for at least the size of FileHeader in memory
  if (input.size() < sizeof(FileHeader)) {
    throw std::runtime_error("[BufferDec] Input too small to contain a FileHeader");
  }

  // Create a memory stream from the input buffer
  std::istringstream memStream(
    std::string(reinterpret_cast<const char*>(input.data()), input.size()),
    std::ios::binary
  );

  // Debug: Check the stream state
  if (verbose) {
    std::cerr << "[DEBUG] memStream state good? " << memStream.good() << "\n";
    std::cerr << "[DEBUG] memStream.tellg(): " << memStream.tellg() << "\n";
  }

  // 3) Read the FileHeader
  FileHeader hdr = readFileHeader(memStream);

  // Check the magic
  if (hdr.magic != MagicNumber) {
    throw std::runtime_error("[BufferDec] Invalid magic number in header");
  }
  if (hdr.cipherMode != 0x10) {
    throw std::runtime_error("[BufferDec] Not a stream cipher file");
  }

  if (verbose) {
    std::cerr << "\n[BufferDec] parse header done. cipherMode=0x" 
              << std::hex << (int)hdr.cipherMode << std::dec << "\n";
    std::cerr << "[BufferDec] originalSize: " << hdr.originalSize << "\n";
  }

  // 4) The remainder after the header is the ciphertext
  size_t headerSize = static_cast<size_t>(memStream.tellg());
  size_t cipherSize = input.size() - headerSize;
  if (cipherSize == 0) {
    throw std::runtime_error("[BufferDec] No ciphertext data found");
  }

  std::vector<uint8_t> cipherData(input.begin() + headerSize, input.end());

  // 3) Derive PRK
  HashAlgorithm algot = HashAlgorithm::Unknown;
  if (hdr.hashName == "rainbow") {
    algot = HashAlgorithm::Rainbow;
  } else if (hdr.hashName == "rainstorm") {
    algot = HashAlgorithm::Rainstorm;
  } else {
    throw std::runtime_error("[BufferDec] Unsupported hashName: " + hdr.hashName);
  }

  std::vector<uint8_t> seed_vec(8);
  for (size_t i = 0; i < 8; ++i) {
    seed_vec[i] = static_cast<uint8_t>((hdr.iv >> (i * 8)) & 0xFF);
  }
  std::vector<uint8_t> ikm(key.begin(), key.end());
  std::vector<uint8_t> prk = derivePRK(seed_vec, hdr.salt, ikm, algot, hdr.hashSizeBits, verbose);

  // 4) Generate Keystream
  size_t needed = cipherData.size() + hdr.outputExtension;
  auto keystream = extendOutputKDF(prk, needed, algot, hdr.hashSizeBits);

  if (verbose) {
    std::cerr << "[BufferDec] cipherData.size(): " << cipherData.size() << "\n";
    std::cerr << "[BufferDec] needed with extension: " << needed << "\n";
    std::cerr << "[BufferDec] keystream.size(): " << keystream.size() << "\n";
  }

  // 5) XOR cipherData with keystream (skip extension bytes)
  for (size_t i = 0; i < cipherData.size(); ++i) {
    cipherData[i] ^= keystream[i + hdr.outputExtension];
  }

  // 6) Decompress
  auto decompressed = decompressData(cipherData);

  return decompressed;
}

/* ------------------------------------------------------------------
 *  The original file-based encryption function
 *  now uses the new buffer-based approach under the hood
 * ------------------------------------------------------------------ */
static void streamEncryptFileWithHeader(
    const std::string &inFilename,
    const std::string &outFilename,
    std::vector<uint8_t> &key,
    HashAlgorithm algot,
    uint32_t hash_bits,
    uint64_t seed, // Used as IV
    const std::vector<uint8_t> &salt,
    uint32_t outputExtension,
    bool verbose
) {
  // 1) Read input file
  std::ifstream fin(inFilename, std::ios::binary);
  if (!fin.is_open()) {
    throw std::runtime_error("[StreamEnc] Cannot open input file: " + inFilename);
  }
  std::vector<uint8_t> plainData((std::istreambuf_iterator<char>(fin)),
                                 (std::istreambuf_iterator<char>()));
  fin.close();

  // 3) Ask the new buffer-based function to create [header + XOR data]
  std::vector<uint8_t> finalBuffer = streamEncryptBuffer(
    plainData,
    key,
    algot,
    hash_bits,
    seed,
    salt,
    outputExtension,
    verbose
  );

  // 4) Write result to output file
  std::ofstream fout(outFilename, std::ios::binary);
  if (!fout.is_open()) {
    throw std::runtime_error("[StreamEnc] Cannot open output file: " + outFilename);
  }
  fout.write(reinterpret_cast<const char*>(finalBuffer.data()), finalBuffer.size());
  fout.close();
}

/* ------------------------------------------------------------------
 *  The original file-based decryption function
 *  also calls the new buffer-based approach
 * ------------------------------------------------------------------ */
static void streamDecryptFileWithHeader(
    const std::string &inFilename,
    const std::string &outFilename,
    std::vector<uint8_t> &key,
    bool verbose
) {
  // 1) Read the entire input (including header) from file
  std::ifstream fin(inFilename, std::ios::binary);
  if (!fin.is_open()) {
    throw std::runtime_error("[StreamDec] Cannot open input file: " + inFilename);
  }
  std::vector<uint8_t> fileData((std::istreambuf_iterator<char>(fin)),
                                (std::istreambuf_iterator<char>()));
  fin.close();

  // 2) Decrypt the buffer-based approach
  std::vector<uint8_t> plaintext = streamDecryptBuffer(fileData, key, verbose);

  // 3) Write plaintext to output file
  std::ofstream fout(outFilename, std::ios::binary);
  if (!fout.is_open()) {
    throw std::runtime_error("[StreamDec] Cannot open output file: " + outFilename);
  }
  fout.write(reinterpret_cast<const char*>(plaintext.data()), plaintext.size());
  fout.close();

  if (verbose) {
    std::cerr << "[StreamDec] Decrypted " << plaintext.size()
              << " bytes from " << inFilename
              << " to " << outFilename << "\n";
  }
}


