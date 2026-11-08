#pragma once

#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <random>
#include <vector>
#include <functional>
#include <string>
#include <array>

// Platform-specific includes
#ifdef _WIN32
  #include <windows.h>
  #include <bcrypt.h>
#elif defined(__linux__) || defined(__FreeBSD__) || defined(__OpenBSD__) || defined(__APPLE__)
  #include <fcntl.h>
  #include <unistd.h>
  #include <sys/random.h>
#elif defined(__EMSCRIPTEN__)
  #include <emscripten/emscripten.h>

// JavaScript function to fill buffer with secure random bytes
EM_JS(int, fill_random_bytes, (void* buf, size_t size), {
    try {
        var heap = new Uint8Array(Module.HEAPU8.buffer, buf, size);
        if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
            // Browser environment
            crypto.getRandomValues(heap);
        } else if (typeof require === 'function') {
            // Node.js environment
            var nodeCrypto = require('crypto');
            var randomBytes = nodeCrypto.randomBytes(size);
            heap.set(randomBytes);
        } else {
            throw new Error('No secure random number generator available.');
        }
        return 0; // Success
    } catch (e) {
        return -1; // Failure
    }
});
#else
  #include <fstream>
#endif

// Cross-platform secure randomness
class CustomRandom {
public:
    // Generate a random 64-bit unsigned integer
    static uint64_t randombytes_random() {
        uint64_t value;
        randombytes_buf(&value, sizeof(value));
        return value;
    }

    // Generate a random number uniformly in [0, upper_bound)
    static uint64_t randombytes_uniform(uint64_t upper_bound) {
        if (upper_bound < 2) {
            return 0; // Only one possible value
        }

        uint64_t r, min;
        min = -upper_bound % upper_bound; // Ensure uniformity

        do {
            r = randombytes_random();
        } while (r < min);

        return r % upper_bound;
    }

    // Fill a buffer with secure random bytes
    static void randombytes_buf(void* buf, size_t size) {
#ifdef __EMSCRIPTEN__
        if (fill_random_bytes(buf, size) != 0) {
            throw std::runtime_error("fill_random_bytes failed");
        }
#elif defined(_WIN32)
        if (BCryptGenRandom(nullptr, static_cast<PUCHAR>(buf), static_cast<ULONG>(size), BCRYPT_USE_SYSTEM_PREFERRED_RNG) != 0) {
            throw std::runtime_error("BCryptGenRandom failed");
        }
#elif defined(__linux__) || defined(__FreeBSD__) || defined(__OpenBSD__)
        if (getrandom(buf, size, 0) == -1) {
            throw std::runtime_error("getrandom() failed");
        }
#elif defined(__APPLE__)
        if (getentropy(buf, size) == -1) {
            throw std::runtime_error("getentropy() failed");
        }
#else
        int fd = open("/dev/urandom", O_RDONLY);
        if (fd < 0) {
            throw std::runtime_error("Failed to open /dev/urandom");
        }
        ssize_t read_bytes = read(fd, buf, size);
        close(fd);
        if (read_bytes < 0 || static_cast<size_t>(read_bytes) != size) {
            throw std::runtime_error("Failed to read from /dev/urandom");
        }
#endif
    }
};

// RandomGenerator class to support rng<T>() syntax
class RandomGenerator {
private:
    std::function<std::vector<uint8_t>(size_t)> byteGenerator;

public:
    // Constructor
    explicit RandomGenerator(std::function<std::vector<uint8_t>(size_t)> generator)
        : byteGenerator(std::move(generator)) {}

    // Generate a single value of any type
    template <typename T>
    T operator()() {
        std::vector<uint8_t> bytes = byteGenerator(sizeof(T));
        T value;
        std::memcpy(&value, bytes.data(), sizeof(T));
        return value;
    }

    // Generate multiple values of the same type
    template <typename T>
    std::vector<T> operator()(size_t count) {
        std::vector<T> results(count);
        for (size_t i = 0; i < count; ++i) {
            results[i] = this->operator()<T>();
        }
        return results;
    }

    // Convenience wrappers
    template <typename T>
    T as() {
        return this->operator()<T>();
    }

    template <typename T>
    std::vector<T> as(size_t count) {
        return this->operator()<T>(count);
    }

    // Fill
    template <typename T>
    void fill(T* dest, size_t size) {
      auto randomBytes = this->as<T>(size);
      std::memcpy(dest, randomBytes.data(), size * sizeof(T));
    }
};

// Factory functions for different modes of randomness

// Default Mode: Mersenne Twister seeded with secure entropy
RandomGenerator createDefaultGenerator() {
    std::array<uint32_t, 20> seedData; // 80 bytes = 20 × 32-bit integers
    CustomRandom::randombytes_buf(seedData.data(), seedData.size() * sizeof(uint32_t));
    std::seed_seq seedSeq(seedData.begin(), seedData.end());
    auto rng = std::mt19937_64(seedSeq);

    auto byteGenerator = [rng = std::move(rng)](size_t size) mutable {
        std::vector<uint8_t> result(size);
        std::uniform_int_distribution<uint8_t> dist(0, 255);
        for (size_t i = 0; i < size; ++i) {
            result[i] = dist(rng);
        }
        return result;
    };

    return RandomGenerator(byteGenerator);
}

// Full Mode: Direct use of CustomRandom
RandomGenerator createFullGenerator() {
    auto byteGenerator = [](size_t size) {
        std::vector<uint8_t> result(size);
        CustomRandom::randombytes_buf(result.data(), size);
        return result;
    };

    return RandomGenerator(byteGenerator);
}

// Risky Mode: Plain std::mt19937_64 seeded with std::random_device
RandomGenerator createRiskyGenerator() {
    std::random_device rd;
    auto rng = std::mt19937_64(rd());

    auto byteGenerator = [rng = std::move(rng)](size_t size) mutable {
        std::vector<uint8_t> result(size);
        std::uniform_int_distribution<uint8_t> dist(0, 255);
        for (size_t i = 0; i < size; ++i) {
            result[i] = dist(rng);
        }
        return result;
    };

    return RandomGenerator(byteGenerator);
}

// RandomFunc returns a RandomGenerator
using RandomFunc = std::function<RandomGenerator()>;

// Select the appropriate random generator factory
RandomFunc selectRandomFunc(const std::string& entropyMode) {
    if (entropyMode == "default") {
        return createDefaultGenerator;
    } else if (entropyMode == "full") {
        return createFullGenerator;
    } else if (entropyMode == "risky") {
        return createRiskyGenerator;
    } else {
        throw std::invalid_argument("Invalid entropy mode: " + entropyMode);
    }
}

