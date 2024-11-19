#ifndef HASHING_HPP
#define HASHING_HPP

#include <glm/glm.hpp>
#include <functional>

// Hash specialization for glm::vec3
namespace std {
template <> struct hash<glm::vec3> {
    size_t operator()(const glm::vec3 &v) const {
        size_t h1 = std::hash<float>{}(v.x);
        size_t h2 = std::hash<float>{}(v.y);
        size_t h3 = std::hash<float>{}(v.z);
        return h1 ^ (h2 << 1) ^ (h3 << 2);
    }
};

// Hash specialization for glm::vec2
template <> struct hash<glm::vec2> {
    size_t operator()(const glm::vec2 &v) const {
        size_t h1 = std::hash<float>{}(v.x);
        size_t h2 = std::hash<float>{}(v.y);
        return h1 ^ (h2 << 1);
    }
};

// Hash specialization for std::vector<T>
template <typename T> struct hash<std::vector<T>> {
    size_t operator()(const std::vector<T> &vec) const {
        size_t result = 0;
        for (const auto &elem : vec) {
            result ^= std::hash<T>{}(elem) + 0x9e3779b9 + (result << 6) + (result >> 2); // Custom hash combination
        }
        return result;
    }
};

} // namespace std

#endif // HASHING_HPP
