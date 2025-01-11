
#ifndef FIXED_SIZE_ARRAY_TRACKER_HPP
#define FIXED_SIZE_ARRAY_TRACKER_HPP

#include <unordered_map>
#include <set>
#include <optional>
#include <iostream>

class FixedSizeArrayTracker {
  public:
    FixedSizeArrayTracker(unsigned int size, bool logging_enabled = false);

    void log(const std::string &message) const;

    std::optional<unsigned int> find_contiguous_space(unsigned int length);

    void add_metadata(int id, unsigned int start, unsigned int length);
    void remove_metadata(int id);
    std::optional<std::pair<unsigned int, unsigned int>> get_metadata(int id) const;

    void compact();

    const std::unordered_map<int, std::pair<unsigned int, unsigned int>> &get_all_metadata() const;

    friend std::ostream &operator<<(std::ostream &os, const FixedSizeArrayTracker &tracker);

  private:
    unsigned int size;
    bool logging_enabled;
    std::unordered_map<int, std::pair<unsigned int, unsigned int>> metadata; // id -> {start, length}
    std::set<std::pair<unsigned int, unsigned int>> occupied_intervals;      // sorted intervals of occupied spaces
};

#endif // FIXED_SIZE_ARRAY_TRACKER_HPP
