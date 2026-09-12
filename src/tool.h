#pragma once
#ifndef VERSION
#define VERSION "4.0.0"
#endif
#include <atomic> // for std::atomic
#include <iostream>
#include <array>
#include <fstream>
#include <vector>
#include <string>
#include <cstring>
#include <cstdint>
#include <cstdlib>
#include <ctime>
#include <chrono>
#include <random>
#include <sstream>
#include <iomanip>
#include <bitset>
#include <algorithm>
#include <stdexcept>
#include <memory>
#include <thread>
#include <iterator>
#include <zlib.h>
#include <stdexcept>

// only define USE_FILESYSTEM if it is supported and needed
#include <sys/stat.h>
#ifdef USE_FILESYSTEM
#include <filesystem>
#endif
#include <mutex>
static std::mutex cerr_mutex;

#include "random.h"
#include "rainbow.cpp"
#include "rainstorm.cpp"
#include "cxxopts.hpp"
#include "common.h"


// Magic number to identify your file format ('RCRY' in hex).
inline constexpr uint32_t MagicNumber = 0x59524352;

struct RandomConfig {
    static std::string entropyMode; // Default: "default"
};
std::string RandomConfig::entropyMode = "default"; // Default initialization

// Standard test vectors
  std::vector<std::string> test_vectors = {
    "",
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    "The quick brown fox jumps over the lazy dog",
    "The quick brown fox jumps over the lazy cog",
    "The quick brown fox jumps over the lazy dog.",
    "After the rainstorm comes the rainbow.",
    std::string(64, '@')
  };

// enums
  enum class Mode {
    Digest,
    Stream,
    BlockEnc,   
    StreamEnc,
    Dec,    
    Info
  };

  // Mining mode enum
  enum class MineMode {
    None,
    Chain,
    NonceInc,
    NonceRand
  };

  enum SearchMode {
    Prefix,
    Sequence, 
    Series,
    Scatter,
    MapScatter,
    ParaScatter
  };

  enum class HashAlgorithm {
    Rainbow,
    Rainstorm,
    Unknown
  };

// Prototypes
  // Add a forward declaration for our new function
  void usage();

  void hashBuffer(Mode mode, HashAlgorithm algot,
                  std::vector<uint8_t>& buffer, uint64_t seed,
                  uint64_t output_length, std::ostream& outstream,
                  uint32_t hash_size);

  void hashAnything(Mode mode, HashAlgorithm algot,
                    const std::string& inpath, std::ostream& outstream,
                    uint32_t size, bool use_test_vectors,
                    uint64_t seed, uint64_t output_length);

  std::string generate_filename(const std::string& filename);

  uint64_t hash_string_to_64_bit(const std::string& seed_str);

// stream helpers
  template <typename T>
  std::ostream& operator<<(std::ostream& os, const std::vector<T>& vec) {
    os << "[";
    for (size_t i = 0; i < vec.size(); ++i) {
      if (i > 0) os << ", ";
      os << vec[i];
    }
    os << "]";
    return os;
  }

  inline bool hasPrefix(const std::vector<uint8_t>& hash_output, const std::vector<uint8_t>& prefix_bytes) {
    if (prefix_bytes.size() > hash_output.size()) return false;
    return std::equal(prefix_bytes.begin(), prefix_bytes.end(), hash_output.begin());
  }

// Helper function to securely overwrite a file with zeros and then truncate it
  static void overwriteFileWithZeros(const std::string &filename) {
      if (!std::filesystem::exists(filename)) {
          return; // File does not exist; nothing to do
      }

      // Open the file in read-write binary mode
      std::fstream file(filename, std::ios::in | std::ios::out | std::ios::binary);
      if (!file.is_open()) {
          throw std::runtime_error("Cannot open existing file for overwriting: " + filename);
      }

      // Determine the size of the file
      file.seekg(0, std::ios::end);
      std::streampos fileSize = file.tellg();
      file.seekp(0, std::ios::beg);

      // Create a buffer of zeros
      const size_t bufferSize = 4096; // 4KB buffer
      std::vector<char> zeros(bufferSize, 0x00);

      std::streampos remaining = fileSize;
      while (remaining > 0) {
          size_t toWrite = static_cast<size_t>(std::min(static_cast<std::streampos>(bufferSize), remaining));
          file.write(zeros.data(), toWrite);
          if (!file) {
              throw std::runtime_error("Failed to write zeros to file: " + filename);
          }
          remaining -= toWrite;
      }

      file.close();

      // Truncate the file to zero size
      std::filesystem::resize_file(filename, 0);
  }

