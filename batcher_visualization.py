
class Printer:
    def __init__(self, array_size=10, logging_enabled=False):
        self.fixed_array = FixedSizeArray(array_size, logging_enabled)
        self.queue = []  # List to store queued items for printing

    def queue_print(self, id, string, replace=False):
        """
        Queues up a string for printing. If the ID exists, the string is added to the queue
        and marked for printing. If `replace` is True, the string is added again using the add function.
        """

        if replace:
            print(f"Queuing up {string} with id: {id} for printing with replacement.")
            # If replace is True, re-add the string, overwriting the existing one
            self.fixed_array.add(id, string)
        else:
            print(f"Queuing up {string} with id: {id} for printing.")
            # Check if the ID exists in metadata before adding
            if id not in self.fixed_array.tracker.metadata:
                # If the ID doesn't exist yet, add it to the array
                self.fixed_array.add(id, string)
            else:
                print(f"ID '{id}' already exists, skipping addition.")
        
        # Queue the ID for printing
        self.queue.append(id)
    
    def print_everything(self):
        """Prints out all the strings that have been queued up."""
        print("=== PRINTING EVERYTHING ===")
        for id in self.queue:
            string = self.fixed_array.get(id)
            if string is not None:
                print(f"ID '{id}': {string}")
            else:
                print(f"ID '{id}' has no associated string.")
        
        # Clear the queue after printing
        self.queue.clear()

class FixedSizeArrayTracker:
    def __init__(self, size, logging_enabled=False):
        self.size = size
        self.metadata = {}  # Map from ID to (start_index, length)
        self.logging_enabled = logging_enabled  # Control logging

    def _log(self, message):
        """Logs a message if logging is enabled."""
        if self.logging_enabled:
            print(f"[LOG]: {message}")
            print(self)

    def _find_space(self, length):
        """Finds a contiguous block of empty space of the given length."""
        empty_start = None
        empty_count = 0

        for i in range(self.size):
            if any(start <= i < start + length for start, length in self.metadata.values()):
                # If there's a conflict, reset the counter
                empty_start = None
                empty_count = 0
            elif empty_start is None:
                # Start tracking empty space
                empty_start = i
                empty_count = 1
            else:
                # Increment empty space count
                empty_count += 1

            # Check if we've found enough space
            if empty_count == length:
                return empty_start

        # If no sufficient space found, return None
        return None

    def add_metadata(self, id, start, length):
        """Adds metadata for a specific ID."""
        if id in self.metadata:
            self._log(f"ID '{id}' already exists. Use a unique ID.")
            return

        if start + length > self.size:
            self._log("Error: Metadata exceeds array bounds.")
            return

        if any(start <= i < start + length for i in range(self.size) for _, (s, l) in self.metadata.items() if s <= i < s + l):
            self._log("Error: Overlapping metadata.")
            return

        self.metadata[id] = (start, length)
        self._log(f"Added metadata: ID={id}, start={start}, length={length}")

    def remove_metadata(self, id):
        """Removes metadata for a specific ID."""
        if id in self.metadata:
            del self.metadata[id]
            self._log(f"Removed metadata for ID={id}")
        else:
            self._log(f"ID '{id}' not found.")

    def get_metadata(self, id):
        """Retrieves the metadata for the given ID."""
        return self.metadata.get(id, None)

    def compact(self):
        """Compacts the metadata by removing gaps."""
        new_metadata = {}
        current_index = 0

        for id, (start, length) in sorted(self.metadata.items(), key=lambda x: x[1][0]):
            new_metadata[id] = (current_index, length)
            current_index += length

        self.metadata = new_metadata
        self._log("Compacted metadata.")

    def _visualize(self):
        """Returns a visual representation of the metadata."""
        array = ["_"] * self.size
        for id, (start, length) in self.metadata.items():
            for i in range(start, start + length):
                array[i] = str(id)

        return "".join(array)

    def __repr__(self):
        """Returns a detailed representation of the metadata."""
        visualization = self._visualize()
        metadata_str = ", ".join([f"{id}: (start={start}, length={length})" for id, (start, length) in self.metadata.items()])
        return f"Metadata: {{{metadata_str}}}\nVisualization: [{visualization}]"


class FixedSizeArrayStorage:
    def __init__(self, size):
        self.array = [''] * size  # Fixed-size array
        self.size = size

    def add_data(self, start, string):
        """Adds the actual data into the array at the given start index."""
        for i, char in enumerate(string):
            self.array[start + i] = char
    
    def remove_data(self, start, length):
        """Removes data from the array by clearing the specified range."""
        for i in range(length):
            self.array[start + i] = ''
    
    def compact(self):
        """Compacts the array by removing gaps and shifting the data."""
        # Shifting the actual array data to remove gaps
        new_array = [''] * self.size
        current_index = 0

        for i in range(self.size):
            if self.array[i] != '':
                new_array[current_index] = self.array[i]
                current_index += 1

        self.array = new_array

    def get_data(self, start, length):
        """Retrieves data from the array at the given start index."""
        return ''.join(self.array[start:start + length])

    def __repr__(self):
        """Returns a visual representation of the array."""
        return f"Array: {self.array}"


class FixedSizeArray:
    def __init__(self, size, logging_enabled=False):
        self.tracker = FixedSizeArrayTracker(size, logging_enabled)  # Tracks metadata
        self.storage = FixedSizeArrayStorage(size)  # Manages actual data

    def toggle_logging(self):
        """Toggles logging state on or off."""
        self.tracker.logging_enabled = not self.tracker.logging_enabled
    
    def add(self, id, string):
        """Adds a string to the array with a given ID."""
        if self.tracker.logging_enabled:
            print(f"Adding string with ID '{id}': {string}")

        # Clear existing string if ID is already present
        metadata = self.tracker.get_metadata(id)
        if metadata:
            start, length = metadata
            self.storage.remove_data(start, length)
            self.tracker.remove_metadata(id)
            if self.tracker.logging_enabled:
                print(f"Removed old string with ID '{id}'.")

        # Find space for the new string
        length = len(string)
        start = self.tracker._find_space(length)

        # If no space found, compact and try again
        if start is None:
            if self.tracker.logging_enabled:
                print("No space found, compacting array...")
            self.tracker.compact()
            self.storage.compact()
            start = self.tracker._find_space(length)
            if start is None:
                raise ValueError("Not enough space in the array to store the string.")
        
        # Store the string in the array
        self.storage.add_data(start, string)
        # Update metadata
        self.tracker.add_metadata(id, start, length)

        if self.tracker.logging_enabled:
            print(f"Array after adding string with ID '{id}'")

    def get(self, id):
        """Retrieves the string associated with the given ID."""
        metadata = self.tracker.get_metadata(id)
        if not metadata:
            return None
        start, length = metadata
        return self.storage.get_data(start, length)

    def __repr__(self):
        """Returns a visual representation of the array and metadata."""
        return f"{self.storage}\n{self.tracker}"

# Example usage of Printer class
if __name__ == "__main__":
    printer = Printer(array_size=10, logging_enabled=True)
    
    printer.queue_print('id1', 'aaa')
    printer.queue_print('id2', 'bbb')
    
    printer.print_everything()

    printer.queue_print('id3', 'cc', replace=True)
    printer.queue_print('id1', 'ddd', replace=True)

    printer.print_everything()
