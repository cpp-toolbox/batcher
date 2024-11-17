from cppclass import *
from enum import Enum, auto;
from dataclasses import dataclass
from typing import List
from shader_summary import *
import argparse
import sys

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

TAB = "    "

def snake_to_camel_case(snake_str):
    components = snake_str.lower().split('_')
    return ''.join(x.title() for x in components)

def get_draw_data_struct_name(shader_type: ShaderType):
    return snake_to_camel_case(shader_type.name) + "DrawData"

class ShaderBatcherCppStruct:
    def __init__(self, shader_type: ShaderType, vertex_attributes : List[ShaderVertexAttributeVariable]):
        self.shader_type = shader_type
        self.vertex_attributes = vertex_attributes

    def generate_cpp_struct(self) -> CppStruct:

        struct_name = get_draw_data_struct_name(self.shader_type)
        cpp_struct = CppStruct(struct_name)
        cpp_struct.add_member(CppMember("indices", "std::vector<unsigned int>"))

        equals_body_comparisons = ["indices == other.indices"]

        for vertex_attribute in self.vertex_attributes:
            va_data = shader_vertex_attribute_to_data[vertex_attribute]
            cpp_struct.add_member(CppMember(f"{va_data.plural_name}", f"std::vector<{va_data.attrib_type}>"))
            equals_body_comparisons.append(f"{va_data.plural_name} == other.{va_data.plural_name}")


        equals_body = "return " + " && ".join(equals_body_comparisons) + ";"
        
        cpp_struct.add_method(CppMethod("operator==", "bool", f"const {struct_name} &other", equals_body))

        return cpp_struct