// For cxxopts: getFileSize usage
  uint64_t getFileSize(const std::string& filename) {
    struct stat st;
    if(stat(filename.c_str(), &st) != 0) {
      return 0; // You may want to handle this error differently
    }
    return st.st_size;
  }

#ifdef USE_FILESYSTEM
  std::string generate_filename(const std::string& filename) {
    std::filesystem::path p{filename};
    std::string new_filename;
    std::string timestamp = "-" + std::to_string(std::time(nullptr));

    if (std::filesystem::exists(p)) {
      new_filename = p.stem().string() + timestamp + p.extension().string();

      // Handle filename collision
      int counter = 1;
      while (std::filesystem::exists(new_filename)) {
        new_filename = p.stem().string() + timestamp + "-" + std::to_string(counter++)
                       + p.extension().string();
      }
    } else {
      new_filename = filename;
    }

    return new_filename;
  }
#else
  // If filesystem isn't available, just return the filename as is
  std::string generate_filename(const std::string& filename) {
    return filename;
  }
#endif

  uint64_t hash_string_to_64_bit(const std::string& seed_str) {
    std::vector<char> buffer(seed_str.begin(), seed_str.end());
    std::vector<uint8_t> hash_output(8); // 64 bits = 8 bytes
    // We'll use 64-bit rainstorm for string -> seed
    rainbow::rainbow<64, bswap>(buffer.data(), buffer.size(), 0, hash_output.data());
    uint64_t seed = 0;
    std::memcpy(&seed, hash_output.data(), 8);
    return seed;
  }

// mode helpers
  std::string modeToString(const Mode& mode) {
    switch(mode) {
      case Mode::Digest: return "Digest";
      case Mode::Stream: return "Stream";
      case Mode::BlockEnc:    return "BlockEnc";    // added
      case Mode::StreamEnc:    return "StreamEnc";    // added
      case Mode::Dec:    return "Dec";    // added
      case Mode::Info:   return "Info";
      default: throw std::runtime_error("Unknown hash mode");
    }
  }

  std::istream& operator>>(std::istream& in, Mode& mode) {
    std::string token;
    in >> token;
    if (token == "digest")      mode = Mode::Digest;
    else if (token == "stream") mode = Mode::Stream;
    else if (token == "block-enc")    mode = Mode::BlockEnc;   // added
    else if (token == "stream-enc")    mode = Mode::StreamEnc;   // added
    else if (token == "dec")    mode = Mode::Dec;   // added
    else if (token == "info")   mode = Mode::Info;
    else                       in.setstate(std::ios_base::failbit);
    return in;
  }

  std::string mineModeToString(const MineMode& mode) {
    switch(mode) {
      case MineMode::None:          return "None";
      case MineMode::Chain:         return "Chain";
      case MineMode::NonceInc:      return "NonceInc";    // added
      case MineMode::NonceRand:     return "NonceRand";    // added
      default: throw std::runtime_error("Unknown mine mode");
    }
  }

