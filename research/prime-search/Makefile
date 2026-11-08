# Compiler and flags
CXX = g++
CXXFLAGS = -O2 -std=c++17 -fopenmp

# Target name
TARGET = avalanche_program

# Source files
SRC = main.cpp math_utils.h

# Default rule
all: $(TARGET)

# Rule to build the target
$(TARGET): main.cpp math_utils.h
	$(CXX) $(CXXFLAGS) main.cpp -o $(TARGET)

# Clean up generated files
clean:
	rm -f $(TARGET)

