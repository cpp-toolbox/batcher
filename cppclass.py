import re
from typing import List, Set


def camel_to_snake_case(camel_str):
    """
    Convert a camelCase or PascalCase string to snake_case.
    
    Handles cases with letters and digits, ensuring underscores are 
    added appropriately between camelCase segments and numbers.
    
    Args:
        camel_str (str): The camelCase or PascalCase string.
    
    Returns:
        str: The snake_case version of the string.
    """
    # Add underscores before uppercase letters that are not at the start
    snake_str = re.sub(r'(?<!^)(?=[A-Z])', '_', camel_str)  # Adds underscores before capital letters
    
    # Add underscores between letters and digits, but not between digits themselves
    snake_str = re.sub(r'(?<=\D)(?=\d)', '_', snake_str)   # Adds underscores between letters and digits
    snake_str = re.sub(r'(?<=\d)(?=\D)', '_', snake_str)   # Adds underscores between digits and letters
    
    # Convert all to lowercase
    snake_str = snake_str.lower()
    
    # Remove multiple consecutive underscores
    snake_str = re.sub(r'_{2,}', '_', snake_str)
    
    # Remove trailing underscores if they exist
    snake_str = snake_str.rstrip('_')
    
    return snake_str

class CppType:
    """Enumeration for C++ data types."""
    INT = "int"
    FLOAT = "float"
    DOUBLE = "double"
    CHAR = "char"
    STRING = "std::string"

    @classmethod
    def all_types(cls):
        """Return a list of all C++ types."""
        return [cls.INT, cls.FLOAT, cls.DOUBLE, cls.CHAR, cls.STRING]


class CppMember:
    """Represents a member of a C++ class."""
    
    def __init__(self, name: str, type_name: str, value: str = ""):
        self.name = name
        self.type_name = type_name
        self.value = value;

    def __str__(self):
        """Return the string representation of the member."""
        return f"{self.type_name} {self.name}{"" if self.value == "" else "= " + self.value};"


class CppMethod:
    """Represents a method of a C++ class."""
    
    def __init__(self, name: str, return_type: str, parameters: str, body: str, access_modifier: str = "public", initializer_list: str = ""):
        self.name = name
        self.return_type = return_type
        self.parameters = parameters
        self.body = body
        self.access_modifier = access_modifier
        self.initializer_list = initializer_list

    def declaration(self) -> str:
        """Return the declaration of the method"""
        space = " " if self.return_type != "" else ""
        return f"{self.return_type}{space}{self.name}({self.parameters});"

    def get_definition(self, class_name: str) -> str:
        """Return the definition of the method with class name prepended."""
        space = " " if self.return_type != "" else ""
        initializer = f" : {self.initializer_list}" if self.initializer_list else ""
        return f"{self.return_type}{space}{class_name}::{self.name}({self.parameters}){initializer} {{\n    {self.body}\n}}"


class CppStruct:
    def __init__(self, name: str):
        self.name = name
        self.members = []
        self.methods : List[CppMethod] = []

    def add_member(self, member: CppMember):
        self.members.append(member)

    def add_method(self, method: CppMethod):
        self.methods.append(method)

    def generate_header_content(self):
        members_str = "\n    ".join(str(member) for member in self.members)

        methods_str = "\n    ".join(method.declaration() for method in self.methods )

        header_content = (
            f"struct {self.name} {{\n"
            f"    {members_str}\n"
            f"    {methods_str}\n"
            f"}};\n\n"
        )
        return header_content

    def generate_source_content(self):
        """Generate the source file content."""

        # Add method definitions to the source content with class name prepended
        source_content = "\n\n".join(method.get_definition(self.name) for method in self.methods) + "\n\n"

        return source_content

