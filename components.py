from main import *
from dataclasses import dataclass
from batcher import VertexAttribute


@dataclass
class GLVertexAttributeConfiguration:
    components_per_vertex: str
    data_type_of_component: str
    normalize: str
    stride: str
    pointer_to_start_of_data: str

vertex_attribute_to_configuration = {
        VertexAttribute.XYZ_POSITION: GLVertexAttributeConfiguration("3", "GL_FLOAT", "GL_FALSE", "0", "(void *)0"),
        VertexAttribute.XY_POSITION: GLVertexAttributeConfiguration("2", "GL_FLOAT", "GL_FALSE", "0", "(void *)0"),
        VertexAttribute.PASSTHROUGH_NORMAL: GLVertexAttributeConfiguration("3", "GL_FLOAT", "GL_FALSE", "0", "(void *)0"),
        VertexAttribute.PASSTHROUGH_TEXTURE_COORDINATE: GLVertexAttributeConfiguration("2", "GL_FLOAT", "GL_FALSE", "0", "(void *)0"),
}

# Create the class
vertex_component_class = CppClass("VertexComponent")

# Add private members
vertex_component_class.add_member(CppMember("vertex_attribute_object", "GLuint"))
vertex_component_class.add_member(CppMember("vertex_positions_buffer_object", "GLuint"))
vertex_component_class.add_member(CppMember("vertex_positions", "std::vector<glm::vec3>"))

# Add methods
# Constructor
constructor_body = """
glGenVertexArrays(1, &vertex_attribute_object);
glGenBuffers(1, &vvertex_positions_buffer_objectertex_positions_buffer_object);
shader_cache.configure_vertex_attributes_for_drawables_vao(vertex_attribute_object, vbo_name,
                                                           ShaderType::TRANSFORM_V_WITH_SIGNED_DISTANCE_FIELD_TEXT,
                                                           ShaderVertexAttributeVariable::POSITION);
"""
vertex_component_class.add_method(CppMethod(name="VertexComponent", return_type="", parameters="ShaderType shader_type, ShaderCache &shader_cache", body=constructor_body))

# queue_draw method
queue_draw_body = """
this->vertices.insert(this->vertices.end(), vertices.begin(), vertices.end());
"""
vertex_component_class.add_method(CppMethod(name="queue_draw", return_type="void", parameters="const std::vector<glm::vec3>& vertices", body=queue_draw_body))

# bind method
bind_body = """
glBindBuffer(GL_ARRAY_BUFFER, vertex_positions_buffer_object);
glBufferData(GL_ARRAY_BUFFER, vertices.size() * sizeof(glm::vec3), vertices.data(), GL_STATIC_DRAW);
glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 3 * sizeof(float), (void*)0);
glEnableVertexAttribArray(0);
"""
vertex_component_class.add_method(CppMethod(name="bind", return_type="void", parameters="", body=bind_body))

# clear method
clear_body = """
vertices.clear();
"""
vertex_component_class.add_method(CppMethod(name="clear", return_type="void", parameters="", body=clear_body))

# Generate and print the header and source content
header_content = vertex_component_class.generate_header()
source_content = vertex_component_class.generate_source()

print("Header file content:\n")
print(header_content)
print("\nSource file content:\n")
print(source_content)
