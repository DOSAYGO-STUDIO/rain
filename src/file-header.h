// file-header.h

#pragma once
#ifndef FILE_HEADER_H
#define FILE_HEADER_H

#include <array>
#include <cstdint>
#include <vector>
#include <string>
#include <fstream>
#include <stdexcept>
#include <iostream>
#include <iomanip>
#include <cstring> // for memcpy

// -------------------------------------------------------------------
// FileHeader struct (Public Interface)
// -------------------------------------------------------------------
struct FileHeader {
    uint32_t magic;                  // MagicNumber
    uint8_t version;                 // Version
    uint8_t cipherMode;              // Mode: 0x10 = Stream, 0x11 = Block
    uint16_t blockSize;              // Block size in bytes (for block cipher)
    uint16_t nonceSize;              // Nonce size in bytes
    uint16_t hashSizeBits;           // Hash size in bits
    uint16_t outputExtension;        // How much to extend or handle

    std::string hashName;            // Hash algorithm name
    uint64_t iv;                     // 64-bit IV (seed)

    uint8_t saltLen;                 // Length of salt
    std::vector<uint8_t> salt;       // Salt data

    uint8_t searchModeEnum;          // Search mode enum (0x00 - 0x05 for block ciphers, 0xFF for stream)
    uint64_t originalSize;           // Compressed plaintext size
    std::array<uint8_t, 32> hmac;    // HMAC (256-bit)
};

// -------------------------------------------------------------------
// Internal PackedHeader struct (For Serialization)
// -------------------------------------------------------------------
#pragma pack(push, 1)
struct PackedHeader {
    uint32_t magic;           // (1) MagicNumber
    uint8_t version;          // (2) Version
    uint8_t cipherMode;       // (3) Cipher Mode
    uint16_t blockSize;       // (4) Block Size
    uint16_t nonceSize;       // (5) Nonce Size
    uint16_t hashSizeBits;    // (6) Hash Size in Bits
    uint16_t outputExtension; // (7) Output Extension

    uint8_t hashNameLen;      // (8) Length of hashName

    uint64_t iv;              // (9) IV (Seed)

    uint8_t saltLen;          // (10) Length of salt

    uint8_t searchModeEnum;   // (11) Search Mode Enum

    uint64_t originalSize;    // (12) Original Size

    std::array<uint8_t, 32> hmac; // (13) HMAC
};
#pragma pack(pop)

// -------------------------------------------------------------------
// Function: writeFileHeader
// Description: Serializes the FileHeader and writes it to an output stream.
// -------------------------------------------------------------------
inline void writeFileHeader(std::ostream &out, const FileHeader &hdr) {
    if (!out.good()) {
        throw std::runtime_error("Output stream is not ready.");
    }

    // Initialize PackedHeader with corresponding fields
    PackedHeader ph{};
    ph.magic = hdr.magic;
    ph.version = hdr.version;
    ph.cipherMode = hdr.cipherMode;
    ph.blockSize = hdr.blockSize;
    ph.nonceSize = hdr.nonceSize;
    ph.hashSizeBits = hdr.hashSizeBits;
    ph.outputExtension = hdr.outputExtension;

    // Set hashNameLen and ensure it does not exceed 255
    if (hdr.hashName.size() > 255) {
        throw std::runtime_error("hashName too long (>255 bytes)!");
    }
    ph.hashNameLen = static_cast<uint8_t>(hdr.hashName.size());

    ph.iv = hdr.iv;

    // Set saltLen and ensure it does not exceed 255
    if (hdr.salt.size() > 255) {
        throw std::runtime_error("salt too long (>255 bytes)!");
    }
    ph.saltLen = static_cast<uint8_t>(hdr.salt.size());

    ph.searchModeEnum = hdr.searchModeEnum;
    ph.originalSize = hdr.originalSize;
    ph.hmac = hdr.hmac;

    // 1) Write the packed portion
    out.write(reinterpret_cast<const char*>(&ph), sizeof(ph));
    if (!out.good()) {
        throw std::runtime_error("Failed to write PackedHeader to stream.");
    }

    // 2) Write hashName bytes
    if (ph.hashNameLen > 0) {
        out.write(hdr.hashName.data(), ph.hashNameLen);
        if (!out.good()) {
            throw std::runtime_error("Failed to write hashName to stream.");
        }
    }

    // 3) Write salt data
    if (ph.saltLen > 0) {
        out.write(reinterpret_cast<const char*>(hdr.salt.data()), ph.saltLen);
        if (!out.good()) {
            throw std::runtime_error("Failed to write salt data to stream.");
        }
    }
}

