#include <random>
#include <map>
#include <iostream>
#include <fstream>
#include <iomanip>
#include <cmath>
#include <vector>
#include <algorithm>
#include <string>
#include <sstream>
#include <chrono>
#include <omp.h>
#include <cstring> // for strcmp
#include <cstdlib> // for atoi
#include "math_utils.h"

struct AvalancheStatistics {
    uint64_t P;
    uint64_t G;
    double zero_bits_percentage;
    double mean;
    double stddev;
    std::map<int, int> histogram;
};

AvalancheStatistics avalanche_quality(uint64_t P, uint64_t G) {
    std::random_device rd;
    std::mt19937_64 gen(rd());
    std::uniform_int_distribution<uint64_t> dist(1ULL << 63, ((1ULL << 63) - 1) + (1ULL << 63));

    const int iterations = 10000000;
    std::map<int, int> histogram;
    int sumBitChanges = 0;
    int zero_bits_count = 0;

    for (int i = 1; i <= iterations; i++) {
        uint64_t state = dist(gen);
        uint64_t modified_state = state ^ (1ULL << (gen() % 64));

        uint64_t state_prime = (state * G) % P;
        uint64_t modified_state_prime = (modified_state * G) % P;

        int bitsChanged = math_utils::hamming_distance(state_prime, modified_state_prime);
        histogram[bitsChanged]++;

        if (bitsChanged == 0) {
            zero_bits_count++;
        }

        sumBitChanges += bitsChanged;
    }

    double average = static_cast<double>(sumBitChanges) / iterations;
    double zero_bits_percentage = static_cast<double>(zero_bits_count) / iterations * 100;

    double sumOfSquaredDifferences = 0;
    for (auto &entry : histogram) {
        double diff = entry.first - average;
        sumOfSquaredDifferences += diff * diff * entry.second;
    }
    double stdev = std::sqrt(sumOfSquaredDifferences / iterations);

    return {P, G, zero_bits_percentage, average, stdev, histogram};
}

// Emphasizing stddev more than mean in the ranking function
bool ranking_function(const AvalancheStatistics& a, const AvalancheStatistics& b) {
    double score_a = 10 * std::abs(a.mean - 32) + 15 * a.stddev + 5 * a.zero_bits_percentage;
    double score_b = 10 * std::abs(b.mean - 32) + 15 * b.stddev + 5 * b.zero_bits_percentage;
    return score_a < score_b;
}

std::string generate_histogram_string(const std::map<int, int>& histogram, int iterations) {
    std::stringstream ss;
    for (auto &entry : histogram) {
        ss << std::setw(2) << entry.first << " bits: ";
        int barLength = entry.second / (iterations/500);
        for (int i = 0; i < barLength; i++) ss << "#";
        if (barLength > 0) ss << " ";
        ss << "(" << entry.second << ")\n";
    }
    return ss.str();
}

void print_usage() {
    std::cout << "Usage: avalanche_program [num_samples]\n"
              << "       avalanche_program -h\n\n"
              << "num_samples: number of (P,G) pairs to test (default: 10)\n"
              << "-h         : show this help message\n";
}

int main(int argc, char* argv[]) {
    int num_samples = 10; // default number of samples

    // Check for help flag
    if (argc > 1 && std::strcmp(argv[1], "-h") == 0) {
        print_usage();
        return 0;
    }

    // If a numeric argument is provided, use it as num_samples
    if (argc > 1) {
        num_samples = std::atoi(argv[1]);
        if (num_samples <= 0) {
            std::cerr << "Error: num_samples must be a positive integer.\n";
            return 1;
        }
    }

    std::vector<AvalancheStatistics> results;

    #pragma omp parallel for
    for (int i = 0; i < num_samples; i++) {
        uint64_t P = math_utils::random_large_prime();
        std::vector<uint64_t> factors = math_utils::factorize_source(P);
        uint64_t G = math_utils::find_generator(factors, P);

        AvalancheStatistics stat = avalanche_quality(P, G);

        #pragma omp critical
        {
            results.push_back(stat);
        }
    }

    // Sort the results based on the ranking function
    std::sort(results.begin(), results.end(), ranking_function);

    // Get the current time as timestamp
    auto now = std::chrono::system_clock::now();
    auto now_time_t = std::chrono::system_clock::to_time_t(now);
    auto now_tm = std::localtime(&now_time_t);

    // Format the timestamp
    std::ostringstream timestamp;
    timestamp << std::put_time(now_tm, "%Y-%m-%d_%H-%M-%S");

    // Concatenate timestamp to filename
    std::string filename = "avalanche_results_" + timestamp.str() + ".txt";

    std::ofstream file(filename);
    for (const auto &res : results) {
        file << "P: " << res.P << ", G: " << res.G << ", Zero bits %: " << res.zero_bits_percentage;
        file << ", Mean: " << res.mean << ", Stddev: " << res.stddev << "\n";
        file << "Histogram:\n" << generate_histogram_string(res.histogram, 10000000) << "\n";
    }

    // Print the top 50 results to stdout
    std::cout << "Top 50 results:\n";
    for (int i = 0; i < 50 && i < (int)results.size(); i++) {
        std::cout << "P: " << results[i].P << ", G: " << results[i].G << ", Zero bits %: " << results[i].zero_bits_percentage;
        std::cout << ", Mean: " << results[i].mean << ", Stddev: " << results[i].stddev << "\n";
    }

    return 0;
}

