#ifndef TRANSFORM_V_WITH_TEXTURES_SHADER_BATCHER_HPP
#define TRANSFORM_V_WITH_TEXTURES_SHADER_BATCHER_HPP

#include <iostream>
#include <string>
#include "../sbpt_generated_includes.hpp"

class TransformVWithTexturesShaderBatcher {
public:
    ShaderCache shader_cache;
    GLuint vertex_attribute_object;
    GLuint indices_buffer_object;
    GLuint positions_buffer_object;
    GLuint texture_coordinates_buffer_object;
    std::vector<unsigned int> indices_this_tick;
    std::vector<glm::vec3> positions_this_tick;
    std::vector<glm::vec2> texture_coordinates_this_tick;

    TransformVWithTexturesShaderBatcher(ShaderCache& shader_cache);
    ~TransformVWithTexturesShaderBatcher();
    void queue_draw(const std::vector<unsigned int> &indices, const std::vector<glm::vec3> &positions, const std::vector<glm::vec2> &texture_coordinates);
    void draw_everything();

private:
    
};

#endif // TRANSFORM_V_WITH_TEXTURES_SHADER_BATCHER_HPP