// -------------------------------------------------------------------
// Function: readFileHeader
// Description: Deserializes the FileHeader from an input stream.
// -------------------------------------------------------------------
inline FileHeader readFileHeader(std::istream &in) {
    FileHeader hdr{};
    PackedHeader ph{};

    // 1) Read the packed portion
    in.read(reinterpret_cast<char*>(&ph), sizeof(ph));
    if (!in.good()) {
        throw std::runtime_error("Could not read PackedHeader from stream.");
    }

    // Transfer fields from PackedHeader to FileHeader
    hdr.magic = ph.magic;
    hdr.version = ph.version;
    hdr.cipherMode = ph.cipherMode;
    hdr.blockSize = ph.blockSize;
    hdr.nonceSize = ph.nonceSize;
    hdr.hashSizeBits = ph.hashSizeBits;
    hdr.outputExtension = ph.outputExtension;

    hdr.iv = ph.iv;

    hdr.saltLen = ph.saltLen;
    hdr.searchModeEnum = ph.searchModeEnum;
    hdr.originalSize = ph.originalSize;
    hdr.hmac = ph.hmac;

    // 2) Read hashName
    if (ph.hashNameLen > 0) {
        hdr.hashName.resize(ph.hashNameLen);
        in.read(&hdr.hashName[0], ph.hashNameLen);
        if (!in.good()) {
            throw std::runtime_error("Failed to read hashName from stream.");
        }
    } else {
        hdr.hashName.clear();
    }

    // 3) Read salt data
    if (ph.saltLen > 0) {
        hdr.salt.resize(ph.saltLen);
        in.read(reinterpret_cast<char*>(hdr.salt.data()), ph.saltLen);
        if (!in.good()) {
            throw std::runtime_error("Failed to read salt data from stream.");
        }
    } else {
        hdr.salt.clear();
    }

    // 4) Validate magic number
    if (hdr.magic != MagicNumber) {
        throw std::runtime_error("Invalid magic number in file.");
    }

    return hdr;
}

// -------------------------------------------------------------------
// Function: writeHMACToStream
// Description: Overwrites only the HMAC field in the output stream.
// -------------------------------------------------------------------
inline void writeHMACToStream(std::ostream &out, const std::array<uint8_t, 32> &hmac) {
    size_t hmac_offset = 33; // Based on PackedHeader structure

    out.seekp(hmac_offset, std::ios::beg);
    if (!out.good()) {
        throw std::runtime_error("Failed to seek to HMAC position in stream.");
    }

    out.write(reinterpret_cast<const char*>(hmac.data()), hmac.size());
    if (!out.good()) {
        throw std::runtime_error("Failed to write HMAC to stream.");
    }
}