class ShaderBatcherCppClass:
    def __init__(self, shader_type: ShaderType, vertex_attributes : List[ShaderVertexAttributeVariable]):
        self.shader_type = shader_type
        self.vertex_attributes: List[ShaderVertexAttributeVariable] = vertex_attributes

    def get_class_name(self) -> str:
        return f"{snake_to_camel_case(self.shader_type.name)}ShaderBatcher"

    def generate_queue_draw_parameter_list(self) -> str:
        parameter_list = "const std::vector<unsigned int> &indices, "
        for vertex_attribute in self.vertex_attributes:
            data = shader_vertex_attribute_to_data[vertex_attribute]
            parameter_list += f"const std::vector<{data.attrib_type}> &{data.plural_name}, "
        parameter_list = parameter_list[:-2] # remove space comma
        return parameter_list

    def generate_constructor_body(self) -> str:
        body = ""
        for vertex_attribute in self.vertex_attributes:
           data = shader_vertex_attribute_to_data[vertex_attribute]
           buffer_object_var_name = f"{data.plural_name}_buffer_object"
           body += f"""
    glGenBuffers(1, &{buffer_object_var_name});
    // allocate space but don't actually buffer any data (nullptr) note that size is measured in bytes
    glBindBuffer(GL_ARRAY_BUFFER, {buffer_object_var_name});
    glBufferData(GL_ARRAY_BUFFER, initial_buffer_size * sizeof({data.attrib_type}), nullptr, GL_DYNAMIC_DRAW);
    shader_cache.configure_vertex_attributes_for_drawables_vao(vertex_attribute_object, {buffer_object_var_name}, ShaderType::{self.shader_type.name}, ShaderVertexAttributeVariable::{vertex_attribute.name});
           """
        body += f"""
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, indices_buffer_object);
    glBufferData(GL_ELEMENT_ARRAY_BUFFER, initial_buffer_size * sizeof(unsigned int), nullptr, GL_DYNAMIC_DRAW);
    """
        return body

    def generate_deconstructor(self) -> str:
        body = f"""
    glDeleteVertexArrays(1, &vertex_attribute_object);
    glDeleteBuffers(1, &indices_buffer_object);
    """
        for vertex_attribute in self.vertex_attributes:
           data = shader_vertex_attribute_to_data[vertex_attribute]
           buffer_object_var_name = f"{data.plural_name}_buffer_object"
           body += f"""
    glDeleteBuffers(1, &{buffer_object_var_name});
           """
        return body

    def generate_queue_draw_body(self) -> str:

        def generate_sub_buffering_calls() -> str:
            lines = []
            for v in self.vertex_attributes:
                sva_data = shader_vertex_attribute_to_data[v]
                lines.append(f"glBindBuffer(GL_ARRAY_BUFFER, {sva_data.plural_name}_buffer_object);")
                lines.append(f"glBufferSubData(GL_ARRAY_BUFFER, curr_{sva_data.singular_name}_buffer_offset * sizeof({sva_data.attrib_type}), {sva_data.plural_name}.size() * sizeof({sva_data.attrib_type}), {sva_data.plural_name}.data());")
                lines.append(f"curr_{sva_data.singular_name}_buffer_offset += {sva_data.plural_name}.size();")
                lines.append("\n")

            indentation = TAB * 2
            for i in range(len(lines)):
                lines[i] = indentation + lines[i]

            return '\n'.join(lines)

        body = f"""
    {get_draw_data_struct_name(self.shader_type)} new_data = {{indices, {", ".join([shader_vertex_attribute_to_data[v].plural_name for v in self.vertex_attributes])}}};


    // Check if it's already cached
    auto cached_pos_it = std::find(cached_draw_data.begin(), cached_draw_data.end(), new_data);
    if (cached_pos_it != cached_draw_data.end()) {{
        // It's cached, but not yet in the set of things to draw this tick
        auto draw_it = std::find(draw_data_this_tick.begin(),
                                 draw_data_this_tick.end(), new_data);
        if (draw_it == draw_data_this_tick.end()) {{
            draw_data_this_tick.push_back(new_data);
        }}
    }} else {{

        auto data_with_relative_indices = new_data;
        unsigned int largest_index_in_current_data = 0;

        // Adjust indices and find the largest index in the current data
        for (unsigned int &index : data_with_relative_indices.indices) {{
            index += largest_index_used_so_far;
            if (index > largest_index_in_current_data) {{
                largest_index_in_current_data = index;
            }}
        }}

        // suppose the above indices has 0, 1, 2, 3 in some order, and the largest index so far was equal to
        // 72, then the the largest index so far would now be 75 as it reaches it, but we need to make sure on the next
        // iteration that we don't collide with 75 again, so +1, (collision happens if there is a 0 index)
        largest_index_used_so_far = largest_index_in_current_data + 1;

        glBindVertexArray(vertex_attribute_object);

        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, indices_buffer_object);
        glBufferSubData(GL_ELEMENT_ARRAY_BUFFER, curr_index_buffer_offset * sizeof(unsigned int), data_with_relative_indices.indices.size() * sizeof(unsigned int), data_with_relative_indices.indices.data());
        curr_index_buffer_offset +=  data_with_relative_indices.indices.size(); 

{generate_sub_buffering_calls()}

        glBindVertexArray(0);

        cached_draw_data.push_back(new_data);
        draw_data_this_tick.push_back(data_with_relative_indices);
    }}

        """
        return body

    def generate_draw_everything_clear_code(self) -> str:
        body = "indices_this_tick.clear();\n"
        for vertex_attribute in self.vertex_attributes:
           data = shader_vertex_attribute_to_data[vertex_attribute]
           body += f"    {data.plural_name}_this_tick.clear();\n"
        return body

    def generate_queue_bind_body(self) -> str:
        body = ""
        for vertex_attribute in self.vertex_attributes:
           data = shader_vertex_attribute_to_data[vertex_attribute]
           body += f"   {data.singular_name}_component.bind();\n"
        return body

    def generate_draw_everything_body(self) -> str:
        body = f"""
    shader_cache.use_shader_program(ShaderType::{self.shader_type.name});
    glBindVertexArray(vertex_attribute_object);

    // Concatenate all indices into a single vector for drawing
    std::vector<unsigned int> all_indices;
    for (const auto &draw_data : draw_data_this_tick) {{
        const std::vector<unsigned int> &indices = draw_data.indices;
        all_indices.insert(all_indices.end(), indices.begin(), indices.end());
    }}

    // TODO we probably actually have to do something with indices here...

    glDrawElements(GL_TRIANGLES, all_indices.size(), GL_UNSIGNED_INT, 0);
    glBindVertexArray(0);
    shader_cache.stop_using_shader_program();
    """

        return body

    def generate_cpp_class(self) -> CppClass:
        # Create the Batcher class
        batcher_class = CppClass(self.get_class_name())

        batcher_class.add_member(CppMember("shader_cache", "ShaderCache"))
        batcher_class.add_member(CppMember("vertex_attribute_object", "GLuint"))
        batcher_class.add_member(CppMember("indices_buffer_object", "GLuint"))
        # add vector for each thing this shader type has
        for vertex_attribute in self.vertex_attributes:
            va_data = shader_vertex_attribute_to_data[vertex_attribute]
            batcher_class.add_member(CppMember(f"{va_data.plural_name}_buffer_object", "GLuint"))


        batcher_class.add_member(CppMember("curr_index_buffer_offset", "unsigned int", "0"))
        batcher_class.add_member(CppMember("largest_index_used_so_far", "unsigned int", "0"))
        for vertex_attribute in self.vertex_attributes:
            va_data = shader_vertex_attribute_to_data[vertex_attribute]
            batcher_class.add_member(CppMember(f"curr_{va_data.singular_name}_buffer_offset", "unsigned int", "0"))

        batcher_class.add_member(CppMember("draw_data_this_tick", f"std::vector<{get_draw_data_struct_name(self.shader_type)}>"))
        batcher_class.add_member(CppMember("cached_draw_data", f"std::vector<{get_draw_data_struct_name(self.shader_type)}>"))

        batcher_class.add_constructor("ShaderCache& shader_cache", "shader_cache(shader_cache)", f"""
    glGenVertexArrays(1, &vertex_attribute_object);
    glBindVertexArray(vertex_attribute_object);
    glGenBuffers(1, &indices_buffer_object);
    // reserve space for 1 million elements, probably overkill
    const size_t initial_buffer_size = 10000000;
    {self.generate_constructor_body()}
    glBindVertexArray(0);""")
        


        batcher_class.add_method(CppMethod(f"~{self.get_class_name()}", "", "", 
                                            self.generate_deconstructor(), "public"))

        batcher_class.add_method(CppMethod("queue_draw", "void", self.generate_queue_draw_parameter_list(), 
                                            self.generate_queue_draw_body(), "public"))

        # Add draw method
        batcher_class.add_method(CppMethod("draw_everything", "void", "", self.generate_draw_everything_body(), "public"))

        return batcher_class

