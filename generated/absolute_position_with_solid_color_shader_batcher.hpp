#ifndef ABSOLUTE_POSITION_WITH_SOLID_COLOR_SHADER_BATCHER_HPP
#define ABSOLUTE_POSITION_WITH_SOLID_COLOR_SHADER_BATCHER_HPP

#include <iostream>
#include <string>
#include "../sbpt_generated_includes.hpp"

class AbsolutePositionWithSolidColorShaderBatcher {
public:
    ShaderCache shader_cache;
    GLuint vertex_attribute_object;
    GLuint indices_buffer_object;
    GLuint positions_buffer_object;
    std::vector<unsigned int> indices_this_tick;
    std::vector<glm::vec3> positions_this_tick;

    AbsolutePositionWithSolidColorShaderBatcher(ShaderCache& shader_cache);
    ~AbsolutePositionWithSolidColorShaderBatcher();
    void queue_draw(const std::vector<unsigned int> &indices, const std::vector<glm::vec3> &positions);
    void draw_everything();

private:
    
};

#endif // ABSOLUTE_POSITION_WITH_SOLID_COLOR_SHADER_BATCHER_HPP