class CppClass:
    """Represents a C++ class."""
    
    def __init__(self, name: str):
        self.name = name
        self.members = []
        self.methods: List[CppMethod] = []
        # includes required for this specific class
        self.includes: List[str] = []

    def add_include(self, include: str) -> None:
        self.includes.append(include)

    def add_member(self, member: CppMember):
        """Add a member to the class."""
        self.members.append(member)

    def add_method(self, method: CppMethod):
        """Add a method to the class."""
        self.methods.append(method)

    def add_constructor(self, parameters: str, initializer_list: str = "", body: str = ""):
        """Add a constructor to the class with an optional initializer list."""
        constructor_method = CppMethod(
            name=self.name,
            return_type="",
            parameters=parameters,
            body=body,
            initializer_list=initializer_list
        )
        self.add_method(constructor_method)

    def generate_header_content(self):
        """Generate the header file content."""

        members_str = "\n    ".join(str(member) for member in self.members)

        # Separate public and private method declarations
        public_methods_str = "\n    ".join(method.declaration() for method in self.methods if method.access_modifier == "public")
        private_methods_str = "\n    ".join(method.declaration() for method in self.methods if method.access_modifier == "private")

        header_content = (
            f"class {self.name} {{\n"
            f"public:\n"
            f"    {members_str}\n"
            f"\n    {public_methods_str}\n"
            f"\nprivate:\n"
            f"    {private_methods_str}\n"
            f"}};\n\n"
        )
        return header_content

    def generate_source_content(self):
        """Generate the source file content."""
        source_content = ""

        # Add method definitions to the source content with class name prepended
        definitions_str = "\n\n".join(method.get_definition(self.name) for method in self.methods)
        source_content += definitions_str

        return source_content

    def __str__(self):
        """Return the string representation of the class."""
        members_str = "\n    ".join(str(member) for member in self.members)

        # Separate public and private method declarations for string representation
        public_methods_str = "\n    ".join(method.declaration() for method in self.methods if method.access_modifier == "public")
        private_methods_str = "\n    ".join(method.declaration() for method in self.methods if method.access_modifier == "private")

        return (
            f"class {self.name} {{\n"
            f"public:\n    {members_str}\n\n    {public_methods_str}\n"
            f"\nprivate:\n    {private_methods_str}\n"
            f"}};\n"
        )

class CppHeaderAndSource:

    def __init__(self, name: str):
        self.name = name
        self.structs: List[CppStruct] = []
        self.includes: List[str] = []
        self.classes: List[CppClass] = []

    def add_include(self, include: str) -> None:
        self.includes.append(include)

    def add_struct(self, struct: CppStruct) -> None:
        self.structs.append(struct)

    def add_class(self, cls: CppClass) -> None:
        self.classes.append(cls)

    def generate_header_content(self):
        header_file_content = ""
        guard_name = f"{camel_to_snake_case(self.name).upper()}_HPP"
        all_includes = []
        all_includes.extend(self.includes)

        header_file_content +=  f"#ifndef {guard_name}\n"
        header_file_content += f"#define {guard_name}\n\n"

        for cls in self.classes:
            all_includes.extend(cls.includes)

        header_file_content += '\n'.join(all_includes)

        for struct in self.structs:
            header_file_content += struct.generate_header_content();

        for cls in self.classes:
            header_file_content += cls.generate_header_content();

        header_file_content += f"#endif // {guard_name}"

        return header_file_content

    def generate_source_content(self):
        source_content = f"#include \"{self.name}.hpp\"\n\n"

        for struct in self.structs:
            source_content += struct.generate_source_content();

        for cls in self.classes:
            source_content += cls.generate_source_content()

        return source_content

# Example usage
if __name__ == "__main__":

    cpp_header_and_source = CppHeaderAndSource("example_file")

    cpp_struct = CppStruct("ExampleStruct")
    cpp_struct.add_member(CppMember("w", CppType.INT))
    cpp_struct.add_member(CppMember("z", CppType.INT))
    cpp_struct.add_method(CppMethod("add", "int", "", "return w + z;"))

    cpp_class = CppClass("ExampleClass")
    cpp_class.add_member(CppMember("x", CppType.INT))
    cpp_class.add_member(CppMember("y", CppType.FLOAT))
    cpp_class.add_include("#include <iostream>\n")

    # Add a constructor using the new method
    cpp_class.add_constructor("int x, float y", "x(x), y(y)")

    cpp_header_and_source.add_struct(cpp_struct)
    cpp_header_and_source.add_class(cpp_class)

    print(cpp_header_and_source.generate_header_content())
    print(cpp_header_and_source.generate_source_content())