class BatcherCppClassCreator:
    def __init__(self, constructed_batchers: List[str]):
        self.constructed_batchers = constructed_batchers

    def generate_cpp_class(self) -> CppClass:
        initializer_list = [] 
        batcher_class = CppClass("Batcher")
        requested_shader_types = []

        # Add constructed batchers as members and add them to the initializer list
        for constructed_batcher_name in self.constructed_batchers:
            batcher_class.add_member(CppMember(camel_to_snake_case(constructed_batcher_name), constructed_batcher_name))
            initializer_list.append(f"{camel_to_snake_case(constructed_batcher_name)}(shader_cache)")
            # remove from end
            clip_size = len("_SHADER_BATCHER")
            shader_type = camel_to_snake_case(constructed_batcher_name)[:-clip_size].upper()
            requested_shader_types.append(f"{TAB * 2}ShaderType::{shader_type}");

        # Add requested_shaders member
        batcher_class.add_member(CppMember("requested_shaders", "std::vector<ShaderType>", "{\n" + ",\n".join(requested_shader_types) + f"\n{TAB}}}"))

        initializer_list = ", ".join(initializer_list)

        # Add constructor with updated initializer list
        batcher_class.add_constructor("ShaderCache& shader_cache", initializer_list, "")

        return batcher_class
    
def list_available_shaders(shader_to_used_vertex_attribute_variables):
    print("Available Shaders:")
    shader_list = list(shader_to_used_vertex_attribute_variables.keys())
    for i, shader_type in enumerate(shader_list):
        print(f"{i + 1}. {shader_type.name}")

    selected_indices = input("Enter the numbers of the shaders you want to generate, separated by spaces: ").split()
    selected_shaders = [shader_list[int(index) - 1] for index in selected_indices if index.isdigit()]
    
    print("\nYou have selected the following shaders:")
    for shader in selected_shaders:
        print(f"- {shader.name}")
    
    confirm = input("Are you okay with this selection? (y/n): ")
    if confirm.lower() != 'y':
        return list_available_shaders(shader_to_used_vertex_attribute_variables)  # Re-run selection if not confirmed
    return selected_shaders
    
import os 
import shutil

def wipe_generated_directory():
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Define the path for the 'generated' directory relative to the script's location
    generated_dir = os.path.join(script_dir, 'generated')
    
    # Remove 'generated' if it exists and recreate it
    if os.path.exists(generated_dir):
        shutil.rmtree(generated_dir)
    os.makedirs(generated_dir)

