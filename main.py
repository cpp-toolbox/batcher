from re import sub
from cpp_utils.main import *
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
        
        cpp_struct.add_method(CppMethod("operator==", "bool", [CppParameter("other", struct_name, "const", True)], equals_body, define_in_header=True, qualifiers=["const"]))

        return cpp_struct

class ShaderBatcherCppClass:
    def __init__(self, shader_type: ShaderType, vertex_attributes : List[ShaderVertexAttributeVariable]):
        self.shader_type = shader_type
        self.vertex_attributes: List[ShaderVertexAttributeVariable] = vertex_attributes

    def get_class_name(self) -> str:
        return f"{snake_to_camel_case(self.shader_type.name)}ShaderBatcher"

    def generate_queue_draw_parameter_list(self) -> List[CppParameter]:
        # parameter_list = "const unsigned int object_id, const std::vector<unsigned int> &indices, "
        parameter_list = [
            CppParameter("object_id", "unsigned int", "const"), 
            CppParameter("indices", "std::vector<unsigned int>", "const", True)
        ]
        for vertex_attribute in self.vertex_attributes:
            data = shader_vertex_attribute_to_data[vertex_attribute]
            parameter_list.append(CppParameter(data.plural_name, f"std::vector<{data.attrib_type}>", "const", True))
            # parameter_list += f"const std::vector<{data.attrib_type}> &{data.plural_name}, "

        parameter_list.append(CppParameter("replace", "bool", "", False, "false"))
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
    glDeleteBuffers(1, &{buffer_object_var_name});"""
        return body

    def generate_queue_draw_body(self) -> str:

        def generate_sub_buffering_calls() -> str:
            lines = []
            for v in self.vertex_attributes:
                sva_data = shader_vertex_attribute_to_data[v]
                lines.append(f"glBindBuffer(GL_ARRAY_BUFFER, {sva_data.plural_name}_buffer_object);")
                lines.append(f"glBufferSubData(GL_ARRAY_BUFFER, *start_index * sizeof({sva_data.attrib_type}), {sva_data.plural_name}.size() * sizeof({sva_data.attrib_type}), {sva_data.plural_name}.data());")
                lines.append("\n")

            indentation = TAB 
            for i in range(len(lines)):
                lines[i] = indentation + lines[i]

            return '\n'.join(lines)

        body = f"""
    bool logging = false;

    object_ids_this_tick.push_back(object_id);

    bool incoming_data_is_already_cached =
        cached_object_ids_to_indices.find(object_id) != cached_object_ids_to_indices.end();

    if (incoming_data_is_already_cached and not replace) {{
        return;
    }}

    // therefore the data is either not cached, or it needs to be replaced
    // in both of those cases the data needs to be stored, so moving on:

    // if the data already exists then we need to replace
    auto metadata = fsat.get_metadata(object_id);
    if (metadata) {{
        // so mark that space as free, and it only needs to occur in the realm of metadata
        // later on we'll just clobber the real contents of the VBO which is not a problem
        fsat.remove_metadata(object_id);
    }}

    // note we use positions because that information is what gets stored into the vertex buffer objects
    // note that any other vertex data could be used as they must all have the same size
    size_t length = positions.size();
    auto start_index = fsat.find_contiguous_space(length);

    // if there's no space left we will compactify things, and try again.
    if (!start_index) {{
        fsat.compact();
        // TODO implement later when running out of space is a real issue.
        // storage.compact(tracker.get_all_metadata());
        start_index = fsat.find_contiguous_space(length);
        if (!start_index) {{
            throw std::runtime_error("not enough space even after compacting.");
        }}
    }}

    // at this point it's guarenteed that there is space for the object.
    // therefore *start_index is competely valid from now on

    std::vector<unsigned int> cached_indices_for_data;
    for (unsigned int index : indices) {{
        // note that it's guarenteed that cached_index is going to reside completely
        // within the allocated space this is because if the size of the positions vector
        // is given by N, then the indices are only allowed to be values of 0, ..., N - 1
        // then we move it up by start_index, and thus we're always within start_index + N - 1
        // which it the amount of space we found during our find_contiguous space call
        unsigned int cached_index = index + *start_index;
        cached_indices_for_data.push_back(cached_index);
    }}

    // using this one as it will replace the existing data, thus works for replacement or first time insertion.
    cached_object_ids_to_indices.insert_or_assign(object_id, cached_indices_for_data);

    // now we put that data into the graphics card
    glBindVertexArray(vertex_attribute_object);