// HMAC
  //
  // Note (2026-09-12, external review): despite the name, this is not HMAC.
  // It is the secret-suffix construction H(message || key): no ipad/opad, no
  // keyed compression, and so none of HMAC's proof carries over. Two specific
  // breaks were checked and did NOT apply here, so this is a provenance and
  // naming concern rather than a known vulnerability:
  //
  //   - Field-boundary ambiguity. The concatenation encodes no lengths, but
  //     PackedHeader carries explicit hashNameLen/saltLen and the ciphertext
  //     length is pinned by originalSize, so in practice the split is not
  //     malleable.
  //   - Length extension. Only 256 of the 1024 state bits are output and the
  //     final rounds follow a fold, so the state cannot be resumed from a tag.
  //
  // The generic weakness that does remain is structural: a secret-suffix MAC
  // falls to an internal-state collision on equal-length messages, which for
  // Rainstorm's 1024-bit state is ~2^512 and therefore not a practical
  // concern. Future consideration: adopting real HMAC, or a keyed seed rather
  // than a suffix, would replace an unproven construction with a proved one
  // at negligible cost. Note the seed argument below is 0, so the key reaches
  // the hash only as trailing message bytes.
  static const size_t HMAC_SIZE = 32; // 256 bits for Rainstorm

  std::vector<uint8_t> createHMAC(
    const std::vector<uint8_t> &headerData,
    const std::vector<uint8_t> &ciphertext,
    const std::vector<uint8_t> &key
  ) {
    // 1) Create a buffer for the concatenation
    std::vector<uint8_t> buffer;
    buffer.reserve(headerData.size() + ciphertext.size() + key.size());

    // 2) Concatenate header data, ciphertext, and key
    buffer.insert(buffer.end(), headerData.begin(), headerData.end());
    buffer.insert(buffer.end(), ciphertext.begin(), ciphertext.end());
    buffer.insert(buffer.end(), key.begin(), key.end());

    // 3) Hash the concatenated buffer
    std::vector<uint8_t> hmac(HMAC_SIZE);
    rainstorm::rainstorm<256, false>(buffer.data(), buffer.size(), 0, hmac.data());
    return hmac;
  }

  bool verifyHMAC(
    const std::vector<uint8_t> &headerData,
    const std::vector<uint8_t> &ciphertext,
    const std::vector<uint8_t> &key,
    const std::vector<uint8_t> &hmacToCheck
  ) {
    // Recompute the HMAC
    auto computedHMAC = createHMAC(headerData, ciphertext, key);

    // Compare with the provided HMAC (intended to be constant-time)
    //
    // Note (2026-09-12, external review): this loop does avoid an early
    // return, which is the usual mistake, but it is not constant-time by
    // construction. "if (a[i] != b[i]) equal = false;" is a data-dependent
    // branch; whether it becomes a branchless select is left to the optimiser
    // and can change with compiler, flags, or target. Future consideration:
    // accumulate instead of branching, which is constant-time by construction
    // rather than by the optimiser's choice:
    //
    //   uint8_t diff = 0;
    //   for (size_t i = 0; i < computedHMAC.size(); i++)
    //     diff |= (uint8_t)(computedHMAC[i] ^ hmacToCheck[i]);
    //   return diff == 0;
    //
    // The early size check above is fine to keep: tag length is public.
    if (computedHMAC.size() != hmacToCheck.size()) return false;
    bool equal = true;
    for (size_t i = 0; i < computedHMAC.size(); i++) {
      if (computedHMAC[i] != hmacToCheck[i]) equal = false;
    }
    return equal;
  }

// ------------------------------------------------------------------
// Mining Mode Operator>>(std::istream&, MineMode&) Implementation
//    (If you haven't placed this in tool.h, it can go here)
// ------------------------------------------------------------------
  std::istream& operator>>(std::istream& in, MineMode& mode) {
    std::string token;
    in >> token;
    if (token == "chain") {
      mode = MineMode::Chain;
    } else if (token == "nonceInc") {
      mode = MineMode::NonceInc;
    } else if (token == "nonceRand") {
      mode = MineMode::NonceRand;
    } else {
      mode = MineMode::None;
    }
    return in;
  }
  std::string searchModeToString(const SearchMode& mode) {
    switch(mode) {
      case SearchMode::Prefix:      return "Prefix";
      case SearchMode::Sequence:    return "Sequence";
      case SearchMode::Series:      return "Series";      // added
      case SearchMode::Scatter:     return "Scatter";     // added
      case SearchMode::MapScatter:     return "MapScatter";     // added
      case SearchMode::ParaScatter:     return "ParaScatter";     // added
      default: throw std::runtime_error("Unknown search mode");
    }
  }

  std::istream& operator>>(std::istream& in, SearchMode& mode) {
    std::string token;
    in >> token;
    if (token == "prefix") {
      mode = SearchMode::Prefix;
    } else if (token == "Sequence") {
      mode = SearchMode::Sequence;
    } else if (token == "Series") {
      mode = SearchMode::Series;
    } else if (token == "Scatter" ) {
      mode = SearchMode::Scatter;
    } else if (token == "MapScatter" ) {
      mode = SearchMode::MapScatter;
    } else if (token == "ParaScatter" ) {
      mode = SearchMode::ParaScatter;
    } else {
      in.setstate(std::ios_base::failbit);
    }
    return in;
  }

