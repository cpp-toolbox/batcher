#include "batcher.hpp"

Batcher::Batcher(ShaderCache& shader_cache) : absolute_position_with_solid_color_shader_batcher(shader_cache), transform_v_with_textures_shader_batcher(shader_cache) {
    
}