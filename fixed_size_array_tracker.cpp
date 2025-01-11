#include "fixed_size_array_tracker.hpp"
#include <vector>

FixedSizeArrayTracker::FixedSizeArrayTracker(unsigned int size, bool logging_enabled)
    : size(size), logging_enabled(logging_enabled) {}

void FixedSizeArrayTracker::log(const std::string &message) const {
    if (logging_enabled) {
        std::cout << "[LOG]: " << message << "\n";
        std::cout << *this << "\n";
    }
}

std::optional<unsigned int> FixedSizeArrayTracker::find_contiguous_space(unsigned int length) {
    unsigned int last_end = 0;

    // Traverse through sorted intervals
    for (const auto &[start, end] : occupied_intervals) {
        if (start - last_end >= length) {
            return last_end; // Found space before this interval
        }
        last_end = end;
    }

    // Check if there's enough space after the last interval
    if (size - last_end >= length) {
        return last_end;
    }

    return std::nullopt;
}

void FixedSizeArrayTracker::add_metadata(int id, unsigned int start, unsigned int length) {
    if (metadata.count(id)) {
        log("ID '" + std::to_string(id) + "' already exists. Use a unique ID.");
        return;
    }

    if (start + length > size) {
        log("Error: Metadata exceeds array bounds.");
        return;
    }

    // Add metadata and update occupied intervals
    metadata[id] = {start, length};
    occupied_intervals.insert({start, start + length});

    log("Added metadata: ID=" + std::to_string(id) + ", start=" + std::to_string(start) +
        ", length=" + std::to_string(length));
}

void FixedSizeArrayTracker::remove_metadata(int id) {
    auto it = metadata.find(id);
    if (it != metadata.end()) {
        // Remove metadata and update intervals
        auto &[start, length] = it->second;
        occupied_intervals.erase({start, start + length});
        metadata.erase(it);

        log("Removed metadata for ID=" + std::to_string(id));
    } else {
        log("ID '" + std::to_string(id) + "' not found.");
    }
}

std::optional<std::pair<unsigned int, unsigned int>> FixedSizeArrayTracker::get_metadata(int id) const {
    auto it = metadata.find(id);
    if (it != metadata.end()) {
        return it->second;
    }
    return std::nullopt;
}

void FixedSizeArrayTracker::compact() {
    unsigned int current_index = 0;
    std::unordered_map<int, std::pair<unsigned int, unsigned int>> new_metadata;

    // Reassign metadata to eliminate gaps
    for (const auto &[id, range] : metadata) {
        unsigned int length = range.second;
        new_metadata[id] = {current_index, length};
        current_index += length;
    }

    metadata = std::move(new_metadata); // Move the new metadata
    occupied_intervals.clear();         // Clear the current intervals
    for (const auto &[id, range] : metadata) {
        unsigned int start = range.first;
        unsigned int length = range.second;
        occupied_intervals.insert({start, start + length});
    }

    log("Compacted metadata.");
}

const std::unordered_map<int, std::pair<unsigned int, unsigned int>> &FixedSizeArrayTracker::get_all_metadata() const {
    return metadata;
}

std::ostream &operator<<(std::ostream &os, const FixedSizeArrayTracker &tracker) {
    os << "Metadata: {";
    for (const auto &[id, range] : tracker.metadata) {
        os << id << ": (start=" << range.first << ", length=" << range.second << "), ";
    }
    os << "}";
    return os;
}
