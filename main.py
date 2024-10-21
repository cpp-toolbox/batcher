import re

def camel_to_snake_case(camel_str):
    # Add an underscore before each capital letter and convert to lowercase
    snake_str = re.sub(r'(?<!^)(?=[A-Z])', '_', camel_str).lower()
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
    
    def __init__(self, name: str, type_name: str):
        self.name = name
        self.type_name = type_name

    def __str__(self):
        """Return the string representation of the member."""
        return f"{self.type_name} {self.name};"


class CppMethod:
    """Represents a method of a C++ class."""
    
    def __init__(self, name: str, return_type: str, parameters: str, body: str, access_modifier: str = "public"):
        self.name = name
        self.return_type = return_type
        self.parameters = parameters
        self.body = body
        self.access_modifier = access_modifier

    def declaration(self):
        """Return the declaration of the method with access modifier."""
        return f"{self.access_modifier}: {self.return_type} {self.name}({self.parameters});"

    def definition(self, class_name: str):
        """Return the definition of the method with class name prepended."""
        return f"{self.return_type} {class_name}::{self.name}({self.parameters}) {{\n    {self.body}\n}}"


class CppClass:
    """Represents a C++ class."""
    
    def __init__(self, name: str):
        self.name = name
        self.members = []
        self.methods = []

    def add_member(self, member: CppMember):
        """Add a member to the class."""
        self.members.append(member)

    def add_method(self, method: CppMethod):
        """Add a method to the class."""
        self.methods.append(method)

    def generate_header(self, includes: str):
        """Generate the header file content."""
        guard_name = f"{camel_to_snake_case(self.name).upper()}_HPP"

        members_str = "\n    ".join(str(member) for member in self.members)

        # Separate public and private method declarations
        public_methods_str = "\n    ".join(method.declaration() for method in self.methods if method.access_modifier == "public")
        private_methods_str = "\n    ".join(method.declaration() for method in self.methods if method.access_modifier == "private")

        header_content = (
            f"#ifndef {guard_name}\n"
            f"#define {guard_name}\n\n"
            f"{includes}"
            f"class {self.name} {{\n"
            f"public:\n"
            f"    {members_str}\n"
            f"\n    {public_methods_str}\n"
            f"\nprivate:\n"
            f"    {private_methods_str}\n"
            f"}};\n\n"
            f"#endif // {guard_name}\n"
        )
        return header_content

    def generate_source(self):
        """Generate the source file content."""
        source_content = f"#include \"{camel_to_snake_case(self.name)}.hpp\"\n\n"

        # Add method definitions to the source content with class name prepended
        definitions_str = "\n\n".join(method.definition(self.name) for method in self.methods)
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

