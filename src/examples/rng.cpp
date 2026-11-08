#include "../random.h"
#include <iostream>

int main() {
    RandomFunc randomFunc = selectRandomFunc(RandomConfig::entropyMode);
    RandomGenerator rng = randomFunc();

    // Generate random values
    uint64_t randomValue64 = rng.as<uint64_t>();
    uint8_t randomValue8 = rng.as<uint8_t>();

    // Generate multiple values
    auto randomValues = rng.as<uint64_t>(5);

    std::cout << "Random uint64_t: " << randomValue64 << "\n";
    std::cout << "Random uint8_t: " << static_cast<int>(randomValue8) << "\n";

    std::cout << "Random values: ";
    for (const auto& val : randomValues) {
        std::cout << val << " ";
    }
    std::cout << "\n";

    return 0;
}

