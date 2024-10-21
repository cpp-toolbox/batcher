#include "transform_v_with_textures_shader_batcher.hpp"

TransformVWithTexturesShaderBatcher::TransformVWithTexturesShaderBatcher(ShaderCache& shader_cache) {
    
    shader_cache = shader_cache;
    glGenVertexArrays(1, &vertex_attribute_object);
    glBindVertexArray(vertex_attribute_object);
    glGenBuffers(1, &indices_buffer_object);
    
    glGenBuffers(1, &positions_buffer_object);
    shader_cache.configure_vertex_attributes_for_drawables_vao(vertex_attribute_object, positions_buffer_object, ShaderType::TRANSFORM_V_WITH_TEXTURES, ShaderVertexAttributeVariable::XYZ_POSITION);
           
    glGenBuffers(1, &texture_coordinates_buffer_object);
    shader_cache.configure_vertex_attributes_for_drawables_vao(vertex_attribute_object, texture_coordinates_buffer_object, ShaderType::TRANSFORM_V_WITH_TEXTURES, ShaderVertexAttributeVariable::PASSTHROUGH_TEXTURE_COORDINATE);
           
    glBindVertexArray(0);
}

TransformVWithTexturesShaderBatcher::~TransformVWithTexturesShaderBatcher() {
    glDeleteVertexArrays(1, &vertex_attribute_object);
}

void TransformVWithTexturesShaderBatcher::queue_draw(const std::vector<glm::vec3> &positions, const std::vector<glm::vec2> &texture_coordinates) {
    
    std::vector<std::vector<unsigned int>> all_indices = {indices_this_tick, indices};
    indices_this_tick = flatten_and_increment_indices(all_indices);
        
    positions_this_tick.insert(positions.end(), positions.begin(), positions.end());
           
    texture_coordinates_this_tick.insert(texture_coordinates.end(), texture_coordinates.begin(), texture_coordinates.end());
           
}

void TransformVWithTexturesShaderBatcher::draw_everything() {
    
    shader_cache.use_shader_program(ShaderType::TRANSFORM_V_WITH_TEXTURES);
    glBindVertexArray(vertex_attribute_object);

    
    glBindBuffer(GL_ARRAY_BUFFER, positions_buffer_object);
    glBufferData(GL_ARRAY_BUFFER, positions_this_tick.size() * sizeof(glm::vec3), positions_this_tick.data(), GL_STATIC_DRAW);
           
    glBindBuffer(GL_ARRAY_BUFFER, texture_coordinates_buffer_object);
    glBufferData(GL_ARRAY_BUFFER, texture_coordinates_this_tick.size() * sizeof(glm::vec2), texture_coordinates_this_tick.data(), GL_STATIC_DRAW);
           

    glDrawElements(GL_TRIANGLES, indices.size(), GL_UNSIGNED_INT, 0);
    glBindVertexArray(0);
    shader_cache.stop_using_shader_program();

    indices_this_tick.clear()
    positions_this_tick.clear();
    texture_coordinates_this_tick.clear();

    
}