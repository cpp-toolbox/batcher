from main import *
from enum import Enum, auto;
from dataclasses import dataclass
from typing import List

class VertexAttribute(Enum):
    INDEX = auto()
    XYZ_POSITION = auto()
    XY_POSITION = auto()
    PASSTHROUGH_TEXTURE_COORDINATE = auto()
    PASSTHROUGH_RGB_COLOR = auto()
    PASSTHROUGH_NORMAL = auto()

class ShaderType(Enum):
    ABSOLUTE_POSITION_WITH_SOLID_COLOR = auto()
    TRANSFORM_V_WITH_TEXTURES = auto()

@dataclass
class VertexAttributeData:
    singular_name: str
    plural_name: str
    attrib_type: str

shader_type_to_vertex_attributes = {
    ShaderType.ABSOLUTE_POSITION_WITH_SOLID_COLOR : [VertexAttribute.XYZ_POSITION],
    ShaderType.TRANSFORM_V_WITH_TEXTURES : [VertexAttribute.XYZ_POSITION, VertexAttribute.PASSTHROUGH_TEXTURE_COORDINATE],
}


vertex_attribute_to_data = {
    VertexAttribute.INDEX: VertexAttributeData("index", "indices", "unsigned int"),
    VertexAttribute.XYZ_POSITION: VertexAttributeData("position", "positions", "glm::vec3"),
    VertexAttribute.XY_POSITION: VertexAttributeData("xy_position", "xy_positions", "glm::vec2"),
    VertexAttribute.PASSTHROUGH_TEXTURE_COORDINATE: VertexAttributeData("texture_coordinate", "texture_coordinates", "glm::vec2"),
    VertexAttribute.PASSTHROUGH_RGB_COLOR: VertexAttributeData("color", "colors", "glm::vec2"),
}

constructor_body_template = """
glGenVertexArrays(1, &vertex_attribute_object);
glBindVertexArray(vertex_attribute_object);

REPLACE_ME

glBindVertexArray(0);
"""

destructor_body_template = """
glGenVertexArrays(1, &vertex_attribute_object);
glBindVertexArray(vertex_attribute_object);

REPLACE_ME

glBindVertexArray(0);
"""

def snake_to_camel_case(snake_str):
    components = snake_str.lower().split('_')
    return ''.join(x.title() for x in components)

class ShaderBatcherCppClass:
    def __init__(self, shader_type: ShaderType, vertex_attributes : List[VertexAttribute]):
        self.shader_type = shader_type
        self.vertex_attributes = vertex_attributes

    def get_class_name(self) -> str:
        return f"{snake_to_camel_case(self.shader_type.name)}ShaderBatcher"

    def generate_queue_draw_parameter_list(self) -> str:
        parameter_list = "const std::vector<unsigned int> &indices, "
        for vertex_attribute in self.vertex_attributes:
            data = vertex_attribute_to_data[vertex_attribute]
            parameter_list += f"const std::vector<{data.attrib_type}> &{data.plural_name}, "
        parameter_list = parameter_list[:-2] # remove space comma
        return parameter_list

    def generate_constructor_body(self) -> str:
        body = ""
        for vertex_attribute in self.vertex_attributes:
           data = vertex_attribute_to_data[vertex_attribute]
           buffer_object_var_name = f"{data.plural_name}_buffer_object"
           body += f"""
    glGenBuffers(1, &{buffer_object_var_name});
    shader_cache.configure_vertex_attributes_for_drawables_vao(vertex_attribute_object, {buffer_object_var_name}, ShaderType::{self.shader_type.name}, ShaderVertexAttributeVariable::{vertex_attribute.name});
           """
        return body

    def generate_queue_draw_body(self) -> str:
        body = """
    std::vector<std::vector<unsigned int>> all_indices = {indices_this_tick, indices};
    indices_this_tick = flatten_and_increment_indices(all_indices);
        """
        for vertex_attribute in self.vertex_attributes:
           data = vertex_attribute_to_data[vertex_attribute]
           body += f"""
    {data.plural_name}_this_tick.insert({data.plural_name}_this_tick.end(), {data.plural_name}.begin(), {data.plural_name}.end());
           """
        return body

    def generate_draw_everything_clear_code(self) -> str:
        body = "indices_this_tick.clear();\n"
        for vertex_attribute in self.vertex_attributes:
           data = vertex_attribute_to_data[vertex_attribute]
           body += f"    {data.plural_name}_this_tick.clear();\n"
        return body

    def generate_queue_bind_body(self) -> str:
        body = ""
        for vertex_attribute in self.vertex_attributes:
           data = vertex_attribute_to_data[vertex_attribute]
           body += f"   {data.singular_name}_component.bind();\n"
        return body

    def generate_draw_everything_body(self) -> str:
        body = """
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, indices_buffer_object);
    glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices_this_tick.size() * sizeof(unsigned int), indices_this_tick.data(), GL_STATIC_DRAW);
    """
        for vertex_attribute in self.vertex_attributes:
           data = vertex_attribute_to_data[vertex_attribute]
           body += f"""
    glBindBuffer(GL_ARRAY_BUFFER, {data.plural_name}_buffer_object);
    glBufferData(GL_ARRAY_BUFFER, {data.plural_name}_this_tick.size() * sizeof({data.attrib_type}), {data.plural_name}_this_tick.data(), GL_STATIC_DRAW);
           """
        return body

    def generate_cpp_class(self) -> CppClass:
        # Create the Batcher class
        batcher_class = CppClass(self.get_class_name())

        batcher_class.add_member(CppMember("shader_cache", "ShaderCache"))
        batcher_class.add_member(CppMember("vertex_attribute_object", "GLuint"))
        batcher_class.add_member(CppMember("indices_buffer_object", f"GLuint"))
        # add vector for each thing this shader type has
        for vertex_attribute in self.vertex_attributes:
            va_data = vertex_attribute_to_data[vertex_attribute]
            batcher_class.add_member(CppMember(f"{va_data.plural_name}_buffer_object", "GLuint"))

        batcher_class.add_member(CppMember("indices_this_tick", f"std::vector<unsigned int>"))
        for vertex_attribute in self.vertex_attributes:
            va_data = vertex_attribute_to_data[vertex_attribute]
            batcher_class.add_member(CppMember(f"{va_data.plural_name}_this_tick", f"std::vector<{va_data.attrib_type}>"))

        batcher_class.add_constructor("ShaderCache& shader_cache", "shader_cache(shader_cache)", f"""
    glGenVertexArrays(1, &vertex_attribute_object);
    glBindVertexArray(vertex_attribute_object);
    glGenBuffers(1, &indices_buffer_object);
    {self.generate_constructor_body()}
    glBindVertexArray(0);""")
        

        batcher_class.add_method(CppMethod(f"~{self.get_class_name()}", "", "", 
                                            "glDeleteVertexArrays(1, &vertex_attribute_object);", "public"))

        batcher_class.add_method(CppMethod("queue_draw", "void", self.generate_queue_draw_parameter_list(), 
                                            self.generate_queue_draw_body(), "public"))

        # Add draw method
        batcher_class.add_method(CppMethod("draw_everything", "void", "", f"""
    shader_cache.use_shader_program(ShaderType::{self.shader_type.name});
    glBindVertexArray(vertex_attribute_object);

    {self.generate_draw_everything_body()}

    glDrawElements(GL_TRIANGLES, indices_this_tick.size(), GL_UNSIGNED_INT, 0);
    glBindVertexArray(0);
    shader_cache.stop_using_shader_program();

    {self.generate_draw_everything_clear_code()}
    """, "public"))

        return batcher_class

