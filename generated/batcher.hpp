#ifndef BATCHER_HPP
#define BATCHER_HPP

#include "absolute_position_with_solid_color_shader_batcher.hpp"
#include "transform_v_with_textures_shader_batcher.hpp"

class Batcher {
public:
    AbsolutePositionWithSolidColorShaderBatcher absolute_position_with_solid_color_shader_batcher;
    TransformVWithTexturesShaderBatcher transform_v_with_textures_shader_batcher;

    

private:
    
};

#endif // BATCHER_HPP