// Stream retrieval (stdin vs file)
  std::istream& getInputStream() {
  #ifdef _WIN32
    // On Windows, use std::cin
    return std::cin;
  #else
    // On Unix-based systems, use std::ifstream with /dev/stdin
    static std::ifstream in("/dev/stdin");
    return in;
  #endif
  }


// Convert string -> HashAlgorithm
  std::string hashAlgoToString(const HashAlgorithm& algo) {
    switch(algo) {
      case HashAlgorithm::Rainbow:   return "Rainbow";
      case HashAlgorithm::Rainstorm: return "Rainstorm";
      default:
        throw std::runtime_error("Unknown hash algorithm value (expected rainbow or rainstorm)");
    }
  }

  HashAlgorithm getHashAlgorithm(const std::string& algorithm) {
    if (algorithm == "rainbow" || algorithm == "bow") {
      return HashAlgorithm::Rainbow;
    } else if (algorithm == "rainstorm" || algorithm == "storm") {
      return HashAlgorithm::Rainstorm;
    } else {
      return HashAlgorithm::Unknown;
    }
  }

// hash helper
  template<bool bswap>
  void invokeHash(HashAlgorithm algot, uint64_t seed, std::vector<uint8_t>& buffer,
                  std::vector<uint8_t>& temp_out, int hash_size) {
    if (algot == HashAlgorithm::Rainbow) {
      switch(hash_size) {
        case 64:
          rainbow::rainbow<64, bswap>(buffer.data(), buffer.size(), seed, temp_out.data());
          break;
        case 128:
          rainbow::rainbow<128, bswap>(buffer.data(), buffer.size(), seed, temp_out.data());
          break;
        case 256:
          rainbow::rainbow<256, bswap>(buffer.data(), buffer.size(), seed, temp_out.data());
          break;
        default:
          throw std::runtime_error("Invalid hash_size for rainbow");
      }
    } else if (algot == HashAlgorithm::Rainstorm) {
      switch(hash_size) {
        case 64:
          rainstorm::rainstorm<64, bswap>(buffer.data(), buffer.size(), seed, temp_out.data());
          break;
        case 128:
          rainstorm::rainstorm<128, bswap>(buffer.data(), buffer.size(), seed, temp_out.data());
          break;
        case 256:
          rainstorm::rainstorm<256, bswap>(buffer.data(), buffer.size(), seed, temp_out.data());
          break;
        case 512:
          rainstorm::rainstorm<512, bswap>(buffer.data(), buffer.size(), seed, temp_out.data());
          break;
        default:
          throw std::runtime_error("Invalid hash_size for rainstorm");
      }
    } else {
      throw std::runtime_error("Invalid algorithm: " + hashAlgoToString(algot));
    }
  }

