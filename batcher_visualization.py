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
            print(f"queuing up {string} with id: {id} for printing with replacement")
            # If replace is True, re-add the string, overwriting the existing one
            self.fixed_array.add(id, string)
        else:
            print(f"queuing up {string} with id: {id} for printing")
            if id not in self.fixed_array.metadata:
                # If the ID doesn't exist yet, add it to the array
                self.fixed_array.add(id, string)
            # Queue the string for printing
        self.queue.append(id)
    
    def print_everything(self):
        """Prints out all the strings that have been queued up."""
        print("=== PRINTING EVERYTHING ===")
        for id in self.queue:
            print(self.fixed_array.get(id))
        # Clear the queue after printing
        self.queue.clear()

# FixedSizeArray Class
class FixedSizeArray:
    def __init__(self, size, logging_enabled=False):
        self.array = [''] * size  # Fixed-size array
        self.metadata = {}  # Map from ID to (start_index, length)
        self.size = size
        self.logging_enabled = logging_enabled  # Control logging
    
    def toggle_logging(self):
        """Toggles logging state on or off."""
        self.logging_enabled = not self.logging_enabled

    def _compact(self):
        """Compacts the array by removing gaps and updating metadata."""
        if self.logging_enabled:
            print("Compacting the array...")

        new_array = [''] * self.size
        new_metadata = {}
        current_index = 0

        for id, (start, length) in self.metadata.items():
            for i in range(length):
                new_array[current_index + i] = self.array[start + i]
            new_metadata[id] = (current_index, length)
            current_index += length

        self.array = new_array
        self.metadata = new_metadata
        
        if self.logging_enabled:
            self._log_state("Array after compaction")

    def _find_space(self, length):
        """Finds a contiguous block of empty space of the given length."""
        empty_start = None
        empty_count = 0

        for i in range(self.size):
            if self.array[i] == '':
                if empty_start is None:
                    empty_start = i
                empty_count += 1
                if empty_count == length:
                    return empty_start
            else:
                empty_start = None
                empty_count = 0

        return None
    
    def add(self, id, string):
        """Adds a string to the array with a given ID."""
        if self.logging_enabled:
            print(f"Adding string with ID '{id}': {string}")

        # Clear existing string if ID is already present
        if id in self.metadata:
            start, length = self.metadata[id]
            for i in range(length):
                self.array[start + i] = ''
            del self.metadata[id]
            if self.logging_enabled:
                print(f"Removed old string with ID '{id}'.")

        # Find space for the new string
        length = len(string)
        start = self._find_space(length)

        # If no space found, compact and try again
        if start is None:
            if self.logging_enabled:
                print("No space found, compacting array...")
            self._compact()
            start = self._find_space(length)
            if start is None:
                raise ValueError("Not enough space in the array to store the string.")
        
        # Store the string in the array
        for i, char in enumerate(string):
            self.array[start + i] = char
        
        # Update metadata
        self.metadata[id] = (start, length)
        
        if self.logging_enabled:
            self._log_state(f"Array after adding string with ID '{id}'")

    def get(self, id):
        """Retrieves the string associated with the given ID."""
        if self.logging_enabled:
            print(f"Retrieving string with ID '{id}'")

        if id not in self.metadata:
            return None
        start, length = self.metadata[id]
        return ''.join(self.array[start:start + length])
    
    def _log_state(self, message):
        """Helper function to log the state of the array and metadata."""
        print(message)
        print(f"Array: {self.array}")
        print(f"Metadata: {self.metadata}")
    
    def __repr__(self):
        """Returns a visual representation of the array and metadata."""
        return f"Array: {self.array}\nMetadata: {self.metadata}"

# Example usage of Printer class
if __name__ == "__main__":
    printer = Printer(array_size=10, logging_enabled=True)
    
    printer.queue_print('id1', 'aaa')
    printer.queue_print('id2', 'bbb')
    
    printer.print_everything()

    printer.queue_print('id3', 'cc', replace=True)
    printer.queue_print('id1', 'ddd', replace=True)

    printer.print_everything()