{generate_sub_buffering_calls()}

    glBindVertexArray(0);

    // ok now we're done, update the metadata so that we know this space is used up
    fsat.add_metadata(object_id, *start_index, length);

    replaced_data_for_an_object_this_tick = true;

    if (logging) {{
        std::cout << "^^^ QUEUE_DRAW ^^^" << std::endl;
    }}
        """
        return body


    def generate_draw_everything_body(self) -> str:
        body = f"""

    bool logging = false;

    if (logging) {{
        std::cout << "VVV DRAW_EVERYTHING VVV" << std::endl;
    }}
    shader_cache.use_shader_program(ShaderType::{self.shader_type.name});
    glBindVertexArray(vertex_attribute_object);

    if (replaced_data_for_an_object_this_tick or object_ids_this_tick != object_ids_last_tick) {{
        std::vector<unsigned int> all_indices;
        for (const auto &draw_data : object_ids_this_tick) {{
            auto it = cached_object_ids_to_indices.find(draw_data);
            if (it != cached_object_ids_to_indices.end()) {{
                const std::vector<unsigned int> &cached_indices = it->second;
                all_indices.insert(all_indices.end(), cached_indices.begin(), cached_indices.end());
            }} else {{
                if (logging) {{
                    std::cerr << "draw data tried to be drawn but was not cached, look into this as it should not occur"
                              << std::endl;
                }}
            }}
        }}

        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, indices_buffer_object);
        glBufferSubData(GL_ELEMENT_ARRAY_BUFFER, 0, all_indices.size() * sizeof(unsigned int), all_indices.data());

        glDrawElements(GL_TRIANGLES, all_indices.size(), GL_UNSIGNED_INT, 0);
        object_ids_last_tick = object_ids_this_tick;
        drawn_indices_last_tick = all_indices;
    }} else {{
        glDrawElements(GL_TRIANGLES, drawn_indices_last_tick.size(), GL_UNSIGNED_INT, 0);
    }}

    glBindVertexArray(0);
    shader_cache.stop_using_shader_program();

    object_ids_this_tick.clear();
    replaced_data_for_an_object_this_tick = false;

    if (logging) {{
        std::cout << "^^^ DRAW_EVERYTHING ^^^" << std::endl;
    }}
    """

        return body

    # NOTE: this is the main entry point to generating each batcher
    def generate_cpp_class(self) -> CppClass:
        batcher_class = CppClass(self.get_class_name())

        ubo_shader_types = [
            ShaderType.CWL_V_TRANSFORMATION_UBOS_1024_WITH_SOLID_COLOR,
            ShaderType.CWL_V_TRANSFORMATION_UBOS_1024_WITH_COLORED_VERTEX,
            ShaderType.CWL_V_TRANSFORMATION_UBOS_1024_WITH_OBJECT_ID,
            ShaderType.TEXTURE_PACKER_CWL_V_TRANSFORMATION_UBOS_1024,
            ShaderType.TEXTURE_PACKER_CWL_V_TRANSFORMATION_UBOS_1024_AMBIENT_AND_DIFFUSE_LIGHTING,
            ShaderType.TEXTURE_PACKER_CWL_V_TRANSFORMATION_UBOS_1024_MULTIPLE_LIGHTS,
            ShaderType.TEXTURE_PACKER_RIGGED_AND_ANIMATED_CWL_V_TRANSFORMATION_UBOS_1024_WITH_TEXTURES_AND_MULTIPLE_LIGHTS,
            ShaderType.TEXTURE_PACKER_RIGGED_AND_ANIMATED_CWL_V_TRANSFORMATION_UBOS_1024_WITH_TEXTURES,
        ]

        is_ubo_1024_shader : bool = self.shader_type in ubo_shader_types

        if (is_ubo_1024_shader):
            batcher_class.add_member(CppMember("ltw_object_id_generator", "BoundedUniqueIDGenerator", "BoundedUniqueIDGenerator(1024)"))
            batcher_class.add_member(CppMember("ltw_matrices_gl_name", "GLuint"))
            batcher_class.add_member(CppMember("ltw_matrices[1024]", "glm::mat4"))

        batcher_class.add_member(CppMember("object_id_generator", "UniqueIDGenerator"))
        batcher_class.add_member(CppMember("shader_cache", "ShaderCache"))
        batcher_class.add_member(CppMember("vertex_attribute_object", "GLuint"))
        batcher_class.add_member(CppMember("indices_buffer_object", "GLuint"))

        # add vector for each thing this shader type has
        for vertex_attribute in self.vertex_attributes:
            va_data = shader_vertex_attribute_to_data[vertex_attribute]
            batcher_class.add_member(CppMember(f"{va_data.plural_name}_buffer_object", "GLuint"))


        batcher_class.add_member(CppMember("curr_index_buffer_offset", "unsigned int", "0"))
        batcher_class.add_member(CppMember("largest_index_used_so_far", "unsigned int", "0"))

        batcher_class.add_member(CppMember("object_ids_this_tick", f"std::vector<unsigned int>"))
        batcher_class.add_member(CppMember("object_ids_last_tick", f"std::vector<unsigned int>"))
        batcher_class.add_member(CppMember("drawn_indices_last_tick", f"std::vector<unsigned int>"));
        batcher_class.add_member(CppMember("cached_object_ids_to_indices", f"std::unordered_map<unsigned int, std::vector<unsigned int>>"))

        batcher_class.add_member(CppMember("fsat", f"FixedSizeArrayTracker"))

        batcher_class.add_member(CppMember("replaced_data_for_an_object_this_tick ", f"bool"))



        ubo_matrices_initialization = f"""
    for (int i = 0; i < 1024; ++i) {{
        ltw_matrices[i] = glm::mat4(1.0f);
    }}

    glGenBuffers(1, &ltw_matrices_gl_name);
    glBindBuffer(GL_UNIFORM_BUFFER, ltw_matrices_gl_name);
    glBufferData(GL_UNIFORM_BUFFER, sizeof(ltw_matrices), ltw_matrices, GL_STATIC_DRAW);
    glBindBufferBase(GL_UNIFORM_BUFFER, 0, ltw_matrices_gl_name);

        """
            

        batcher_class.add_constructor([CppParameter("shader_cache", "ShaderCache", "", True )], "shader_cache(shader_cache), fsat(10000000)", f"""
    { ubo_matrices_initialization if (is_ubo_1024_shader) else "" }
    glGenVertexArrays(1, &vertex_attribute_object);
    glBindVertexArray(vertex_attribute_object);
    glGenBuffers(1, &indices_buffer_object);
    // reserve space for 1 million elements, probably overkill
    const size_t initial_buffer_size = 10000000;
    {self.generate_constructor_body()}
    glBindVertexArray(0);""")
        


        batcher_class.add_method(CppMethod(f"~{self.get_class_name()}", "", [], 
                                            self.generate_deconstructor(), "public"))

        if (is_ubo_1024_shader):
            batcher_class.add_method(CppMethod("upload_ltw_matrices", "void", [], f"""
    glGenBuffers(1, &ltw_matrices_gl_name);
    glBindBuffer(GL_UNIFORM_BUFFER, ltw_matrices_gl_name);
    glBufferData(GL_UNIFORM_BUFFER, sizeof(ltw_matrices), ltw_matrices, GL_STATIC_DRAW);
    glBindBufferBase(GL_UNIFORM_BUFFER, 0, ltw_matrices_gl_name);
            """))

        # glBindBuffer(GL_UNIFORM_BUFFER, ltw_matrices_gl_name);
        # glBufferSubData(GL_UNIFORM_BUFFER, 0, sizeof(ltw_matrices), ltw_matrices);
        # glBindBuffer(GL_UNIFORM_BUFFER, 0);

        batcher_class.add_method(CppMethod("delete_object", "void", [CppParameter("object_id", "unsigned int", "const")] , 
                                            "fsat.remove_metadata(object_id); object_id_generator.reclaim_id(object_id); cached_object_ids_to_indices.erase(object_id);", "public"))

        batcher_class.add_method(CppMethod("queue_draw", "void", self.generate_queue_draw_parameter_list(), 
                                            self.generate_queue_draw_body(), "public"))

        batcher_class.add_method(CppMethod("draw_everything", "void", [], self.generate_draw_everything_body(), "public"))

        return batcher_class

class BatcherCppClassCreator:
    def __init__(self, constructed_batchers: List[str]):
        self.constructed_batchers = constructed_batchers

    def generate_cpp_class(self) -> CppClass:
        initializer_list = [] 
        batcher_class = CppClass("Batcher")
        # requested_shader_types = []

        # Add constructed batchers as members and add them to the initializer list
        for constructed_batcher_name in self.constructed_batchers:
            batcher_class.add_member(CppMember(camel_to_snake_case(constructed_batcher_name), constructed_batcher_name))
            initializer_list.append(f"{camel_to_snake_case(constructed_batcher_name)}(shader_cache)")
            # remove from end
            clip_size = len("_SHADER_BATCHER")
            shader_type = camel_to_snake_case(constructed_batcher_name)[:-clip_size].upper()
            # requested_shader_types.append(f"{TAB * 2}ShaderType::{shader_type}");

        # Add requested_shaders member
        batcher_class.add_member(CppMember("requested_shaders", "static std::vector<ShaderType>", ))

        initializer_list = ", ".join(initializer_list)

        # Add constructor with updated initializer list
        # batcher_class.add_constructor("ShaderCache& shader_cache", initializer_list, "requested_shaders = {\n" + ",\n".join(requested_shader_types) + f"\n{TAB}}};")
        batcher_class.add_constructor([CppParameter("shader_cache", "ShaderCache", "", True )], initializer_list, "")

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

            shader_batcher_header_and_source.add_include('#include <iostream>\n#include <string>\n#include "../fixed_size_array_tracker/fixed_size_array_tracker.hpp"\n#include "../sbpt_generated_includes.hpp"\n\n');

            shader_batcher = ShaderBatcherCppClass(shader_type, vertex_attributes)
            batcher_class = shader_batcher.generate_cpp_class()
            shader_batcher_header_and_source.add_class(batcher_class)

            # shader_batcher_draw_info_struct = ShaderBatcherCppStruct(shader_type, vertex_attributes)
            # struct = shader_batcher_draw_info_struct.generate_cpp_struct()
            # shader_batcher_header_and_source.add_struct(struct)

            # shader_batcher_header_and_source.add_extra_header_code(generate_hashing_code_for_draw_data(vertex_attributes, shader_type))

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


