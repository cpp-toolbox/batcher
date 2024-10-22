#include "absolute_position_with_solid_color_shader_batcher.hpp"

AbsolutePositionWithSolidColorShaderBatcher::AbsolutePositionWithSolidColorShaderBatcher(ShaderCache& shader_cache) : shader_cache(shader_cache) {
    
    glGenVertexArrays(1, &vertex_attribute_object);
    glBindVertexArray(vertex_attribute_object);
    glGenBuffers(1, &indices_buffer_object);
    
    glGenBuffers(1, &positions_buffer_object);
    shader_cache.configure_vertex_attributes_for_drawables_vao(vertex_attribute_object, positions_buffer_object, ShaderType::ABSOLUTE_POSITION_WITH_SOLID_COLOR, ShaderVertexAttributeVariable::XYZ_POSITION);
           
    glBindVertexArray(0);
}

AbsolutePositionWithSolidColorShaderBatcher::~AbsolutePositionWithSolidColorShaderBatcher() {
    glDeleteVertexArrays(1, &vertex_attribute_object);
}

void AbsolutePositionWithSolidColorShaderBatcher::queue_draw(const std::vector<unsigned int> &indices, const std::vector<glm::vec3> &positions) {
    
    std::vector<std::vector<unsigned int>> all_indices = {indices_this_tick, indices};
    indices_this_tick = flatten_and_increment_indices(all_indices);
        
    positions_this_tick.insert(positions_this_tick.end(), positions.begin(), positions.end());
           
}

void AbsolutePositionWithSolidColorShaderBatcher::draw_everything() {
    
    shader_cache.use_shader_program(ShaderType::ABSOLUTE_POSITION_WITH_SOLID_COLOR);
    glBindVertexArray(vertex_attribute_object);

    
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, indices_buffer_object);
    glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices_this_tick.size() * sizeof(unsigned int), indices_this_tick.data(), GL_STATIC_DRAW);
    
    glBindBuffer(GL_ARRAY_BUFFER, positions_buffer_object);
    glBufferData(GL_ARRAY_BUFFER, positions_this_tick.size() * sizeof(glm::vec3), positions_this_tick.data(), GL_STATIC_DRAW);
           

    glDrawElements(GL_TRIANGLES, indices_this_tick.size(), GL_UNSIGNED_INT, 0);
    glBindVertexArray(0);
    shader_cache.stop_using_shader_program();

    indices_this_tick.clear();
    positions_this_tick.clear();

    
}