// -------------------------------------------------------------------
// Function: showFileFullInfo
// Description: Displays the FileHeader information in a human-readable format.
// -------------------------------------------------------------------
inline void showFileFullInfo(const std::string &inFilename) {
    std::ifstream fin(inFilename, std::ios::binary);
    if (!fin.is_open()) {
        throw std::runtime_error("Cannot open file for info: " + inFilename);
    }

    FileHeader hdr = readFileHeader(fin);
    fin.close();

    // Determine cipher mode string
    std::string cipherModeStr;
    if (hdr.cipherMode == 0x10) {
        cipherModeStr = "StreamCipher";
    }
    else if (hdr.cipherMode == 0x11) {
        cipherModeStr = "BlockCipher";
    }
    else {
        cipherModeStr = "Unknown/LegacyPuzzle";
    }

    // Display the header information
    std::cout << "=== Unified File Header Info ===\n";
    std::cout << "Magic: RCRY (0x" << std::hex << hdr.magic << std::dec << ")\n";
    std::cout << "Version: " << static_cast<int>(hdr.version) << "\n";
    std::cout << "Cipher Mode: " << cipherModeStr << " (0x"
              << std::hex << static_cast<int>(hdr.cipherMode) << std::dec << ")\n";
    std::cout << "Block Size: " << hdr.blockSize << "\n";
    std::cout << "Nonce Size: " << hdr.nonceSize << "\n";
    std::cout << "Hash Size: " << hdr.hashSizeBits << " bits\n";
    std::cout << "Output Extension: " << hdr.outputExtension << " bytes\n";
    std::cout << "Hash Algorithm: " << hdr.hashName << "\n";
    std::cout << "IV (Seed): 0x" << std::hex << hdr.iv << std::dec << "\n";
    std::cout << "Salt Length: " << static_cast<int>(hdr.saltLen) << "\n";

    if (hdr.saltLen > 0) {
        std::cout << "Salt Data: ";
        for (auto b : hdr.salt) {
            std::cout << std::hex << std::setw(2) << std::setfill('0')
                      << static_cast<int>(b) << " ";
        }
        std::cout << std::dec << "\n";
    }

    std::cout << "Compressed Plaintext Size: " << hdr.originalSize << " bytes\n";
    std::cout << "Search Mode Enum: 0x" << std::hex
              << static_cast<int>(hdr.searchModeEnum) << std::dec << "\n";
    std::cout << "HMAC: ";
    for (auto b : hdr.hmac) {
        std::cout << std::hex << std::setw(2) << std::setfill('0')
                  << static_cast<int>(b) << " ";
    }
    std::cout << std::dec << "\n";
    std::cout << "===============================\n";
}

// -------------------------------------------------------------------
// Function: serializeFileHeader
// Description: Serializes the FileHeader into a contiguous byte buffer.
// -------------------------------------------------------------------
inline std::vector<uint8_t> serializeFileHeader(const FileHeader &hdr) {
    // Initialize PackedHeader
    PackedHeader ph{};
    ph.magic = hdr.magic;
    ph.version = hdr.version;
    ph.cipherMode = hdr.cipherMode;
    ph.blockSize = hdr.blockSize;
    ph.nonceSize = hdr.nonceSize;
    ph.hashSizeBits = hdr.hashSizeBits;
    ph.outputExtension = hdr.outputExtension;

    // Set hashNameLen and ensure it does not exceed 255
    if (hdr.hashName.size() > 255) {
        throw std::runtime_error("hashName too long (>255 bytes)!");
    }
    ph.hashNameLen = static_cast<uint8_t>(hdr.hashName.size());

    ph.iv = hdr.iv;

    // Set saltLen and ensure it does not exceed 255
    if (hdr.salt.size() > 255) {
        throw std::runtime_error("salt too long (>255 bytes)!");
    }
    ph.saltLen = static_cast<uint8_t>(hdr.salt.size());

    ph.searchModeEnum = hdr.searchModeEnum;
    ph.originalSize = hdr.originalSize;
    ph.hmac = hdr.hmac;

    // Allocate buffer with enough space
    std::vector<uint8_t> buffer;
    buffer.reserve(sizeof(ph) + ph.hashNameLen + ph.saltLen);

    // Append the packed header
    buffer.insert(buffer.end(),
                 reinterpret_cast<const uint8_t*>(&ph),
                 reinterpret_cast<const uint8_t*>(&ph) + sizeof(ph));

    // Append hashName bytes
    if (ph.hashNameLen > 0) {
        buffer.insert(buffer.end(),
                     reinterpret_cast<const uint8_t*>(hdr.hashName.data()),
                     reinterpret_cast<const uint8_t*>(hdr.hashName.data()) + ph.hashNameLen);
    }

    // Append salt bytes
    if (ph.saltLen > 0) {
        buffer.insert(buffer.end(),
                     reinterpret_cast<const uint8_t*>(hdr.salt.data()),
                     reinterpret_cast<const uint8_t*>(hdr.salt.data()) + ph.saltLen);
    }

    return buffer;
}

#endif // FILE_HEADER_H