// ------------------------------------------------------------------
// Mining Implementations
// ------------------------------------------------------------------
  static void chainAppend(std::vector<uint8_t>& inputBuffer, const std::vector<uint8_t>& hash_output) {
    // Just append the new hash to the existing buffer
    inputBuffer.insert(inputBuffer.end(), hash_output.begin(), hash_output.end());
  }

  void mineChain(HashAlgorithm algot, uint64_t seed, uint32_t hash_size, const std::vector<uint8_t>& prefix_bytes) {
    std::vector<uint8_t> inputBuffer;
    std::vector<uint8_t> hash_output(hash_size / 8);

    uint64_t iterationCount = 0;
    auto start_time = std::chrono::steady_clock::now();

    while (true) {
      iterationCount++;
      invokeHash<bswap>(algot, seed, inputBuffer, hash_output, hash_size);

      if (hasPrefix(hash_output, prefix_bytes)) {
        auto end_time = std::chrono::steady_clock::now();
        double elapsed = std::chrono::duration<double>(end_time - start_time).count();
        double hps = iterationCount / elapsed;

        std::cerr << "\n[mineChain] Found after " << iterationCount << " iterations, ~"
                  << hps << " H/s\n";

        // Print final hash to stdout
        std::cout << "Final Hash: ";
        for (auto b : hash_output) {
          std::cout << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(b);
        }
        std::cout << std::dec << std::endl;
        return;
      }
      chainAppend(inputBuffer, hash_output);

      if (iterationCount % 1000 == 0) {
        auto now = std::chrono::steady_clock::now();
        double elapsed = std::chrono::duration<double>(now - start_time).count();
        double hps = iterationCount / elapsed;
        std::cerr << "\r[mineChain] " << iterationCount << " iterations, ~"
                  << hps << " H/s    " << std::flush;
      }
    }
  }

  void mineNonceInc(HashAlgorithm algot, uint64_t seed, uint32_t hash_size,
                    const std::vector<uint8_t>& prefix_bytes,
                    const std::string& baseInput) {
    std::vector<uint8_t> hash_output(hash_size / 8);
    uint64_t iterationCount = 0;
    uint64_t nonce = 0;

    auto start_time = std::chrono::steady_clock::now();

    while (true) {
      iterationCount++;

      // Build input = baseInput + numeric nonce as text
      std::stringstream ss;
      ss << baseInput << nonce;
      std::string inputStr = ss.str();

      // Convert to bytes
      std::vector<uint8_t> buffer(inputStr.begin(), inputStr.end());
      invokeHash<bswap>(algot, seed, buffer, hash_output, hash_size);

      if (hasPrefix(hash_output, prefix_bytes)) {
        auto end_time = std::chrono::steady_clock::now();
        double elapsed = std::chrono::duration<double>(end_time - start_time).count();
        double hps = iterationCount / elapsed;

        std::cerr << "\n[mineNonceInc] Found after " << iterationCount
                  << " iterations, ~" << hps << " H/s\n"
                  << "Winning nonce: " << nonce << "\n";

        std::cout << "Final Hash: ";
        for (auto b : hash_output) {
          std::cout << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(b);
        }
        std::cout << std::dec << "\n";
        return;
      }

      if (iterationCount % 1000 == 0) {
        auto now = std::chrono::steady_clock::now();
        double elapsed = std::chrono::duration<double>(now - start_time).count();
        double hps = iterationCount / elapsed;
        std::cerr << "\r[mineNonceInc] " << iterationCount << " iterations, ~"
                  << hps << " H/s    " << std::flush;
      }

      nonce++;
    }
  }

  void mineNonceRand(HashAlgorithm algot, uint64_t seed, uint32_t hash_size,
                     const std::vector<uint8_t>& prefix_bytes,
                     const std::string& baseInput) {
    std::vector<uint8_t> hash_output(hash_size / 8);
    uint64_t iterationCount = 0;

    RandomFunc randomFunc = selectRandomFunc(RandomConfig::entropyMode);
    RandomGenerator rng = randomFunc();

    auto start_time = std::chrono::steady_clock::now();

    while (true) {
      iterationCount++;

      // Build input = baseInput + random bytes
      std::vector<uint8_t> buffer(baseInput.begin(), baseInput.end());
      std::vector<uint8_t> random = rng.as<uint8_t>(16);
      buffer.insert(buffer.end(), random.begin(), random.end());

      invokeHash<bswap>(algot, seed, buffer, hash_output, hash_size);

      if (hasPrefix(hash_output, prefix_bytes)) {
        auto end_time = std::chrono::steady_clock::now();
        double elapsed = std::chrono::duration<double>(end_time - start_time).count();
        double hps = iterationCount / elapsed;

        std::cerr << "\n[mineNonceRand] Found after " << iterationCount
                  << " iterations, ~" << hps << " H/s\n";

        std::cout << "Final Hash: ";
        for (auto b : hash_output) {
          std::cout << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(b);
        }
        std::cout << std::dec << "\n";
        return;
      }

      if (iterationCount % 1000 == 0) {
        auto now = std::chrono::steady_clock::now();
        double elapsed = std::chrono::duration<double>(now - start_time).count();
        double hps = iterationCount / elapsed;
        std::cerr << "\r[mineNonceRand] " << iterationCount << " iterations, ~"
                  << hps << " H/s    " << std::flush;
      }
    }
  }

