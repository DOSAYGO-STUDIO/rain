// wasm_exports.cpp

#ifdef _OPENMP
#include <omp.h>
#endif

#ifdef __EMSCRIPTEN__
#include <emscripten.h>
#include <cstdlib>   // for malloc/free
#include <cstring>   // for memcpy
#include <vector>
#include <string>
#include <sstream>
#include <stdexcept>
#include <iostream>
#include "../tool.h"         // for invokeHash, etc.
#include "../file-header.h"  // for FileHeader serialization/deserialization
#include "../block-cipher.h"
#include "../stream-cipher.h"


/**
 * Utility function to deserialize a buffer from WASM memory.
 * Returns a std::vector<uint8_t> containing the data.
 */
std::vector<uint8_t> deserializeBuffer(const uint8_t* data, size_t size) {
    return std::vector<uint8_t>(data, data + size);
}

extern "C" {

  // -------------------------------------------------------------------
  // Hash Functions
  // -------------------------------------------------------------------
  KEEPALIVE void rainstormHash64(const void* in, const size_t len, const seed_t seed, void* out) {
      rainstorm::rainstorm<64, false>(in, len, seed, out);
  }

  KEEPALIVE void rainstormHash128(const void* in, const size_t len, const seed_t seed, void* out) {
      rainstorm::rainstorm<128, false>(in, len, seed, out);
  }

  KEEPALIVE void rainstormHash256(const void* in, const size_t len, const seed_t seed, void* out) {
      rainstorm::rainstorm<256, false>(in, len, seed, out);
  }

  KEEPALIVE void rainstormHash512(const void* in, const size_t len, const seed_t seed, void* out) {
      rainstorm::rainstorm<512, false>(in, len, seed, out);
  }

  KEEPALIVE void rainbowHash64(const void* in, const size_t len, const seed_t seed, void* out) {
      rainbow::rainbow<64, false>(in, len, seed, out);
  }

  KEEPALIVE void rainbowHash128(const void* in, const size_t len, const seed_t seed, void* out) {
      rainbow::rainbow<128, false>(in, len, seed, out);
  }

  KEEPALIVE void rainbowHash256(const void* in, const size_t len, const seed_t seed, void* out) {
      rainbow::rainbow<256, false>(in, len, seed, out);
  }

  KEEPALIVE void rainbow2Hash64(const void* in, const size_t len, const seed_t seed, void* out) {
      rainbow2::rainbow2<64, false>(in, len, seed, out);
  }

  KEEPALIVE void rainbow2Hash128(const void* in, const size_t len, const seed_t seed, void* out) {
      rainbow2::rainbow2<128, false>(in, len, seed, out);
  }

  KEEPALIVE void rainbow2Hash256(const void* in, const size_t len, const seed_t seed, void* out) {
      rainbow2::rainbow2<256, false>(in, len, seed, out);
  }

  // -------------------------------------------------------------------
  // WASM Memory Management Utilities
  // -------------------------------------------------------------------

  /**
   * Utility function to serialize a buffer into a WASM-allocated memory block.
   * Returns the pointer to the serialized buffer.
   */
  uint8_t* serializeBuffer(const std::vector<uint8_t>& buffer, size_t& outSize) {
      outSize = buffer.size();
      uint8_t* wasmBuffer = (uint8_t*)malloc(outSize);
      if (!wasmBuffer) {
          throw std::runtime_error("Memory allocation failed in serializeBuffer.");
      }
      std::memcpy(wasmBuffer, buffer.data(), outSize);
      return wasmBuffer;
  }

  // -------------------------------------------------------------------
  // WASM Export: wasmGetFileHeaderInfo
  // Description: Parse a file header from a buffer in WASM memory and return a JSON-like string.
  // -------------------------------------------------------------------
  EMSCRIPTEN_KEEPALIVE
  char* wasmGetFileHeaderInfo(const uint8_t* data, size_t size) {
      try {
          // Deserialize input buffer
          std::vector<uint8_t> buffer(data, data + size);

          // Parse the header using readFileHeader
          std::istringstream inStream(std::string(buffer.begin(), buffer.end()), std::ios::binary);
          FileHeader hdr = readFileHeader(inStream);

          // Construct JSON-like string
          std::stringstream ss;
          ss << "{";
          ss << "\"magic\":\"0x" << std::hex << hdr.magic << "\",";
          ss << "\"version\":" << std::dec << static_cast<int>(hdr.version) << ",";
          ss << "\"cipherMode\":\"0x" << std::hex << static_cast<int>(hdr.cipherMode) << "\",";
          ss << "\"blockSize\":" << std::dec << hdr.blockSize << ",";
          ss << "\"nonceSize\":" << hdr.nonceSize << ",";
          ss << "\"hashSizeBits\":" << hdr.hashSizeBits << ",";
          ss << "\"outputExtension\":" << hdr.outputExtension << ",";
          ss << "\"hashName\":\"" << hdr.hashName << "\",";
          ss << "\"iv\":\"0x" << std::hex << hdr.iv << "\",";
          ss << "\"saltLen\":" << std::dec << static_cast<int>(hdr.saltLen) << ",";
          ss << "\"salt\":\"";
          for (auto b : hdr.salt) {
              ss << std::setw(2) << std::setfill('0') << std::hex << static_cast<int>(b);
          }
          ss << "\",";
          ss << "\"searchModeEnum\":\"0x" << std::hex << static_cast<int>(hdr.searchModeEnum) << "\",";
          ss << "\"originalSize\":" << std::dec << hdr.originalSize << ",";
          ss << "\"hmac\":\"";
          for (auto b : hdr.hmac) {
              ss << std::setw(2) << std::setfill('0') << std::hex << static_cast<int>(b);
          }
          ss << "\"";
          ss << "}";

          std::string result = ss.str();

          // Allocate memory for the output string
          char* output = (char*)malloc(result.size() + 1);
          if (!output) {
              throw std::runtime_error("Memory allocation failed in wasmGetFileHeaderInfo.");
          }
          std::memcpy(output, result.c_str(), result.size() + 1);
          return output;
      }
      catch (const std::exception &e) {
          // Return an error string. Caller must free this memory.
          std::string err = "{\"error\":\"" + std::string(e.what()) + "\"}";
          char* output = (char*)malloc(err.size() + 1);
          if (!output) {
              return nullptr; // Allocation failed
          }
          std::memcpy(output, err.c_str(), err.size() + 1);
          return output;
      }
  }

  /**
   * Utility function so JS can free the char* or buffers returned by
   * wasmGetFileHeaderInfo (or any other WASM-allocated pointers).
   */
  EMSCRIPTEN_KEEPALIVE
  void wasmFree(void* ptr) {
      free(ptr);
  }

  /**
   * Utility function to free a string allocated by WASM.
   */
  EMSCRIPTEN_KEEPALIVE
  void wasmFreeString(char* strPtr) {
      free(strPtr);
  }

  /**
   * Utility function to free a buffer allocated by WASM.
   */
  EMSCRIPTEN_KEEPALIVE
  void wasmFreeBuffer(uint8_t* bufferPtr) {
      free(bufferPtr);
  }

  // -------------------------------------------------------------------
  // WASM Export: wasmStreamEncryptBuffer
  // Description: Buffer-based stream encryption for WASM.
  // -------------------------------------------------------------------
  EMSCRIPTEN_KEEPALIVE
  void wasmStreamEncryptBuffer(
      const uint8_t* inBufferPtr,
      size_t inBufferSize,
      const char* keyPtr,
      size_t keyLength,
      const char* algorithmPtr,
      size_t algorithmLength,
      uint32_t hashBits,
      uint64_t seed,
      const uint8_t* saltPtr,
      size_t saltLen,
      uint32_t outputExtension,
      int verbose,
      uint8_t** outBufferPtr,
      size_t* outBufferSizePtr
  ) {
      try {
          // Deserialize input buffer
          std::vector<uint8_t> plainData = deserializeBuffer(inBufferPtr, inBufferSize);

          // Convert C strings to std::string
          std::vector<uint8_t> key(keyPtr, keyPtr + keyLength);
          std::string algorithm(algorithmPtr, algorithmLength);

          // Convert salt to std::vector<uint8_t>
          std::vector<uint8_t> salt(saltPtr, saltPtr + saltLen);

          // Determine HashAlgorithm enum
          HashAlgorithm algot;
          if (algorithm == "rainbow") {
              algot = HashAlgorithm::Rainbow;
          }
          else if (algorithm == "rainstorm") {
              algot = HashAlgorithm::Rainstorm;
          }
          else {
              throw std::runtime_error("Unsupported algorithm: " + algorithm);
          }

          // Call the buffer-based encryption function
          std::vector<uint8_t> encryptedBuffer = streamEncryptBuffer(
              plainData,
              key,
              algot,
              hashBits,          // hash_size
              seed,              // seed (IV)
              salt,              // salt
              outputExtension,   // outputExtension
              verbose != 0       // verbose
          );

          // Serialize the output buffer
          size_t encryptedSize;
          uint8_t* encryptedPtr = serializeBuffer(encryptedBuffer, encryptedSize);

          // Set output pointers
          *outBufferPtr = encryptedPtr;
          *outBufferSizePtr = encryptedSize;
      }
      catch (const std::exception& e) {
          // In case of error, set output pointers to nullptr and size to 0
          *outBufferPtr = nullptr;
          *outBufferSizePtr = 0;
          // Optionally, log the error to stderr
          fprintf(stderr, "Error in wasmStreamEncryptBuffer: %s\n", e.what());
      }
  }

  // -------------------------------------------------------------------
  // WASM Export: wasmStreamDecryptBuffer
  // Description: Buffer-based stream decryption for WASM.
  // -------------------------------------------------------------------
  EMSCRIPTEN_KEEPALIVE
  void wasmStreamDecryptBuffer(
      const uint8_t* inBufferPtr,
      size_t inBufferSize,
      const char* keyPtr,
      size_t keyLength,
      int verbose,
      uint8_t** outBufferPtr,
      size_t* outBufferSizePtr,
      char** errorPtr // New parameter for error messages
  ) {
      try {
          // Deserialize input buffer
          std::vector<uint8_t> encryptedData = deserializeBuffer(inBufferPtr, inBufferSize);

          // Convert C string to std::vector<uint8_t>
          std::vector<uint8_t> key(keyPtr, keyPtr + keyLength);

          // Call the buffer-based decryption function
          std::vector<uint8_t> decryptedBuffer = streamDecryptBuffer(
              encryptedData,
              key,
              verbose != 0
          );

          // Serialize the output buffer
          size_t decryptedSize;
          uint8_t* decryptedPtr = serializeBuffer(decryptedBuffer, decryptedSize);

          // Set output pointers
          *outBufferPtr = decryptedPtr;
          *outBufferSizePtr = decryptedSize;

          // Indicate no error
          *errorPtr = nullptr;
      }
      catch (const std::exception& e) {
          // In case of error, set output pointers to nullptr and size to 0
          *outBufferPtr = nullptr;
          *outBufferSizePtr = 0;

          // Allocate memory for the error message
          std::string errMsg = std::string("{\"error\":\"") + e.what() + "\"}";
          size_t errLen = errMsg.length();
          char* errCStr = (char*)malloc(errLen + 1);
          if (errCStr) {
              std::memcpy(errCStr, errMsg.c_str(), errLen);
              errCStr[errLen] = '\0'; // Null-terminate
              *errorPtr = errCStr;
          }
          else {
              *errorPtr = nullptr; // Allocation failed
          }

          // Optionally, log the error to stderr
          fprintf(stderr, "Error in wasmStreamDecryptBuffer: %s\n", e.what());
      }
  }

  // -------------------------------------------------------------------
  // WASM Export: wasmBlockEncryptBuffer
  // Description: Buffer-based block encryption for WASM.
  // -------------------------------------------------------------------
  EMSCRIPTEN_KEEPALIVE
  uint8_t* wasmBlockEncryptBuffer(
      const uint8_t* data, size_t data_len,
      const char* keyPtr,
      size_t keyLength,
      const char* algorithm,
      const char* searchMode,
      uint32_t hashBits,
      uint64_t seed,
      uint8_t* saltPtr,
      size_t saltLen,
      size_t blockSize,
      size_t nonceSize,
      uint32_t outputExtension,
      int deterministicNonce,
      int verbose,
      size_t* out_len
  ) {
      try {
          // Prepare input data
          std::vector<uint8_t> plainData(data, data + data_len);
          std::vector<uint8_t> key(keyPtr, keyPtr + keyLength);
          std::string algorithmStr(algorithm, strlen(algorithm));
          std::string searchModeStr(searchMode, strlen(searchMode));
          std::vector<uint8_t> salt(saltPtr, saltPtr + saltLen);

          // Determine HashAlgorithm enum
          HashAlgorithm algot;
          if (algorithmStr == "rainbow") {
              algot = HashAlgorithm::Rainbow;
          }
          else if (algorithmStr == "rainstorm") {
              algot = HashAlgorithm::Rainstorm;
          }
          else {
              throw std::runtime_error("Unsupported algorithm: " + algorithmStr);
          }

          // Call the buffer-based encryption function
          std::vector<uint8_t> encryptedBuffer = puzzleEncryptBufferWithHeader(
              plainData,
              key,
              algot,
              hashBits,          // hash_size
              seed,              // seed (IV)
              salt,              // salt
              static_cast<uint16_t>(blockSize),     // blockSize
              static_cast<uint16_t>(nonceSize),     // nonceSize
              searchModeStr,     // searchMode
              verbose == 1,      // verbose
              deterministicNonce == 1,  // deterministicNonce
              static_cast<uint16_t>(outputExtension)    // outputExtension
          );

          // Serialize the output buffer
          size_t encryptedSize;
          uint8_t* encryptedPtr = serializeBuffer(encryptedBuffer, encryptedSize);

          // Set output pointer
          *out_len = encryptedSize;
          return encryptedPtr;
      }
      catch (const std::exception &e) {
          fprintf(stderr, "wasmBlockEncryptBuffer error: %s\n", e.what());
          *out_len = 0;
          return nullptr;
      }
  }

  // -------------------------------------------------------------------
  // WASM Export: wasmBlockDecryptBuffer
  // Description: Buffer-based block decryption for WASM.
  // -------------------------------------------------------------------
  EMSCRIPTEN_KEEPALIVE
  void wasmBlockDecryptBuffer(
      const uint8_t* inBufferPtr,
      size_t inBufferSize,
      const char* keyPtr,
      size_t keyLength,
      uint8_t** outBufferPtr,
      size_t* outBufferSizePtr,
      int verbose
  ) {
      try {
          if (verbose == 1) {
            fprintf(stderr, "Verbose ? %d\n", verbose);
            fprintf(stderr, "Input Buffer Pointer: %p\n", (const void*)inBufferPtr);
            fprintf(stderr, "Input Buffer Size: %zu\n", inBufferSize);
            fprintf(stderr, "Key Pointer: %p\n", (const void*)keyPtr);
            fprintf(stderr, "Key Length: %zu\n", keyLength);
            fprintf(stderr, "Output Buffer Pointer: %p\n", (void*)outBufferPtr);
            fprintf(stderr, "Output Buffer Size Pointer: %p\n", (void*)outBufferSizePtr);
          }

          // Deserialize input buffer
          std::vector<uint8_t> cipherData = deserializeBuffer(inBufferPtr, inBufferSize);
          std::vector<uint8_t> key(keyPtr, keyPtr + keyLength);

          // Call the buffer-based decryption function
          std::vector<uint8_t> decryptedData = puzzleDecryptBufferWithHeader(cipherData, key);

          // Serialize output
          size_t decryptedSize;
          uint8_t* decryptedPtr = serializeBuffer(decryptedData, decryptedSize);

          // Set output pointers
          *outBufferPtr = decryptedPtr;
          *outBufferSizePtr = decryptedSize;
      }
      catch (const std::exception &e) {
          fprintf(stderr, "wasmBlockDecryptBuffer error: %s\n", e.what());
          *outBufferPtr = nullptr;
          *outBufferSizePtr = 0;
      }
  }

  /**
     * wasmSerializeHeader
     *
     * Reads a FileHeader from a buffer (using readFileHeader), zeros the HMAC field,
     * then serializes the header (using serializeFileHeader) and returns a pointer to the
     * new header buffer along with its size (via outHeaderSize).
     *
     * The header returned will have a zeroed HMAC. The JS side can then use this header along
     * with the rest of the encrypted data (ciphertext) and the key to compute the new HMAC.
     *
     * Parameters:
     *   data         - Pointer to the beginning of the encrypted file data.
     *   size         - Total size of the encrypted file data.
     *   outHeaderSize - Pointer to a size_t where the size of the serialized header will be stored.
     *
     * Returns:
     *   A pointer to the allocated header buffer (which must be freed later via wasmFreeBuffer or similar)
     *   or nullptr on error.
   */
  EMSCRIPTEN_KEEPALIVE
  uint8_t* wasmSerializeHeader(const uint8_t* data, size_t size, size_t* outHeaderSize) {
      try {
          // Create a string from the incoming buffer (this is a simple way to wrap it in an istream)
          std::string inStr(reinterpret_cast<const char*>(data), size);
          std::istringstream inStream(inStr, std::ios::binary);

          // Use readFileHeader to parse the FileHeader from the input stream.
          FileHeader hdr = readFileHeader(inStream);

          // Zero out the HMAC field in the header.
          std::fill(hdr.hmac.begin(), hdr.hmac.end(), 0x00);

          // Serialize the header to a contiguous byte vector.
          std::vector<uint8_t> ser = serializeFileHeader(hdr);

          // Allocate space to return the serialized header.
          *outHeaderSize = ser.size();
          uint8_t* buffer = (uint8_t*)malloc(ser.size());
          if (!buffer) {
              throw std::runtime_error("Memory allocation failed in wasmSerializeHeader.");
          }
          std::memcpy(buffer, ser.data(), ser.size());
          return buffer;
      } catch (const std::exception& e) {
          fprintf(stderr, "wasmSerializeHeader error: %s\n", e.what());
          *outHeaderSize = 0;
          return nullptr;
      }
  }

  /**
     * wasmWriteHMACToBuffer
     *
     * Overwrites the HMAC field in a serialized header held in memory.
     *
     * It assumes that the header has the PackedHeader structure at the very beginning,
     * where the HMAC field is located at a fixed offset (33 bytes into the header).
     *
     * Parameters:
     *   buffer    - Pointer to the serialized header in memory.
     *   bufferSize- Size of the header buffer (must be at least 33 + 32 bytes).
     *   newHMAC   - Pointer to a 32-byte buffer containing the new HMAC value.
     *
     * Returns:
     *   0 on success; nonzero if an error occurs.
   */
  EMSCRIPTEN_KEEPALIVE
  int wasmWriteHMACToBuffer(uint8_t* buffer, size_t bufferSize, const uint8_t* newHMAC) {
      try {
          // According to PackedHeader layout:
          // magic(4) + version(1) + cipherMode(1) + blockSize(2) +
          // nonceSize(2) + hashSizeBits(2) + outputExtension(2) +
          // hashNameLen(1) + iv(8) + saltLen(1) + searchModeEnum(1) + originalSize(8)
          // = 33 bytes before the HMAC field.
          const size_t hmac_offset = 33;
          const size_t HMAC_SIZE = 32;
          if (bufferSize < hmac_offset + HMAC_SIZE) {
              throw std::runtime_error("Buffer size too small in wasmWriteHMACToBuffer.");
          }
          std::memcpy(buffer + hmac_offset, newHMAC, HMAC_SIZE);
          return 0; // success
      } catch (const std::exception& e) {
          fprintf(stderr, "wasmWriteHMACToBuffer error: %s\n", e.what());
          return -1;
      }
  }


  EMSCRIPTEN_KEEPALIVE
  uint8_t* wasmCreateHMAC(
      const uint8_t* headerDataPtr,
      size_t headerDataLen,
      const uint8_t* ciphertextPtr,
      size_t ciphertextLen,
      const uint8_t* keyPtr,
      size_t keyLen,
      size_t* outHMACLen
  ) {
      try {
          // Deserialize input buffers
          std::vector<uint8_t> headerData(headerDataPtr, headerDataPtr + headerDataLen);
          std::vector<uint8_t> ciphertext(ciphertextPtr, ciphertextPtr + ciphertextLen);
          std::vector<uint8_t> key(keyPtr, keyPtr + keyLen);

          // Compute HMAC
          auto hmac = createHMAC(headerData, ciphertext, key);

          // Serialize output
          *outHMACLen = hmac.size();
          uint8_t* hmacPtr = (uint8_t*)malloc(hmac.size());
          if (!hmacPtr) {
              throw std::runtime_error("Memory allocation failed for HMAC output.");
          }
          std::memcpy(hmacPtr, hmac.data(), hmac.size());
          return hmacPtr;
      } catch (const std::exception& e) {
          fprintf(stderr, "Error in wasmCreateHMAC: %s\n", e.what());
          *outHMACLen = 0;
          return nullptr;
      }
  }

  EMSCRIPTEN_KEEPALIVE
  bool wasmVerifyHMAC(
      const uint8_t* headerDataPtr,
      size_t headerDataLen,
      const uint8_t* ciphertextPtr,
      size_t ciphertextLen,
      const uint8_t* keyPtr,
      size_t keyLen,
      const uint8_t* hmacToCheckPtr,
      size_t hmacToCheckLen
  ) {
      try {
          // Deserialize input buffers
          std::vector<uint8_t> headerData(headerDataPtr, headerDataPtr + headerDataLen);
          std::vector<uint8_t> ciphertext(ciphertextPtr, ciphertextPtr + ciphertextLen);
          std::vector<uint8_t> key(keyPtr, keyPtr + keyLen);
          std::vector<uint8_t> hmacToCheck(hmacToCheckPtr, hmacToCheckPtr + hmacToCheckLen);

          // Verify HMAC
          return verifyHMAC(headerData, ciphertext, key, hmacToCheck);
      } catch (const std::exception& e) {
          fprintf(stderr, "Error in wasmVerifyHMAC: %s\n", e.what());
          return false;
      }
  }

} // extern "C"


#endif // __EMSCRIPTEN__

