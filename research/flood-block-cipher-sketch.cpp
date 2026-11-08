#include <iostream>
#include <vector>
#include <cstdint>
#include <cstring>
#include "rainstorm.cpp"  

// Helper function to convert std::vector<uint8_t> to uint64_t array
void convertToUint64Array(const std::vector<uint8_t>& input, uint64_t* output) {
  std::memcpy(output, input.data(), input.size());
}

// Helper function to convert uint64_t array to std::vector<uint8_t>
std::vector<uint8_t> convertToUint8Vector(const uint64_t* input, size_t size) {
  return std::vector<uint8_t>(reinterpret_cast<const uint8_t*>(input), 
                              reinterpret_cast<const uint8_t*>(input) + size);
}

// Feistel round function using Rainstorm
std::vector<uint8_t> feistelRound(const std::vector<uint8_t>& halfBlock, const std::vector<uint8_t>& key) {
  uint64_t block[8], keyBlock[8], output[8];
  convertToUint64Array(halfBlock, block);
  convertToUint64Array(key, keyBlock);

  rainstorm::rainstorm<512, false>(block, sizeof(block), 0, output); // Seed is 0
  return convertToUint8Vector(output, sizeof(output));
}

// Function to generate key schedule
std::vector<std::vector<uint8_t>> generateKeySchedule(const std::string& passphrase, int rounds) {
  std::vector<uint8_t> initialKey(passphrase.begin(), passphrase.end());
  std::vector<std::vector<uint8_t>> keySchedule;

  for (int i = 0; i < rounds; ++i) {
    uint64_t tempOutput[8];
    rainstorm::rainstorm<512, false>(reinterpret_cast<const uint64_t*>(initialKey.data()), initialKey.size(), 0, tempOutput);
    initialKey = convertToUint8Vector(tempOutput, sizeof(tempOutput));
    keySchedule.push_back(initialKey);
  }

  return keySchedule;
}

// Feistel network encryption/decryption
std::vector<uint8_t> feistelNetwork(const std::vector<uint8_t>& block, const std::vector<std::vector<uint8_t>>& keySchedule, int rounds) {
  std::vector<uint8_t> leftHalf(block.begin(), block.begin() + block.size() / 2);
  std::vector<uint8_t> rightHalf(block.begin() + block.size() / 2, block.end());

  for (int i = 0; i < rounds; ++i) {
    std::vector<uint8_t> newRight = feistelRound(rightHalf, keySchedule[i]);
    for (size_t j = 0; j < leftHalf.size(); ++j) {
      leftHalf[j] ^= newRight[j];
    }
    if (i < rounds - 1) {
      std::swap(leftHalf, rightHalf);
    }
  }

  std::vector<uint8_t> combinedBlock(leftHalf.begin(), leftHalf.end());
  combinedBlock.insert(combinedBlock.end(), rightHalf.begin(), rightHalf.end());
  return combinedBlock;
}

int main() {
  std::string passphrase = "SecretPassphrase";
  int rounds = 5;
  std::vector<uint8_t> block(64, 0);  // 512-bit block initialized with zeros

  std::vector<std::vector<uint8_t>> keySchedule = generateKeySchedule(passphrase, rounds);
  std::vector<uint8_t> encrypted = feistelNetwork(block, keySchedule, rounds);
  std::vector<uint8_t> decrypted = feistelNetwork(encrypted, keySchedule, rounds);

  // Displaying encrypted and decrypted data for testing purposes
  std::cout << "Encrypted Data: ";
  for (auto& byte : encrypted) {
    std::cout << std::hex << static_cast<int>(byte);
  }
  std::cout << "\nDecrypted Data: ";
  for (auto& byte : decrypted) {
    std::cout << std::hex << static_cast<int>(byte);
  }
  std::cout << std::endl;

  return 0;
}