// ------------------------------------------------------------------
// Original hashBuffer
// ------------------------------------------------------------------
  void hashBuffer(Mode mode, HashAlgorithm algot, std::vector<uint8_t>& buffer,
                  uint64_t seed, uint64_t output_length, std::ostream& outstream,
                  uint32_t hash_size) {
    int byte_size = hash_size / 8;
    std::vector<uint8_t> temp_out(byte_size);

    if (mode == Mode::Digest) {
      invokeHash<bswap>(algot, seed, buffer, temp_out, hash_size);

      for (const auto& byte : temp_out) {
        outstream << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(byte);
      }
    }
    else if (mode == Mode::Stream) {
      while (output_length > 0) {
        invokeHash<bswap>(algot, seed, buffer, temp_out, hash_size);

        uint64_t chunk_size = std::min(output_length, (uint64_t)byte_size);
        outstream.write(reinterpret_cast<const char*>(temp_out.data()), chunk_size);

        output_length -= chunk_size;
        if (output_length == 0) {
          break;
        }

        // Update buffer with the output of the last hash operation
        buffer.assign(temp_out.begin(), temp_out.begin() + chunk_size);
      }
    }
  }

void hashAnything(Mode mode, HashAlgorithm algot, const std::string& inpath,
                  std::ostream& outstream, uint32_t size, bool use_test_vectors,
                  uint64_t seed, uint64_t output_length) {

  // If using test vectors, process each one and print the hash.
  if (use_test_vectors) {
    for (const auto& test_vector : test_vectors) {
      std::vector<uint8_t> buffer(test_vector.begin(), test_vector.end());
      hashBuffer(mode, algot, buffer, seed, output_length, outstream, size);
      outstream << ' ' << '"' << test_vector << '"' << '\n';
    }
  } else {
    std::vector<uint8_t> buffer;
    if (!inpath.empty()) {
      // Open the file and read its entire contents into buffer.
      std::ifstream infile(inpath, std::ios::binary);
      if (!infile) {
        throw std::runtime_error("Cannot open file for reading: " + inpath);
      }
      buffer = std::vector<uint8_t>((std::istreambuf_iterator<char>(infile)),
                                    std::istreambuf_iterator<char>());
      infile.close();
    }
    else {
      // Read from stdin (using getInputStream() helper).
      std::istream& in_stream = getInputStream();
      buffer = std::vector<uint8_t>((std::istreambuf_iterator<char>(in_stream)),
                                    std::istreambuf_iterator<char>());
    }

    // Process the complete input buffer.
    hashBuffer(mode, algot, buffer, seed, output_length, outstream, size);
    outstream << ' ' << (inpath.empty() ? "stdin" : inpath) << '\n';
  }
}

// ------------------------------------------------------------------
// Helper for password (key) prompt - disabling echo on POSIX systems
// ------------------------------------------------------------------
#ifdef _WIN32
  static std::string promptForKey(const std::string &prompt) {
    std::cerr << prompt;
    std::string key;
    std::getline(std::cin, key);
    return key;
  }
#else
#include <termios.h>
#include <unistd.h>
  static std::string promptForKey(const std::string &prompt) {
    std::cerr << prompt;
    // Disable echo
    termios oldt;
    tcgetattr(STDIN_FILENO, &oldt);
    termios noEcho = oldt;
    noEcho.c_lflag &= ~ECHO;
    tcsetattr(STDIN_FILENO, TCSANOW, &noEcho);

    std::string key;
    std::getline(std::cin, key);

    // Restore echo
    tcsetattr(STDIN_FILENO, TCSANOW, &oldt);
    std::cerr << std::endl;
    return key;
  }
#endif