def read_config_file(config_file):
    """Read the configuration file and return a list of ShaderType enums after validation."""
    with open(config_file, 'r') as file:
        shader_names = [line.strip() for line in file if line.strip()]
    
    return validate_shader_names(shader_names)

def validate_shader_names(shader_names):
    """Validate shader names and return a list of corresponding ShaderType enums."""
    valid_shader_names = {shader.name.lower(): shader for shader in ShaderType}  # Map enum names to their values

    selected_shaders = []  # This will hold the valid ShaderType enums

    for shader_name in shader_names:
        formatted_shader_name = shader_name.lower()  # Convert input to lowercase
        if formatted_shader_name not in valid_shader_names:
            print(f"Error: '{shader_name}' is not a valid shader type.")
            exit(1)  # Stop execution if an invalid shader name is found
        
        # Append the corresponding ShaderType enum to the list
        selected_shaders.append(valid_shader_names[formatted_shader_name])

    print("All shader names are valid.")
    return selected_shaders  # Return the list of ShaderType enums

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Generate C++ shader batcher classes.')
    parser.add_argument('--generate-config', '-gc', action='store_true',
                        help='Generate a config file for the requested shaders.')
    parser.add_argument('--config-file', '-c', type=str,
                        help='Path to the configuration file to read from.')
    parser.add_argument('--config-file-output-dir', '-cfod', type=str, default='.',
                        help='Directory to save the generated config file (default: current directory).')

    args = parser.parse_args()


    if args.generate_config:
        selected_shaders = list_available_shaders(shader_to_used_vertex_attribute_variables)
        config_file_path = os.path.join(args.config_file_output_dir, '.requested_shaders.txt')
        with open(config_file_path, 'w') as config_file:
            for shader in selected_shaders:
                shader_name = str(shader).split('.')[-1].lower()
                config_file.write(f"{shader_name}\n")
        print(f"Configuration written to {config_file_path}")
    else:

        if args.config_file:
            if not os.path.exists(args.config_file):
                print(f"Configuration file {args.config_file} not found.")
                sys.exit(1)

            selected_shaders = read_config_file(args.config_file)
            print(f"Selected shaders from config file: {selected_shaders}")
        else:
            selected_shaders = list_available_shaders(shader_to_used_vertex_attribute_variables)

        constructed_class_names: List[str] = []
        constructed_header_files: List[str] = []

        wipe_generated_directory()

        # Get the directory where the script exists
        script_directory = os.path.dirname(os.path.abspath(__file__)) + "/generated"


        for shader_type, vertex_attributes in shader_to_used_vertex_attribute_variables.items():


            if shader_type not in selected_shaders:
                continue


            header_file = f"{shader_type.name.lower()}_shader_batcher.hpp"
            constructed_header_files.append(header_file)

            # Create file paths relative to the script's directory
            header_filename = os.path.join(script_directory, f"{shader_type.name.lower()}_shader_batcher.hpp")
            source_filename = os.path.join(script_directory, f"{shader_type.name.lower()}_shader_batcher.cpp")

            shader_batcher_header_and_source = CppHeaderAndSource(f"{shader_type.name.lower()}_shader_batcher")

            shader_batcher_header_and_source.add_include('#include <iostream>\n#include <string>\n#include "../sbpt_generated_includes.hpp"\n\n');

            shader_batcher = ShaderBatcherCppClass(shader_type, vertex_attributes)
            batcher_class = shader_batcher.generate_cpp_class()
            shader_batcher_header_and_source.add_class(batcher_class)

            shader_batcher_draw_info_struct = ShaderBatcherCppStruct(shader_type, vertex_attributes)
            struct = shader_batcher_draw_info_struct.generate_cpp_struct()
            shader_batcher_header_and_source.add_struct(struct)

            source_content = shader_batcher_header_and_source.generate_source_content()
            header_content = shader_batcher_header_and_source.generate_header_content()

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

        # File paths for the main batcher class
        header_filename = os.path.join(script_directory, f"batcher.hpp")
        source_filename = os.path.join(script_directory, f"batcher.cpp")

        include_statements = "\n".join([f'#include "{header_file}"' for header_file in constructed_header_files]) + "\n\n"

        batcher_class.add_include(include_statements);

        batcher_header_and_source = CppHeaderAndSource("batcher")
        batcher_header_and_source.add_class(batcher_class)

        header_content = batcher_header_and_source.generate_header_content()
        source_content = batcher_header_and_source.generate_source_content()

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

