// rainsum.cpp

#ifdef _OPENMP
#include <omp.h>
#endif
#include "tool.h" // for invokeHash, etc.
#include "file-header.h"
#include "block-cipher.h"
#include "stream-cipher.h"

// =================================================================
// ADDED: Main Function with Additions Only
// =================================================================
int main(int argc, char** argv) {
    try {
        // Initialize cxxopts with program name and description
        cxxopts::Options options("rainsum", "Calculate a Rainbow or Rainstorm hash, or perform puzzle-based block encryption/decryption, or stream encryption/decryption.");

        // Define command-line options (unchanged)
        options.add_options()
            ("m,mode", "Mode: digest, stream, block-enc, stream-enc, dec, info",
                cxxopts::value<std::string>()->default_value("digest"))
            ("a,algorithm", "Specify the hash algorithm to use (rainbow, rainbow2, rainstorm)",
                cxxopts::value<std::string>()->default_value("rainbow"))
            ("s,size", "Specify the size of the hash (e.g., 64, 128, 256, 512)",
                cxxopts::value<uint32_t>()->default_value("256"))
            ("block-size", "Block size in bytes for puzzle-based encryption (1-255)",
                cxxopts::value<uint16_t>()->default_value("17"))
            ("n,nonce-size", "Size of the nonce in bytes [1-255] (block-enc mode)",
                cxxopts::value<uint16_t>()->default_value("22"))
            ("e,entropy-mode", "Style of random sourcing: default (MT seeded with secure randomness), full (all values drawn from secure randomness)",
                cxxopts::value<std::string>()->default_value("default"))
            ("deterministic-nonce", "Use a deterministic counter for nonce generation",
                cxxopts::value<bool>()->default_value("false"))
            ("search-mode", "Search mode for plaintext mining block cipher: prefix, sequence, series, scatter, mapscatter, parascatter",
#ifdef _OPENMP
                cxxopts::value<std::string>()->default_value("parascatter"))
#else
                cxxopts::value<std::string>()->default_value("scatter"))
#endif
            ("o,output-file", "Output file (stream mode)",
                cxxopts::value<std::string>()->default_value("/dev/stdout"))
            ("t,test-vectors", "Calculate the hash of the standard test vectors",
                cxxopts::value<bool>()->default_value("false"))
            ("l,output-length", "Output length in hash iterations (stream mode)",
                cxxopts::value<uint64_t>()->default_value("1000000"))
            ("x,output-extension", "Output extension in bytes (block-enc mode). Extend digest by this many bytes to make mining larger P blocks faster",
                cxxopts::value<uint16_t>()->default_value("1024"))
            ("seed", "Seed value (0x prefixed hex string or numeric)",
                cxxopts::value<std::string>()->default_value(""))
            ("salt", "Salt value (0x prefixed hex string or string)",
                cxxopts::value<std::string>()->default_value(""))
            // Mining options
            ("mine-mode", "Mining demo mode: chain, nonceInc, nonceRand (mining demo only)",
                cxxopts::value<std::string>()->default_value("None"))
            ("match-prefix", "Hex prefix to match in mining tasks (mining demo only)",
                cxxopts::value<std::string>()->default_value(""))
            // Encrypt / Decrypt options
            ("P,password", "Encryption/Decryption password (raw, insecure)",
                cxxopts::value<std::string>()->default_value(""))
            ("key-material", "Path to a file whose contents will be hashed to derive the encryption/decryption key",
                cxxopts::value<std::string>()->default_value(""))
            ("noop", "Noop flag useful for testing as a placeholder",
                cxxopts::value<bool>()->default_value("false"))
            // ADDED: verbose
            ("vv,verbose", "Enable verbose output for series/scatter indices",
                cxxopts::value<bool>()->default_value("false"))
            ("v,version", "Print version")
            ("h,help", "Print usage");

        // Parse command-line options
        auto result = options.parse(argc, argv);

        // Handle help and version immediately
        if (result.count("help")) {
            std::cerr << options.help() << "\n";
            return 0;
        }

        if (result.count("version")) {
            std::cerr << "rainsum version: " << VERSION << "\n"; // Replace with actual VERSION
            return 0;
        }

        // ADDED: verbose
        bool verbose = result["verbose"].as<bool>();

        // Access and validate options

        // Hash Size
        uint32_t hash_size = result["size"].as<uint32_t>();

        // Determine Mode
        std::string modeStr = result["mode"].as<std::string>();
        Mode mode;
        if (modeStr == "digest") mode = Mode::Digest;
        else if (modeStr == "stream") mode = Mode::Stream;
        else if (modeStr == "block-enc") mode = Mode::BlockEnc;
        else if (modeStr == "stream-enc") mode = Mode::StreamEnc;
        else if (modeStr == "dec") mode = Mode::Dec;
        else if (modeStr == "info") mode = Mode::Info;
        else throw std::runtime_error("Invalid mode: " + modeStr);

        // Determine entropy mode
        RandomConfig::entropyMode = result["entropy-mode"].as<std::string>();


        // Key material or password
        // Key material handling
        std::string keyMaterialPath = result["key-material"].as<std::string>();
        std::string password = result["password"].as<std::string>();
        std::vector<uint8_t> key_input_enc;

        if ( mode == Mode::BlockEnc || mode == Mode::StreamEnc || mode == Mode::Dec ) {
          if (!keyMaterialPath.empty()) {
              // Read the file contents
              std::ifstream keyFile(keyMaterialPath, std::ios::binary);
              if (!keyFile.is_open()) {
                  throw std::runtime_error("Unable to open key material file: " + keyMaterialPath);
              }
              std::vector<uint8_t> fileData((std::istreambuf_iterator<char>(keyFile)),
                                            (std::istreambuf_iterator<char>()));
              keyFile.close();

              // Hash the file contents to derive a 512-bit key
              key_input_enc.resize(512 / 8);
              rainstorm::rainstorm<512, bswap>(fileData.data(), fileData.size(), 0, key_input_enc.data());
              if (verbose) {
                  std::cerr << "[Info] Derived 512-bit key from file: " << keyMaterialPath << "\n";
              }
          } else {
              // Fallback to password-based key derivation
              if (password.empty()) {
                  password = promptForKey("Enter encryption key: ");
              }
              key_input_enc.assign(password.begin(), password.end());
          }
        }

        std::vector<uint8_t> keyVec_enc(key_input_enc.begin(), key_input_enc.end());

        // Determine Hash Algorithm
        std::string algorithm = result["algorithm"].as<std::string>();
        HashAlgorithm algot = getHashAlgorithm(algorithm);
        if (algot == HashAlgorithm::Unknown) {
            throw std::runtime_error("Unsupported algorithm string: " + algorithm);
        }

        // Validate Hash Size based on Algorithm
        if (algot == HashAlgorithm::Rainbow || algot == HashAlgorithm::Rainbow2) {
            if (hash_size == 512) {
                hash_size = 256;
            }
            if (hash_size != 64 && hash_size != 128 && hash_size != 256) {
                throw std::runtime_error("Invalid size for Rainbow/Rainbow2 (must be 64, 128, or 256).");
            }
            if ( mode == Mode::BlockEnc || mode == Mode::StreamEnc || mode == Mode::Dec ) {
              algot = HashAlgorithm::Rainstorm;
              hash_size = 512;
            }
        }
        else if (algot == HashAlgorithm::Rainstorm) {
            if (hash_size != 64 && hash_size != 128 && hash_size != 256 && hash_size != 512) {
                throw std::runtime_error("Invalid size for Rainstorm (must be 64, 128, 256, or 512).");
            }
            if ( mode == Mode::BlockEnc || mode == Mode::StreamEnc || mode == Mode::Dec ) {
              hash_size = 512;
            }
        }

        // Block Size
        uint16_t blockSize = result["block-size"].as<uint16_t>();
        if (blockSize == 0 || blockSize > 65535) {
            throw std::runtime_error("Block size must be between 1 and 65535 bytes.");
        }

        // Nonce Size
        uint16_t nonceSize = result["nonce-size"].as<uint16_t>();
        if (nonceSize == 0 || nonceSize > 65535) {
            throw std::runtime_error("Nonce size must be between 1 and 65535 bytes.");
        }

        // Nonce nature
        bool deterministicNonce = result["deterministic-nonce"].as<bool>();

        // Search Mode
        std::string searchMode = result["search-mode"].as<std::string>();
        if (searchMode != "prefix" && searchMode != "sequence" &&
            searchMode != "series" && searchMode != "scatter" && searchMode != "mapscatter" && searchMode != "parascatter") {
            throw std::runtime_error("Invalid search mode: " + searchMode);
        }

        // Output extension
        uint16_t output_extension = result["output-extension"].as<uint16_t>();

        RandomFunc randomFunc = selectRandomFunc(RandomConfig::entropyMode);
        RandomGenerator rng = randomFunc();

        // Convert Seed (either numeric or hex string)
        std::string seed_str = result["seed"].as<std::string>();
        uint64_t seed = 0;
        bool userProvidedSeed = false;
        if (!seed_str.empty()) {
          userProvidedSeed = true;
          try {
            if (seed_str.find("0x") == 0 || seed_str.find("0X") == 0) {
              seed = std::stoull(seed_str.substr(2), nullptr, 16);
            } else {
              seed = std::stoull(seed_str, nullptr, 10);
            }
          }
          catch (...) {
            // If not a valid number, hash the string to 64 bits
            seed = hash_string_to_64_bit(seed_str);
          }
        }

        // If user did NOT provide seed, generate a random one
        if (!userProvidedSeed && mode != Mode::Digest) {
          // A simple example using std::random_device + Mersenne Twister
          seed = rng.as<uint64_t>();  // 64-bit random
          if (verbose) {
            std::cerr << "[Info] No seed provided; generated random seed: 0x"
                      << std::hex << seed << std::dec << "\n";
          }
        }

        if (verbose) {
            std::cerr << "[Verbose] Seed Details:" << "\n"
                      << "  - Seed empty: " << (seed_str.empty() ? "true" : "false") << "\n"
                      << "  - Seed size: " << seed_str.size() << "\n"
                      << "  - Seed string: \"" << seed_str << "\"\n"
                      << "  - Seed uint64_t (hex): 0x" << std::hex << seed << std::dec << "\n";
        }


        // SALT handling:
        std::string salt_str = result["salt"].as<std::string>();
        std::vector<uint8_t> salt;
        bool userProvidedSalt = false;

        if (!salt_str.empty()) {
          userProvidedSalt = true;
          if (salt_str.find("0x") == 0 || salt_str.find("0X") == 0) {
            // Hex string
            salt_str = salt_str.substr(2);
            if (salt_str.size() % 2 != 0) {
              throw std::runtime_error("Salt hex string must have even length.");
            }
            for (size_t i = 0; i < salt_str.size(); i += 2) {
              uint8_t byte = static_cast<uint8_t>(std::stoul(salt_str.substr(i, 2), nullptr, 16));
              salt.push_back(byte);
            }
          } else {
            // Regular string
            salt.assign(salt_str.begin(), salt_str.end());
          }
        }

        // If user did NOT provide salt, generate random salt with size 32 (or hash_size/8, your choice)
        if (!userProvidedSalt && mode != Mode::Digest) {
          // For example, 32 random bytes:
          const size_t saltLen = 32;
          salt.resize(saltLen);
          rng.fill(salt.data(), saltLen);
          if (verbose) {
            std::cerr << "[Info] No salt provided; generated random 32-byte salt:\n  ";
            for (auto &b : salt) {
              std::cerr << std::hex << (int)b << " ";
            }
            std::cerr << std::dec << "\n";
          }
        }

        // Test Vectors
        bool use_test_vectors = result["test-vectors"].as<bool>();

        // Output Length
        uint64_t output_length = result["output-length"].as<uint64_t>();

        // Adjust output_length based on mode
        if (mode == Mode::Digest) {
            // digest mode output_length is just the digest size
            output_length = hash_size / 8;
        }
        else if (mode == Mode::Stream) {
            // stream mode is hash output in bytes by output_length because output length is then iterations of hash
            output_length *= hash_size / 8;
        }

        // Mining arguments
        std::string mine_mode_str = result["mine-mode"].as<std::string>();
        MineMode mine_mode;
        if (mine_mode_str == "chain") mine_mode = MineMode::Chain;
        else if (mine_mode_str == "nonceInc") mine_mode = MineMode::NonceInc;
        else if (mine_mode_str == "nonceRand") mine_mode = MineMode::NonceRand;
        else mine_mode = MineMode::None;

        std::string prefixHex = result["match-prefix"].as<std::string>();

        // Unmatched arguments might be input file
        std::string inpath;
        if (!result.unmatched().empty()) {
            inpath = result.unmatched().front();
        }

        // Handle Mining Modes
        if (mine_mode != MineMode::None) {
            if (prefixHex.empty()) {
                throw std::runtime_error("You must specify --match-prefix for mining modes.");
            }

            // Convert prefix from hex
            auto hexToBytes = [&](const std::string &hexstr) -> std::vector<uint8_t> {
                if (hexstr.size() % 2 != 0) {
                    throw std::runtime_error("Hex prefix must have even length.");
                }
                std::vector<uint8_t> bytes(hexstr.size() / 2);
                for (size_t i = 0; i < bytes.size(); ++i) {
                    unsigned int val = 0;
                    std::stringstream ss;
                    ss << std::hex << hexstr.substr(i*2, 2);
                    ss >> val;
                    bytes[i] = static_cast<uint8_t>(val);
                }
                return bytes;
            };

            std::vector<uint8_t> prefixBytes = hexToBytes(prefixHex);

            switch (mine_mode) {
                case MineMode::Chain:
                    mineChain(algot, seed, hash_size, prefixBytes);
                    return 0;
                case MineMode::NonceInc:
                    mineNonceInc(algot, seed, hash_size, prefixBytes, inpath);
                    return 0;
                case MineMode::NonceRand:
                    mineNonceRand(algot, seed, hash_size, prefixBytes, inpath);
                    return 0;
                default:
                    throw std::runtime_error("Invalid mine-mode encountered.");
            }
        }

        // If mode == info, just show header info
        if (mode == Mode::Info) {
            if (inpath.empty()) {
                throw std::runtime_error("No input file specified for info mode.");
            }

            // Show unified FileHeader info
            showFileFullInfo(inpath);
            return 0;
        }

        // Normal Hashing or Encryption/Decryption
        std::string outpath_enc = result["output-file"].as<std::string>();
        // We'll write ciphertext to inpath + ".rc"
        std::string encFile = inpath + ".rc";

        if (mode == Mode::Digest) {
            // Just a normal digest
            if (outpath_enc == "/dev/stdout") {
                hashAnything(Mode::Digest, algot, inpath, std::cout, hash_size, use_test_vectors, seed, output_length);
            }
            else {
                std::ofstream outfile(outpath_enc, std::ios::binary);
                if (!outfile.is_open()) {
                    std::cerr << "Failed to open output file: " << outpath_enc << std::endl;
                    return 1;
                }
                hashAnything(Mode::Digest, algot, inpath, outfile, hash_size, use_test_vectors, seed, output_length);
            }
        }
        else if (mode == Mode::Stream) {
            if (outpath_enc == "/dev/stdout") {
                hashAnything(Mode::Stream, algot, inpath, std::cout, hash_size, use_test_vectors, seed, output_length);
            }
            else {
                std::ofstream outfile(outpath_enc, std::ios::binary);
                if (!outfile.is_open()) {
                    std::cerr << "Failed to open output file: " << outpath_enc << std::endl;
                    return 1;
                }
                hashAnything(Mode::Stream, algot, inpath, outfile, hash_size, use_test_vectors, seed, output_length);
            }
        }
        else if (mode == Mode::BlockEnc) {
            if (inpath.empty()) {
                throw std::runtime_error("No input file specified for encryption.");
            }

            // Check if encFile exists and overwrite it with zeros if it does
            try {
                overwriteFileWithZeros(encFile);
                if (std::filesystem::exists(encFile)) {
                    std::cerr << "[Info] Existing encrypted file '" << encFile << "' has been securely overwritten with zeros.\n";
                }
            }
            catch (const std::exception &e) {
                throw std::runtime_error("Error while overwriting existing encrypted file: " + std::string(e.what()));
            }

            // ADDED: Call the existing puzzleEncryptFileWithHeader with updated header
            puzzleEncryptFileWithHeader(inpath, encFile, keyVec_enc, algot, hash_size, seed, salt, blockSize, nonceSize, searchMode, verbose, deterministicNonce, output_extension);
            std::cerr << "[Enc] Wrote encrypted file to: " << encFile << "\n";
        }
        else if (mode == Mode::StreamEnc) {
            if (inpath.empty()) {
                throw std::runtime_error("No input file specified for encryption.");
            }

            // Check if encFile exists and overwrite it with zeros if it does
            try {
                overwriteFileWithZeros(encFile);
                if (std::filesystem::exists(encFile)) {
                    std::cerr << "[Info] Existing encrypted file '" << encFile << "' has been securely overwritten with zeros.\n";
                }
            }
            catch (const std::exception &e) {
                throw std::runtime_error("Error while overwriting existing encrypted file: " + std::string(e.what()));
            }

            // ADDED: Call streamEncryptFileWithHeader
            streamEncryptFileWithHeader(
                inpath,
                encFile,
                keyVec_enc,
                algot,
                hash_size,
                seed,          // Using seed as IV
                salt,          // Using provided salt
                output_extension,
                verbose
            );
            std::cerr << "[StreamEnc] Wrote encrypted file to: " << encFile << "\n";
        }
        else if (mode == Mode::Dec) {
            if (inpath.empty()) {
                throw std::runtime_error("No ciphertext file specified for decryption.");
            }

            // We'll write plaintext to inpath + ".dec"
            std::string decFile = inpath + ".dec";

            // ======== HMAC Verification ========
            // 1. Open the encrypted file to read header and ciphertext
            std::ifstream fin_dec(inpath, std::ios::binary);
            if (!fin_dec.is_open()) {
                throw std::runtime_error("[Dec] Cannot open ciphertext file: " + inpath);
            }

            // 2. Read the header
            FileHeader hdr_dec = readFileHeader(fin_dec);

            // 3. Read the ciphertext (rest of the file after header)
            std::vector<uint8_t> ciphertext_dec(
                (std::istreambuf_iterator<char>(fin_dec)),
                (std::istreambuf_iterator<char>())
            );
            fin_dec.close();

            // 4. Backup the stored HMAC
            std::vector<uint8_t> storedHMAC_vec(hdr_dec.hmac.begin(), hdr_dec.hmac.end());

            // 5. Serialize the header with zeroed HMAC for HMAC computation
            FileHeader hdr_dec_for_hmac = hdr_dec;
            std::fill(hdr_dec_for_hmac.hmac.begin(), hdr_dec_for_hmac.hmac.end(), 0x00);
            std::vector<uint8_t> headerData_dec = serializeFileHeader(hdr_dec_for_hmac);

            // 6. Convert key_input to vector<uint8_t>
            std::vector<uint8_t> keyVec_dec(key_input_enc.begin(), key_input_enc.end());

            // 7. Compute HMAC
            auto computedHMAC_dec = createHMAC(headerData_dec, ciphertext_dec, keyVec_dec);

            // 8. Verify HMAC
            if (!verifyHMAC(headerData_dec, ciphertext_dec, keyVec_dec, storedHMAC_vec)) {
                throw std::runtime_error("[Dec] HMAC verification failed! File may be corrupted or tampered with.");
            }
            else {
                std::cerr << "[Dec] HMAC verification succeeded.\n";
            }

            if (hdr_dec.magic != MagicNumber) {
                throw std::runtime_error("[Dec] Invalid magic number in header.");
            }

            if (hdr_dec.cipherMode == 0x10) { // Stream Cipher Mode
                // ADDED: Stream Decryption
                streamDecryptFileWithHeader(
                    inpath,
                    decFile,
                    keyVec_dec,
                    verbose
                );
                std::cerr << "[Dec] Wrote decrypted plaintext to: " << decFile << "\n";
            }
            else if (hdr_dec.cipherMode == 0x11) { // Block Cipher Mode
                // ADDED: Block Decryption (integration with tool.h assumed)
                puzzleDecryptFileWithHeader(inpath, decFile, keyVec_dec);
                std::cerr << "[Dec] Wrote decrypted plaintext to: " << decFile << "\n";
            }
            else {
                throw std::runtime_error("[Dec] Unknown cipher mode in header.");
            }
        }

        if ( mode == Mode::StreamEnc || mode == Mode::BlockEnc ) {
            // ======== HMAC Creation ========
            // 1. Open the encrypted file to read header and ciphertext
            std::ifstream fin_enc(encFile, std::ios::binary);
            if (!fin_enc.is_open()) {
                throw std::runtime_error("Cannot reopen encrypted file for HMAC computation: " + encFile);
            }

            // 2. Read the header
            FileHeader hdr_enc = readFileHeader(fin_enc);

            // 3. Read the ciphertext (rest of the file after header)
            std::vector<uint8_t> ciphertext_enc(
                (std::istreambuf_iterator<char>(fin_enc)),
                (std::istreambuf_iterator<char>())
            );
            fin_enc.close();

            // 4. Serialize the header with zeroed HMAC for HMAC computation
            FileHeader hdr_enc_for_hmac = hdr_enc;
            std::fill(hdr_enc_for_hmac.hmac.begin(), hdr_enc_for_hmac.hmac.end(), 0x00);
            std::vector<uint8_t> headerData_enc = serializeFileHeader(hdr_enc_for_hmac);

            // 6. Compute HMAC
            auto hmac_enc = createHMAC(headerData_enc, ciphertext_enc, keyVec_enc);

            // 7. Update the HMAC field in the original header
            hdr_enc.hmac = std::array<uint8_t, 32>();
            std::copy(hmac_enc.begin(), hmac_enc.end(), hdr_enc.hmac.begin());

            // 8. Overwrite only the HMAC field in the encrypted file
            std::ofstream fout_enc(encFile, std::ios::binary | std::ios::in | std::ios::out);
            if (!fout_enc.is_open()) {
                throw std::runtime_error("Cannot reopen encrypted file for HMAC writing: " + encFile);
            }

            // Use the new function to write HMAC
            writeHMACToStream(fout_enc, hdr_enc.hmac);
            fout_enc.close();

            // Test read back
            std::ifstream test_enc(encFile, std::ios::binary);
            auto test_hdr = readFileHeader(test_enc);
            test_enc.close();

            std::cerr << "[Enc] HMAC computed and stored successfully. HMAC first 4 bytes: "
                      << std::hex
                      << static_cast<int>(test_hdr.hmac[0]) << " "
                      << static_cast<int>(test_hdr.hmac[1]) << " "
                      << static_cast<int>(test_hdr.hmac[2]) << " "
                      << static_cast<int>(test_hdr.hmac[3])
                      << std::dec << "\n";
        }

        return 0;
    }
    catch (const cxxopts::exceptions::exception& e) {
        std::cerr << "Error parsing options: " << e.what() << "\n";
        return 1;
    }
    catch (const std::bad_cast &e) {
        std::cerr << "Bad cast during option parsing: " << e.what() << "\n";
        return 1;
    }
    catch (const std::runtime_error &e) {
        std::cerr << "An error occurred: " << e.what() << std::endl;
        return 1;
    }
}