class BatcherCppClassCreator:
    def __init__(self, constructed_batchers: List[str]):
        self.constructed_batchers = constructed_batchers

    def generate_cpp_class(self):
        initializer_list = [] 
        batcher_class = CppClass("Batcher")
        for constructed_batcher_name in self.constructed_batchers:
            batcher_class.add_member(CppMember(camel_to_snake_case(constructed_batcher_name), constructed_batcher_name))
            initializer_list.append(f"{camel_to_snake_case(constructed_batcher_name)}(shader_cache)")

        initializer_list = ", ".join(initializer_list)


        batcher_class.add_constructor("ShaderCache& shader_cache", initializer_list, "")

        return batcher_class
    
    

if __name__ == "__main__":

    constructed_class_names: List[str] = []
    constructed_header_files: List[str] = []

    for shader_type, vertex_attributes in shader_type_to_vertex_attributes.items():

        shader_batcher = ShaderBatcherCppClass(shader_type, vertex_attributes)
        batcher_class = shader_batcher.generate_cpp_class()

        # Generate the header and source file content
        header_content = batcher_class.generate_header(includes = '#include <iostream>\n#include <string>\n#include "../sbpt_generated_includes.hpp"\n\n')
        source_content = batcher_class.generate_source()

        header_file = f"{shader_type.name.lower()}_shader_batcher.hpp"
        constructed_header_files.append(header_file)
        
        header_filename = f"generated/{shader_type.name.lower()}_shader_batcher.hpp"
        source_filename = f"generated/{shader_type.name.lower()}_shader_batcher.cpp"

        # Write the header content to the header file
        with open(header_filename, 'w') as header_file:
            header_file.write(header_content)

        # Write the source content to the source file
        with open(source_filename, 'w') as source_file:
            source_file.write(source_content)

        # Optional: Print confirmation message
        print(f"Header written to {header_filename}")
        print(f"Source written to {source_filename}")
        constructed_class_names.append(shader_batcher.get_class_name())

    batcher_cpp_class_creator = BatcherCppClassCreator(constructed_class_names)
    batcher_class = batcher_cpp_class_creator.generate_cpp_class()

    header_filename = f"generated/batcher.hpp"
    source_filename = f"generated/batcher.cpp"

    include_statements = "\n".join([f'#include "{header_file}"' for header_file in constructed_header_files]) + "\n\n"

    header_content = batcher_class.generate_header(include_statements)
    source_content = batcher_class.generate_source()

    # Write the header content to the header file
    with open(header_filename, 'w') as header_file:
        header_file.write(header_content)

    # Write the source content to the source file
    with open(source_filename, 'w') as source_file:
        source_file.write(source_content)

    # Optional: Print confirmation message
    print(f"Header written to {header_filename}")
    print(f"Source written to {source_filename}")

    # # Print the generated C++ Batcher class
    # print("Header Content:\n")
    # print(header_content)
    #
    # print("Source Content:\n")
    # print(source_content)