// Compress using zlib
  std::vector<uint8_t> compressData(const std::vector<uint8_t>& data) {
    z_stream zs = {};
    if (deflateInit(&zs, Z_BEST_COMPRESSION) != Z_OK) {
      throw std::runtime_error("Failed to initialize zlib deflate.");
    }

    zs.next_in = const_cast<Bytef*>(data.data());
    zs.avail_in = data.size();

    std::vector<uint8_t> compressed;
    uint8_t buffer[1024];

    do {
      zs.next_out = buffer;
      zs.avail_out = sizeof(buffer);

      if (deflate(&zs, Z_FINISH) == Z_STREAM_ERROR) {
        deflateEnd(&zs);
        throw std::runtime_error("zlib compression failed.");
      }

      compressed.insert(compressed.end(), buffer, buffer + (sizeof(buffer) - zs.avail_out));
    } while (zs.avail_out == 0);

    deflateEnd(&zs);
    return compressed;
  }

// Decompress using zlib
  std::vector<uint8_t> decompressData(const std::vector<uint8_t>& data) {
    z_stream zs = {};
    if (inflateInit(&zs) != Z_OK) {
      throw std::runtime_error("Failed to initialize zlib inflate.");
    }

    zs.next_in = const_cast<Bytef*>(data.data());
    zs.avail_in = data.size();

    std::vector<uint8_t> decompressed;
    uint8_t buffer[1024];

    do {
      zs.next_out = buffer;
      zs.avail_out = sizeof(buffer);

      int ret = inflate(&zs, Z_NO_FLUSH);
      if (ret == Z_STREAM_ERROR || ret == Z_DATA_ERROR || ret == Z_MEM_ERROR) {
        inflateEnd(&zs);
        throw std::runtime_error("zlib decompression failed.");
      }

      decompressed.insert(decompressed.end(), buffer, buffer + (sizeof(buffer) - zs.avail_out));

      if (ret == Z_STREAM_END) break;
    } while (zs.avail_out == 0);

    inflateEnd(&zs);
    return decompressed;
  }

// usage
  void usage() {
    std::cout << "Usage: rainsum [OPTIONS] [INFILE]\n"
              << "Calculate a Rainbow or Rainstorm hash.\n\n"
              << "Options:\n"
              << "  -m, --mode [digest|stream]        Specifies the mode, where:\n"
              << "                                    digest mode (the default) gives a fixed length hash in hex,\n"
              << "                                    stream mode gives a variable length binary feedback output\n"
              << "  -a, --algorithm [bow|storm]       Specify the hash algorithm to use. Default: storm\n"
              << "  -s, --size [64-256|64-512]        Specify the bit size of the hash. Default: 256\n"
              << "  -o, --output-file FILE            Output file for the hash or stream\n"
              << "  -t, --test-vectors                Calculate the hash of the standard test vectors\n"
              << "  -l, --output-length HASHES        Set the output length in hash iterations (stream only)\n"
              << "  -v, --version                     Print out the version\n"
              << "  --seed                            Seed value (64-bit number or string). If string is used,\n"
              << "                                    it is hashed with Rainstorm to a 64-bit number\n"
              << "  --mine-mode [chain|nonceInc|nonceRand]   Perform 'mining' tasks until prefix is matched\n"
              << "  --match-prefix <hexstring>               Hex prefix to match for mining tasks\n";
  }

