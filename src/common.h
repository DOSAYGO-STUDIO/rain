#pragma once

#define __ENDIAN_H_VERSION__ "1.3.0"

#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
constexpr bool bswap = false;
#elif __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
constexpr bool bswap = true;
#else
#error "Endianness not supported!"
#endif

#define ROTR64(x, n) (((x) >> (n)) | ((x) << (64 - (n))))
constexpr size_t CHUNK_SIZE = 16384;

typedef uint64_t seed_t;

struct IHashState {
    virtual void update(const uint8_t* chunk, size_t chunk_len) = 0;
    virtual void finalize(void* out) = 0;
    virtual ~IHashState() = default;
    size_t len;
};

template <bool bswap>
static inline uint64_t GET_U64(const uint8_t* data, size_t index) {
  uint64_t result;
  std::memcpy(&result, data + index, sizeof(result));
  if(bswap) {
    result = ((result & 0x00000000000000FF) << 56) |
             ((result & 0x000000000000FF00) << 40) |
             ((result & 0x0000000000FF0000) << 24) |
             ((result & 0x00000000FF000000) << 8) |
             ((result & 0x000000FF00000000) >> 8) |
             ((result & 0x0000FF0000000000) >> 24) |
             ((result & 0x00FF000000000000) >> 40) |
             ((result & 0xFF00000000000000) >> 56);
  }
  return result;
}

template <bool bswap>
static inline void PUT_U64(uint64_t value, uint8_t* data, size_t index) {
  if(bswap) {
    value = ((value & 0x00000000000000FF) << 56) |
            ((value & 0x000000000000FF00) << 40) |
            ((value & 0x0000000000FF0000) << 24) |
            ((value & 0x00000000FF000000) << 8) |
            ((value & 0x000000FF00000000) >> 8) |
            ((value & 0x0000FF0000000000) >> 24) |
            ((value & 0x00FF000000000000) >> 40) |
            ((value & 0xFF00000000000000) >> 56);
  }
  std::memcpy(data + index, &value, sizeof(value));
}