// prk and xof
// ADDED: KDF with Iterations and Info
  static const std::string KDF_INFO_STRING = "powered by Rain hashes created by Cris and DOSYAGO (aka DOSAYGO) over the years 2023 through 2025";
  static const int KDF_ITERATIONS = 8;
  static const int XOF_ITERATIONS = 4;
  static const int DE_ITERATIONS = 1;

  static std::vector<uint8_t> derivePRK(
    const std::vector<uint8_t> &seed,
    const std::vector<uint8_t> &salt,
    const std::vector<uint8_t> &ikm,
    HashAlgorithm algot,
    uint32_t hash_bits,
    bool debug = false
  ) {
    // Combine salt || ikm || info
    std::vector<uint8_t> combined;
    combined.reserve(salt.size() + ikm.size() + KDF_INFO_STRING.size());
    combined.insert(combined.end(), salt.begin(), salt.end());
    combined.insert(combined.end(), ikm.begin(), ikm.end());
    combined.insert(combined.end(), KDF_INFO_STRING.begin(), KDF_INFO_STRING.end());

    // PRK is expected to be (hash_bits / 8) bytes
    size_t prkSize = hash_bits / 8;
    std::vector<uint8_t> prk(prkSize, 0);

    // temp is initialized to the combined salt || ikm || info
    std::vector<uint8_t> temp(combined);

    // Convert first 8 bytes of seed vector to uint64_t (little-endian)
    uint64_t seed_num = 0;
    for (size_t j = 0; j < std::min(static_cast<size_t>(8), seed.size()); ++j) {
      seed_num |= static_cast<uint64_t>(seed[j]) << (j * 8);
    }

    if (debug) {
      std::cerr << "[derivePRK] hash_bits: " << hash_bits << "\n";
      std::cerr << "[derivePRK] prkSize (expected): " << prkSize << "\n";
      std::cerr << "[derivePRK] combined.size(): " << combined.size() << "\n";
      std::cerr << "[derivePRK] seed_num (0x" << std::hex << seed_num << std::dec << "), seed.size(): " << seed.size() << "\n";
      std::cerr << "[derivePRK] Beginning KDF iterations: " << KDF_ITERATIONS << "\n";
    }

    // Iterate the hash function KDF_ITERATIONS times
    for (int i = 0; i < KDF_ITERATIONS; ++i) {
      // Call your hashing function
      invokeHash<bswap>(algot, seed_num, temp, prk, hash_bits);

      // prk is now the result of invokeHash
      temp = prk; // Next iteration takes the output of the previous

      if (debug) {
        std::cerr << "[derivePRK] Iteration " << i + 1
                  << " completed. prk.size(): " << prk.size() << "\n";
        // (Optional) print the first few bytes of prk
        std::cerr << "[derivePRK] PRK first 16 bytes: ";
        for (size_t x = 0; x < std::min<size_t>(16, prk.size()); ++x) {
          std::cerr << std::hex << static_cast<int>(prk[x]) << " ";
        }
        std::cerr << std::dec << "\n";
      }
    }

    if (debug) {
      std::cerr << "[derivePRK] Final PRK size: " << prk.size() << "\n";
      std::cerr << "[derivePRK] Final PRK first 32 bytes: ";
      for (size_t x = 0; x < std::min<size_t>(32, prk.size()); ++x) {
        std::cerr << std::hex << static_cast<int>(prk[x]) << " ";
      }
      std::cerr << std::dec << "\n";
    }

    return prk;
  }


  // SIMD-friendly memory copy
  inline void fast_memcpy(void* dst, const void* src, size_t size) {
    std::memcpy(dst, src, size); // Replace with SIMD intrinsics if beneficial
  }

  static std::vector<uint8_t> extendOutputKDF(
      const std::vector<uint8_t>& prk,
      size_t totalLen,
      HashAlgorithm algot,
      uint32_t hash_bits) {
    
    const size_t hash_size = hash_bits / 8;
    std::vector<uint8_t> output(totalLen);
    
    uint64_t counter = 1;
    std::vector<uint8_t> kn = prk; // Initial K_n = PRK
    
    size_t generated = 0;
    while (generated < totalLen) {
      // Combine PRK || info || counter
      std::vector<uint8_t> combined;
      combined.reserve(prk.size() + KDF_INFO_STRING.size() + 8);
      combined.insert(combined.end(), prk.begin(), prk.end());
      combined.insert(combined.end(), KDF_INFO_STRING.begin(), KDF_INFO_STRING.end());
      
      // Append counter in big-endian
      for (int i = 7; i >= 0; --i) {
        combined.push_back(static_cast<uint8_t>((counter >> (i * 8)) & 0xFF));
      }

      // Perform the hash function KDF_ITERATIONS times
      std::vector<uint8_t> temp = combined;
      std::vector<uint8_t> kn_next(hash_size, 0);
      for (int i = 0; i < KDF_ITERATIONS; ++i) {
        invokeHash<bswap>(algot, 0, temp, kn_next, hash_bits);
        temp = kn_next;
      }

      kn = kn_next;

      // Append to output
      size_t to_copy = std::min(hash_size, totalLen - generated);
      fast_memcpy(output.data() + generated, kn.data(), to_copy);
      generated += to_copy;
      counter++;
    }
    
    return output;
  }

