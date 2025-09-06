from re import sub
from cpp_utils.main import *
from fs_utils.main import *
from enum import Enum, auto
from dataclasses import dataclass
from typing import List, Dict
from shader_summary import *
import argparse
import sys

# NOTE: this entire thing should be entirely be done in cpp one day, a long time away

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
    components = snake_str.lower().split("_")
    return "".join(x.title() for x in components)


def get_draw_data_struct_name(shader_type: ShaderType):
    return snake_to_camel_case(shader_type.name) + "DrawData"


class DrawInfo(Enum):
    INDEXED_VERTEX_POSITIONS = "draw_info::IndexedVertexPositions"

    IVPTEXTURED = "draw_info::IVPTextured"
    IVPCOLOR = "draw_info::IVPColor"

    IVPNORMALS = "draw_info::IVPNormals"
    IVPNCOLOR = "draw_info::IVPNColor"
    IVPNTEXTURED = "draw_info::IVPNTextured"


# NOTE not all of them are here
draw_info_struct_hierarchy = {
    DrawInfo.INDEXED_VERTEX_POSITIONS: {
        DrawInfo.IVPNORMALS: {DrawInfo.IVPNCOLOR: {}, DrawInfo.IVPNTEXTURED: {}},
        DrawInfo.IVPTEXTURED: {},
        DrawInfo.IVPCOLOR: {},
    }
}

shader_vertex_attribute_variables_to_valid_draw_info_structs: Dict[
    frozenset[ShaderVertexAttributeVariable], DrawInfo
] = {
    frozenset(
        {ShaderVertexAttributeVariable.XYZ_POSITION}
    ): DrawInfo.INDEXED_VERTEX_POSITIONS,
    frozenset(
        {
            ShaderVertexAttributeVariable.XYZ_POSITION,
            ShaderVertexAttributeVariable.PASSTHROUGH_NORMAL,
        }
    ): DrawInfo.IVPNORMALS,
    frozenset(
        {
            ShaderVertexAttributeVariable.XYZ_POSITION,
            ShaderVertexAttributeVariable.PASSTHROUGH_RGB_COLOR,
        }
    ): DrawInfo.IVPCOLOR,
    frozenset(
        {
            ShaderVertexAttributeVariable.XYZ_POSITION,
            ShaderVertexAttributeVariable.PASSTHROUGH_RGB_COLOR,
            ShaderVertexAttributeVariable.PASSTHROUGH_NORMAL,
        }
    ): DrawInfo.IVPNCOLOR,
}

ivp_param: CppParameter = CppParameter(
    "ivp",
    DrawInfo.INDEXED_VERTEX_POSITIONS.value,
    "",
)
ivp_param_ref: CppParameter = CppParameter(
    "ivp", DrawInfo.INDEXED_VERTEX_POSITIONS.value, "", True
)

ivpn_param: CppParameter = CppParameter(
    "ivpn",
    DrawInfo.IVPNORMALS.value,
    "",
)
ivpn_param_ref: CppParameter = CppParameter("ivpn", DrawInfo.IVPNORMALS.value, "", True)

ivpc_param: CppParameter = CppParameter(
    "ivpc",
    DrawInfo.IVPCOLOR.value,
    "",
)
ivpc_param_ref: CppParameter = CppParameter("ivpc", DrawInfo.IVPCOLOR.value, "", True)

ivpnc_param: CppParameter = CppParameter(
    "ivpnc",
    DrawInfo.IVPNCOLOR.value,
    "",
)
ivpnc_param_ref: CppParameter = CppParameter(
    "ivpnc", DrawInfo.IVPNCOLOR.value, "", True
)

ivpX_struct_to_param_ref: Dict[DrawInfo, CppParameter] = {
    DrawInfo.INDEXED_VERTEX_POSITIONS: ivp_param_ref,
    DrawInfo.IVPNORMALS: ivpn_param_ref,
    DrawInfo.IVPCOLOR: ivpc_param_ref,
    DrawInfo.IVPNCOLOR: ivpnc_param_ref,
}

# NOTE: in the future these should not exist, there should be a generic hierarchy and then a way to produce a parameter of that type easily.
ivpX_param_to_superclass_params: Dict[CppParameter, List[CppParameter]] = {
    ivp_param: [ivp_param, ivpn_param, ivpc_param, ivpnc_param],
    ivpn_param: [ivpn_param, ivpnc_param],
    ivpc_param: [ivpc_param, ivpnc_param],
    ivpnc_param: [ivpnc_param],
}

ivpX_param_ref_to_superclass_param_refs: Dict[CppParameter, List[CppParameter]] = {
    ivp_param_ref: [ivp_param_ref, ivpn_param_ref, ivpc_param_ref, ivpnc_param_ref],
    ivpn_param_ref: [ivpn_param_ref, ivpnc_param_ref],
    ivpc_param_ref: [ivpc_param_ref, ivpnc_param_ref],
    ivpnc_param_ref: [ivpnc_param_ref],
}


class ShaderBatcherCppStruct:
    def __init__(
        self,
        shader_type: ShaderType,
        vertex_attributes: List[ShaderVertexAttributeVariable],
    ):
        self.shader_type = shader_type
        self.vertex_attributes = vertex_attributes

    def generate_cpp_struct(self) -> CppStruct:

        struct_name = get_draw_data_struct_name(self.shader_type)
        cpp_struct = CppStruct(struct_name)
        cpp_struct.add_member(CppMember("indices", "std::vector<unsigned int>"))

        equals_body_comparisons = ["indices == other.indices"]

        for vertex_attribute in self.vertex_attributes:
            va_data = shader_vertex_attribute_to_data[vertex_attribute]
            cpp_struct.add_member(
                CppMember(
                    f"{va_data.plural_name}", f"std::vector<{va_data.attrib_type}>"
                )
            )
            equals_body_comparisons.append(
                f"{va_data.plural_name} == other.{va_data.plural_name}"
            )

        equals_body = "return " + " && ".join(equals_body_comparisons) + ";"

        cpp_struct.add_method(
            CppMethod(
                "operator==",
                "bool",
                [CppParameter("other", struct_name, "const", True)],
                equals_body,
                define_in_header=True,
                qualifiers=["const"],
            )
        )

        return cpp_struct


class ShaderBatcherCppClass:

    is_ubo_shader: bool
    num_elements_in_buffer: int

    def __init__(
        self,
        shader_type: ShaderType,
        num_elements_in_buffer: int,
        vertex_attributes: List[ShaderVertexAttributeVariable],
    ):
        self.shader_type: ShaderType = shader_type
        self.vertex_attributes: List[ShaderVertexAttributeVariable] = vertex_attributes
        self.is_ubo_shader = (
            ShaderVertexAttributeVariable.LOCAL_TO_WORLD_INDEX in self.vertex_attributes
        )
        self.num_elements_in_buffer = num_elements_in_buffer

    def get_class_name(self) -> str:
        return f"{snake_to_camel_case(self.shader_type.name)}ShaderBatcher"

    def get_associated_draw_info_struct(self) -> Optional[DrawInfo]:
        all_shader_vertex_attributes: frozenset[ShaderVertexAttributeVariable] = (
            frozenset(
                [
                    va
                    for va in self.vertex_attributes
                    if va != ShaderVertexAttributeVariable.LOCAL_TO_WORLD_INDEX
                ]
            )
        )
        if (
            all_shader_vertex_attributes
            in shader_vertex_attribute_variables_to_valid_draw_info_structs
        ):
            associated_draw_info_struct: DrawInfo = (
                shader_vertex_attribute_variables_to_valid_draw_info_structs[
                    all_shader_vertex_attributes
                ]
            )
            return associated_draw_info_struct
        else:
            return None

    def generate_queue_draw_parameter_list(self) -> List[CppParameter]:
        # parameter_list = "const unsigned int object_id, const std::vector<unsigned int> &indices, "
        parameter_list = [
            CppParameter("object_id", "unsigned int", "const"),
            CppParameter("indices", "std::vector<unsigned int>", "const", True),
        ]
        for vertex_attribute in self.vertex_attributes:
            data = shader_vertex_attribute_to_data[vertex_attribute]
            parameter_list.append(
                CppParameter(
                    data.plural_name, f"std::vector<{data.attrib_type}>", "const", True
                )
            )
            # parameter_list += f"const std::vector<{data.attrib_type}> &{data.plural_name}, "

        parameter_list.append(CppParameter("replace", "bool", "", False, "false"))
        return parameter_list

    def generate_cache_parameter_list(self) -> List[CppParameter]:
        # parameter_list = "const unsigned int object_id, const std::vector<unsigned int> &indices, "
        parameter_list = [
            CppParameter("object_id", "unsigned int", "const"),
            CppParameter("indices", "std::vector<unsigned int>", "const", True),
        ]
        for vertex_attribute in self.vertex_attributes:
            data = shader_vertex_attribute_to_data[vertex_attribute]
            parameter_list.append(
                CppParameter(
                    data.plural_name, f"std::vector<{data.attrib_type}>", "const", True
                )
            )
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

    def get_delete_object_methods_for_draw_info_struct(self) -> List[CppMethod]:
        associated_draw_info_struct: Optional[DrawInfo] = (
            self.get_associated_draw_info_struct()
        )
        delete_object_methods = []

        if associated_draw_info_struct:
            associated_ivpX_param_ref = ivpX_struct_to_param_ref[
                associated_draw_info_struct
            ]
            ivpX_superclass_param_refs: List[CppParameter] = (
                ivpX_param_ref_to_superclass_param_refs[associated_ivpX_param_ref]
            )

            for ivpX_param_ref in ivpX_superclass_param_refs:

                delete_object_body = f"""
                if ({ivpX_param_ref.name}.buffer_modification_tracker.has_data_in_buffer()) {{
                    delete_object({ivpX_param_ref.name}.id);
                    {ivpX_param_ref.name}.id = -1;
                    {ivpX_param_ref.name}.buffer_modification_tracker.free_buffered_data();
                }}
                """

                delete_object_methods.append(
                    CppMethod(
                        "delete_object",
                        "void",
                        [ivpX_param_ref],
                        delete_object_body,
                        "public",
                    )
                )
        else:
            print("there was no associated draw info struct")

        return delete_object_methods

    def generate_ivpX_tag_id_body(self, struct_var_name: str) -> str:
        if self.is_ubo_shader:
            return f"""
        // NOTE: THIS IS WRONG when we use a tig the id's are not in sync, thus we need a separate id for both, fix later
{struct_var_name}.id = ltw_object_id_generator.get_id();"""
        else:
            return f"""
{struct_var_name}.id = object_id_generator.get_id();"""

    def generate_ivpX_queue_draw_body(
        self, ivpX_struct_parameter_name: str, attributes: List[str]
    ) -> str:
        arg_list: str = ", ".join(
            [ivpX_struct_parameter_name + "." + attr for attr in attributes]
        )

        optional_ubo_matrix_uploading_logic: str = f"""


// NOTE: for singular draw objects their ID represent their ltw matrix index
// but when working with tigs they don't (collection of draw_info structs all with same ltw idx)
ltw_matrices[{ivpX_struct_parameter_name}.id] = {ivpX_struct_parameter_name}.transform.get_transform_matrix();
        """

        return f"""

// NOTE: if you try and queue something for drawing that isn't registered in the system we'll do that now
bool ivp_is_not_yet_registered = {ivpX_struct_parameter_name}.id == -1;
if (ivp_is_not_yet_registered) {{
    tag_id({ivpX_struct_parameter_name});
}}

{optional_ubo_matrix_uploading_logic if self.is_ubo_shader else ""} 

{f'std::vector<unsigned int> ltw_indices({ivpX_struct_parameter_name}.xyz_positions.size(), {ivpX_struct_parameter_name}.id);' if self.is_ubo_shader else ''}
bool replace = {ivpX_struct_parameter_name}.buffer_modification_tracker.has_been_modified_since_last_buffering();
queue_draw({ivpX_struct_parameter_name}.id, {ivpX_struct_parameter_name}.indices, {arg_list}{', ltw_indices' if self.is_ubo_shader else ''}, replace);
// NOTE: sometimes the queue draw doesn't buffer any data, so this method name might be bad, the inner logic makes sense though.
{ivpX_struct_parameter_name}.buffer_modification_tracker.just_buffered_data();
"""

    def generate_ivpX_cache_body(
        self, ivpX_struct_parameter_name: str, attributes: List[str]
    ) -> str:
        arg_list: str = ", ".join(
            [ivpX_struct_parameter_name + "." + attr for attr in attributes]
        )

        optional_ubo_matrix_uploading_logic: str = f"""


// NOTE: for singular draw objects their ID represent their ltw matrix index
// but when working with tigs they don't (collection of draw_info structs all with same ltw idx)
ltw_matrices[{ivpX_struct_parameter_name}.id] = {ivpX_struct_parameter_name}.transform.get_transform_matrix();
        """

        return f"""

// NOTE: if you try and cache something for drawing that isn't registered in the system we'll do that now
bool ivp_is_not_yet_registered = {ivpX_struct_parameter_name}.id == -1;
if (ivp_is_not_yet_registered) {{
    tag_id({ivpX_struct_parameter_name});
}}

{optional_ubo_matrix_uploading_logic if self.is_ubo_shader else ""} 

{f'std::vector<unsigned int> ltw_indices({ivpX_struct_parameter_name}.xyz_positions.size(), {ivpX_struct_parameter_name}.id);' if self.is_ubo_shader else ''}
bool replace = {ivpX_struct_parameter_name}.buffer_modification_tracker.has_been_modified_since_last_buffering();
cache({ivpX_struct_parameter_name}.id, {ivpX_struct_parameter_name}.indices, {arg_list}{', ltw_indices' if self.is_ubo_shader else ''}, replace);
// NOTE: sometimes the queue draw doesn't buffer any data, so this method name might be bad, the inner logic makes sense though.
{ivpX_struct_parameter_name}.buffer_modification_tracker.just_buffered_data();
"""

    def get_queue_draw_methods_for_draw_info_structs(self) -> List[CppMethod]:
        # NOTE: we are generating a bunch of versions of the same function by allowing classes with at least the same attributes as the
        # base param class to be passed in saving us time in the cpp code, guess eventually this could be templatized right? that would be we're generating templatized code which is pretty confusing... avoiding that for now.

        def generate_ivpX_queue_draw_hierarchy_methods(
            base_param: CppParameter, draw_info_attribute_names: List[str]
        ) -> List[CppMethod]:
            return [
                CppMethod(
                    "queue_draw",
                    "void",
                    [super_class_param],
                    self.generate_ivpX_queue_draw_body(
                        super_class_param.name, draw_info_attribute_names
                    ),
                    "public",
                )
                for super_class_param in ivpX_param_ref_to_superclass_param_refs[
                    base_param
                ]
            ]

        def generate_ivpX_cache_hierarchy_methods(
            base_param: CppParameter, draw_info_attribute_names: List[str]
        ) -> List[CppMethod]:
            return [
                CppMethod(
                    "cache",
                    "void",
                    [super_class_param],
                    self.generate_ivpX_cache_body(
                        super_class_param.name, draw_info_attribute_names
                    ),
                    "public",
                )
                for super_class_param in ivpX_param_ref_to_superclass_param_refs[
                    base_param
                ]
            ]

        def generate_ivpX_tag_id_hierarchy_methods(
            base_param_ref: CppParameter,
        ) -> List[CppMethod]:
            return [
                CppMethod(
                    "tag_id",
                    "void",
                    [super_class_param_ref],
                    self.generate_ivpX_tag_id_body(super_class_param_ref.name),
                    "public",
                )
                for super_class_param_ref in ivpX_param_ref_to_superclass_param_refs[
                    base_param_ref
                ]
            ]

        # NOTE: doing this in a stupid way, building a bunch of data and then later on only selecting the stuff we need rather than just
        # only generating the stuff we need in the first place
        ivp_queue_draw_hierarchy_methods = generate_ivpX_queue_draw_hierarchy_methods(
            ivp_param_ref, ["xyz_positions"]
        )
        ivpn_queue_draw_hierarchy_methods = generate_ivpX_queue_draw_hierarchy_methods(
            ivpn_param_ref, ["xyz_positions", "normals"]
        )
        ivpc_queue_draw_hierarchy_methods = generate_ivpX_queue_draw_hierarchy_methods(
            ivpc_param_ref, ["xyz_positions", "rgb_colors"]
        )
        ivpnc_queue_draw_hierarchy_methods = generate_ivpX_queue_draw_hierarchy_methods(
            ivpnc_param_ref, ["xyz_positions", "normals", "rgb_colors"]
        )

        ivp_cache_hierarchy_methods = generate_ivpX_cache_hierarchy_methods(
            ivp_param_ref, ["xyz_positions"]
        )
        ivpn_cache_hierarchy_methods = generate_ivpX_cache_hierarchy_methods(
            ivpn_param_ref, ["xyz_positions", "normals"]
        )
        ivpc_cache_hierarchy_methods = generate_ivpX_cache_hierarchy_methods(
            ivpc_param_ref, ["xyz_positions", "rgb_colors"]
        )
        ivpnc_cache_hierarchy_methods = generate_ivpX_cache_hierarchy_methods(
            ivpnc_param_ref, ["xyz_positions", "normals", "rgb_colors"]
        )

        ivp_tag_id_hierarchy_methods = generate_ivpX_tag_id_hierarchy_methods(
            ivp_param_ref
        )
        ivpn_tag_id_hierarchy_methods = generate_ivpX_tag_id_hierarchy_methods(
            ivpn_param_ref
        )
        ivpc_tag_id_hierarchy_methods = generate_ivpX_tag_id_hierarchy_methods(
            ivpc_param_ref
        )
        ivpnc_tag_id_hierarchy_methods = generate_ivpX_tag_id_hierarchy_methods(
            ivpc_param_ref
        )

        draw_info_struct_to_queue_draw_cpp_methods: Dict[DrawInfo, List[CppMethod]] = {
            DrawInfo.INDEXED_VERTEX_POSITIONS: ivp_queue_draw_hierarchy_methods,
            DrawInfo.IVPNORMALS: ivpn_queue_draw_hierarchy_methods,
            DrawInfo.IVPCOLOR: ivpc_queue_draw_hierarchy_methods,
            DrawInfo.IVPNCOLOR: ivpnc_queue_draw_hierarchy_methods,
        }

        draw_info_struct_to_cache_cpp_methods: Dict[DrawInfo, List[CppMethod]] = {
            DrawInfo.INDEXED_VERTEX_POSITIONS: ivp_cache_hierarchy_methods,
            DrawInfo.IVPNORMALS: ivpn_cache_hierarchy_methods,
            DrawInfo.IVPCOLOR: ivpc_cache_hierarchy_methods,
            DrawInfo.IVPNCOLOR: ivpnc_cache_hierarchy_methods,
        }

        draw_info_struct_to_tag_id_cpp_method: Dict[DrawInfo, List[CppMethod]] = {
            DrawInfo.INDEXED_VERTEX_POSITIONS: ivp_tag_id_hierarchy_methods,
            DrawInfo.IVPNORMALS: ivpn_tag_id_hierarchy_methods,
            DrawInfo.IVPCOLOR: ivpc_tag_id_hierarchy_methods,
            DrawInfo.IVPNCOLOR: ivpnc_tag_id_hierarchy_methods,
        }

        # NOTE: we're using this for all of them, bad.
        queue_draw_methods: List[CppMethod] = []

        associated_draw_info_struct: Optional[DrawInfo] = (
            self.get_associated_draw_info_struct()
        )

        if associated_draw_info_struct:
            associated_queue_draw_methods: List[CppMethod] = (
                draw_info_struct_to_queue_draw_cpp_methods[associated_draw_info_struct]
            )
            queue_draw_methods.extend(associated_queue_draw_methods)

            associated_cache_methods: List[CppMethod] = (
                draw_info_struct_to_cache_cpp_methods[associated_draw_info_struct]
            )
            queue_draw_methods.extend(associated_cache_methods)

            associated_tag_id_methods: List[CppMethod] = (
                draw_info_struct_to_tag_id_cpp_method[associated_draw_info_struct]
            )
            queue_draw_methods.extend(associated_tag_id_methods)
        else:
            print("cannot find an associated queue draw call")

        return queue_draw_methods

    def generate_queue_draw_body(self) -> str:

        parameters_to_cache: List[str] = []
        for vertex_attribute in self.vertex_attributes:
            data = shader_vertex_attribute_to_data[vertex_attribute]
            parameters_to_cache.append(data.plural_name)

        unique_cache_params = ", ".join(parameters_to_cache)

        body = f"""
        object_ids_this_tick.push_back(object_id);
        cache(object_id, indices, {unique_cache_params}, replace);
        """
        return body

    def generate_cache_body(self) -> str:

        def generate_sub_buffering_calls() -> str:
            lines = []
            for v in self.vertex_attributes:
                sva_data = shader_vertex_attribute_to_data[v]
                lines.append(
                    f"glBindBuffer(GL_ARRAY_BUFFER, {sva_data.plural_name}_buffer_object);"
                )
                lines.append(
                    f"glBufferSubData(GL_ARRAY_BUFFER, *start_index * sizeof({sva_data.attrib_type}), {sva_data.plural_name}.size() * sizeof({sva_data.attrib_type}), {sva_data.plural_name}.data());"
                )
                lines.append("\n")

            indentation = TAB
            for i in range(len(lines)):
                lines[i] = indentation + lines[i]

            return "\n".join(lines)

        body = f"""
    bool logging = false;

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

    # TODO: in the future there will be a bass queue draw call and then the extension classes
    # will extend the body of the function filling in empty data (eg bone transforms or something)
    def generate_CWL_V_TRANSFORMATION_UBOS_1024_WITH_SOLID_COLOR_specific_class_data(
        self, batcher_class: CppClass
    ):
        tig = CppParameter("tig", "draw_info::TransformedIVPGroup", "", True)
        replace = CppParameter("replace", "bool", "", False, "false")
        transform_matrix_override = CppParameter(
            "transform_matrix_override", "glm::mat4", "", False, "glm::mat4(0)"
        )
        body = """



int ltw_object_id = tig.id;
// TODO: there will be a bug here if you try to override with the zero matrix, but you will probably never do that
bool requested_override = transform_matrix_override != glm::mat4(0);
if (requested_override) {
    ltw_matrices[ltw_object_id] = transform_matrix_override;
} else {
    ltw_matrices[ltw_object_id] = tig.transform.get_transform_matrix();
}


for (auto &ivp : tig.ivps) {
    std::vector<unsigned int> ltw_indices(ivp.xyz_positions.size(), ltw_object_id);
    queue_draw(ivp.id, ivp.indices, ivp.xyz_positions, ltw_indices, replace);
}
        """
        batcher_class.add_method(
            CppMethod(
                "queue_draw",
                "void",
                [tig, replace, transform_matrix_override],
                body,
                "public",
            )
        )

    def generate_TEXTURE_PACKER_CWL_V_TRANSFORMATION_UBOS_1024_specfic_class_data(
        self, batcher_class: CppClass
    ):

        indices = CppParameter("indices", "std::vector<unsigned int>")
        xyz_positions = CppParameter("xyz_positions", "std::vector<glm::vec3>")

        ivptps = CppParameter("ivptps", "std::vector<draw_info::IVPTexturePacked>")

        # TODO: generic enough to be in any ltw batcher class
        tig = CppParameter(
            "tig_to_update", "draw_info::TransformedIVPTPGroup", "", True
        )
        body = """
tig_to_update.id = ltw_object_id_generator.get_id();
for (auto &ivptp : tig_to_update.ivptps) {
    // NOTE: note that we must regenerate the internal ivptp ids because we do not use instancing here and for each
    // object we store its ltw matrices so we can't re-use the same geometry
    ivptp.id = object_id_generator.get_id();
}
        """
        batcher_class.add_method(
            CppMethod("update_tig_ids", "void", [tig], body, "public")
        )

        const_tig = CppParameter(
            "tig", "draw_info::TransformedIVPTPGroup", "const", True
        )
        body = """
for (const auto &ivptp : tig.ivptps) {
    delete_object(ivptp.id);
}
ltw_object_id_generator.reclaim_id(tig.id);
        """
        batcher_class.add_method(
            CppMethod("delete_tig", "void", [const_tig], body, "public")
        )

        tig = CppParameter("tig", "draw_info::TransformedIVPTPGroup")
        replace = CppParameter("replace", "bool", "", False, "false")
        transform_matrix_override = CppParameter(
            "transform_matrix_override", "glm::mat4", "", False, "glm::mat4(0)"
        )
        body = """
int ltw_object_id = tig.id;
// TODO: there will be a bug here if you try to override with the zero matrix, but you will probably never do that
bool requested_override = transform_matrix_override != glm::mat4(0);
if (requested_override) {
    ltw_matrices[ltw_object_id] = transform_matrix_override;
} else {
    ltw_matrices[ltw_object_id] = tig.transform.get_transform_matrix();
}

for (const auto &ivptp : tig.ivptps) {
    std::vector<unsigned int> ltw_indices(ivptp.xyz_positions.size(), ltw_object_id);
    std::vector<int> ptis(ivptp.xyz_positions.size(), ivptp.packed_texture_index);
    std::vector<int> ptbbi(ivptp.xyz_positions.size(), ivptp.packed_texture_bounding_box_index);

    queue_draw(ivptp.id, ivptp.indices, ltw_indices, ptis, ivptp.packed_texture_coordinates, ptbbi,
                              ivptp.xyz_positions, replace);
}
        """
        batcher_class.add_method(
            CppMethod(
                "queue_draw",
                "void",
                [tig, replace, transform_matrix_override],
                body,
                "public",
            )
        )

    def generate_TEXTURE_PACKER_RIGGED_AND_ANIMATED_CWL_V_TRANSFORMATION_UBOS_1024_WITH_TEXTURES_specfic_class_data(
        self, batcher_class: CppClass
    ):
        tig = CppParameter("tig", "draw_info::TransformedIVPNTPRGroup", "", True)
        replace = CppParameter("replace", "bool", "", False, "false")
        transform_matrix_override = CppParameter(
            "transform_matrix_override", "glm::mat4", "", False, "glm::mat4(0)"
        )
        body = """


    int ltw_object_id = tig.id;
    // TODO: there will be a bug here if you try to override with the zero matrix, but you will probably never do that
    bool requested_override = transform_matrix_override != glm::mat4(0);
    if (requested_override) {
        ltw_matrices[ltw_object_id] = transform_matrix_override;
    } else {
        ltw_matrices[ltw_object_id] = tig.transform.get_transform_matrix();
    }


    for (auto &ivpntpr : tig.ivpntprs) {
        // Populate bone_indices and bone_weights
        std::vector<glm::ivec4> bone_indices;
        std::vector<glm::vec4> bone_weights;

        for (const auto &vertex_bone_data : ivpntpr.bone_data) {
            glm::ivec4 indices(static_cast<int>(vertex_bone_data.indices_of_bones_that_affect_this_vertex[0]),
                               static_cast<int>(vertex_bone_data.indices_of_bones_that_affect_this_vertex[1]),
                               static_cast<int>(vertex_bone_data.indices_of_bones_that_affect_this_vertex[2]),
                               static_cast<int>(vertex_bone_data.indices_of_bones_that_affect_this_vertex[3]));

            glm::vec4 weights(vertex_bone_data.weight_value_of_this_vertex_wrt_bone[0],
                              vertex_bone_data.weight_value_of_this_vertex_wrt_bone[1],
                              vertex_bone_data.weight_value_of_this_vertex_wrt_bone[2],
                              vertex_bone_data.weight_value_of_this_vertex_wrt_bone[3]);

            bone_indices.push_back(indices);
            bone_weights.push_back(weights);
        }

        std::vector<int> packed_texture_indices(ivpntpr.xyz_positions.size(), ivpntpr.packed_texture_index);
        std::vector<int> packed_texture_bounding_box_indices(ivpntpr.xyz_positions.size(), ivpntpr.packed_texture_bounding_box_index);

        std::vector<unsigned int> ltw_indices(ivpntpr.xyz_positions.size(), tig.id);

         queue_draw(ivpntpr.id, ivpntpr.indices, ltw_indices, bone_indices, bone_weights,
                        packed_texture_indices, ivpntpr.packed_texture_coordinates,
                        packed_texture_bounding_box_indices, ivpntpr.xyz_positions);
    }
        """
        batcher_class.add_method(
            CppMethod(
                "queue_draw",
                "void",
                [tig, replace, transform_matrix_override],
                body,
                "public",
            )
        )

    # NOTE: this is the main entry point to generating each batcher
    def generate_cpp_class(self) -> CppClass:
        batcher_class = CppClass(self.get_class_name())

        is_ubo_1024_shader = (
            ShaderVertexAttributeVariable.LOCAL_TO_WORLD_INDEX in self.vertex_attributes
        )
        # CLASS ATTRIBUTES START

        if is_ubo_1024_shader:
            batcher_class.add_member(
                CppMember(
                    "ltw_object_id_generator",
                    "BoundedUniqueIDGenerator",
                    "BoundedUniqueIDGenerator(1024)",
                )
            )
            batcher_class.add_member(CppMember("ltw_matrices_gl_name", "GLuint"))
            batcher_class.add_member(CppMember("ltw_matrices[1024]", "glm::mat4"))

        batcher_class.add_member(CppMember("object_id_generator", "UniqueIDGenerator"))
        batcher_class.add_member(CppMember("shader_cache", "ShaderCache"))
        batcher_class.add_member(CppMember("vertex_attribute_object", "GLuint"))
        batcher_class.add_member(CppMember("indices_buffer_object", "GLuint"))

        # add vector for each thing this shader type has
        for vertex_attribute in self.vertex_attributes:
            va_data = shader_vertex_attribute_to_data[vertex_attribute]
            batcher_class.add_member(
                CppMember(f"{va_data.plural_name}_buffer_object", "GLuint")
            )

        batcher_class.add_member(
            CppMember("curr_index_buffer_offset", "unsigned int", "0")
        )
        batcher_class.add_member(
            CppMember("largest_index_used_so_far", "unsigned int", "0")
        )

        batcher_class.add_member(
            CppMember("object_ids_this_tick", f"std::vector<unsigned int>")
        )
        batcher_class.add_member(
            CppMember("object_ids_last_tick", f"std::vector<unsigned int>")
        )
        batcher_class.add_member(
            CppMember("drawn_indices_last_tick", f"std::vector<unsigned int>")
        )
        batcher_class.add_member(
            CppMember(
                "cached_object_ids_to_indices",
                f"std::unordered_map<unsigned int, std::vector<unsigned int>>",
            )
        )

        batcher_class.add_member(CppMember("fsat", f"FixedSizeArrayTracker"))

        batcher_class.add_member(
            CppMember("replaced_data_for_an_object_this_tick ", f"bool")
        )

        # CLASS ATTRIBUTES END

        # CLASS METHODS START

        ubo_matrices_initialization = f"""
    for (int i = 0; i < 1024; ++i) {{
        ltw_matrices[i] = glm::mat4(1.0f);
    }}

    glGenBuffers(1, &ltw_matrices_gl_name);
    glBindBuffer(GL_UNIFORM_BUFFER, ltw_matrices_gl_name);
    glBufferData(GL_UNIFORM_BUFFER, sizeof(ltw_matrices), ltw_matrices, GL_STATIC_DRAW);
    glBindBufferBase(GL_UNIFORM_BUFFER, 0, ltw_matrices_gl_name);

        """

        # TODO: parameterize
        batcher_class.add_constructor(
            [CppParameter("shader_cache", "ShaderCache", "", True)],
            f"shader_cache(shader_cache), fsat({self.num_elements_in_buffer})",
            f"""
    { ubo_matrices_initialization if (is_ubo_1024_shader) else "" }
    glGenVertexArrays(1, &vertex_attribute_object);
    glBindVertexArray(vertex_attribute_object);
    glGenBuffers(1, &indices_buffer_object);
    // reserve space for 1 million elements, probably overkill
    const size_t initial_buffer_size = {self.num_elements_in_buffer};
    {self.generate_constructor_body()}
    glBindVertexArray(0);""",
        )

        batcher_class.add_method(
            CppMethod(
                f"~{self.get_class_name()}",
                "",
                [],
                self.generate_deconstructor(),
                "public",
            )
        )

        if is_ubo_1024_shader:
            batcher_class.add_method(
                CppMethod(
                    "upload_ltw_matrices",
                    "void",
                    [],
                    f"""
    glBindBuffer(GL_UNIFORM_BUFFER, ltw_matrices_gl_name);
    glBufferData(GL_UNIFORM_BUFFER, sizeof(ltw_matrices), ltw_matrices, GL_STATIC_DRAW);
    glBindBufferBase(GL_UNIFORM_BUFFER, 0, ltw_matrices_gl_name);
            """,
                )
            )

        # glBindBuffer(GL_UNIFORM_BUFFER, ltw_matrices_gl_name);
        # glBufferSubData(GL_UNIFORM_BUFFER, 0, sizeof(ltw_matrices), ltw_matrices);
        # glBindBuffer(GL_UNIFORM_BUFFER, 0);

        delete_object_body = f"""
    auto it = cached_object_ids_to_indices.find(object_id);
    if (it != cached_object_ids_to_indices.end()) {{
        fsat.remove_metadata(object_id);
    {  "ltw_object_id_generator.reclaim_id(object_id);" if self.is_ubo_shader else "object_id_generator.reclaim_id(object_id);"}
        
        cached_object_ids_to_indices.erase(it);
    }}
        """

        batcher_class.add_method(
            CppMethod(
                "delete_object",
                "void",
                [CppParameter("object_id", "unsigned int", "const")],
                delete_object_body,
                "public",
            )
        )

        for method in self.get_delete_object_methods_for_draw_info_struct():
            batcher_class.add_method(method)

        for method in self.get_queue_draw_methods_for_draw_info_structs():
            batcher_class.add_method(method)

        queue_draw_by_id_body = f"""
    auto it = cached_object_ids_to_indices.find(object_id);
    if (it != cached_object_ids_to_indices.end()) {{
        object_ids_this_tick.push_back(object_id);
    }} else {{
        std::cout << "you tried to draw an object that is not cached, we cannot do that, it has id: " << object_id << std::endl;
    }}
        """

        batcher_class.add_method(
            CppMethod(
                "queue_draw",
                "void",
                [CppParameter("object_id", "unsigned int", "const")],
                queue_draw_by_id_body,
                "public",
            )
        )

        # NOTE: this is the base queue draw that the above ones use internally
        batcher_class.add_method(
            CppMethod(
                "queue_draw",
                "void",
                self.generate_queue_draw_parameter_list(),
                self.generate_queue_draw_body(),
                "public",
            )
        )

        batcher_class.add_method(
            CppMethod(
                "cache",
                "void",
                self.generate_cache_parameter_list(),
                self.generate_cache_body(),
                "public",
            )
        )

        if (
            self.shader_type
            == ShaderType.CWL_V_TRANSFORMATION_UBOS_1024_WITH_SOLID_COLOR
        ):
            self.generate_CWL_V_TRANSFORMATION_UBOS_1024_WITH_SOLID_COLOR_specific_class_data(
                batcher_class
            )

        if self.shader_type == ShaderType.TEXTURE_PACKER_CWL_V_TRANSFORMATION_UBOS_1024:
            self.generate_TEXTURE_PACKER_CWL_V_TRANSFORMATION_UBOS_1024_specfic_class_data(
                batcher_class
            )

        if (
            self.shader_type
            == ShaderType.TEXTURE_PACKER_RIGGED_AND_ANIMATED_CWL_V_TRANSFORMATION_UBOS_1024_WITH_TEXTURES
        ):
            self.generate_TEXTURE_PACKER_RIGGED_AND_ANIMATED_CWL_V_TRANSFORMATION_UBOS_1024_WITH_TEXTURES_specfic_class_data(
                batcher_class
            )

        batcher_class.add_method(
            CppMethod(
                "draw_everything",
                "void",
                [],
                self.generate_draw_everything_body(),
                "public",
            )
        )

        # CLASS METHODS END

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
            batcher_class.add_member(
                CppMember(
                    camel_to_snake_case(constructed_batcher_name),
                    constructed_batcher_name,
                )
            )
            initializer_list.append(
                f"{camel_to_snake_case(constructed_batcher_name)}(shader_cache)"
            )
            # remove from end
            clip_size = len("_SHADER_BATCHER")
            shader_type = camel_to_snake_case(constructed_batcher_name)[
                :-clip_size
            ].upper()
            # requested_shader_types.append(f"{TAB * 2}ShaderType::{shader_type}");

        # Add requested_shaders member
        batcher_class.add_member(
            CppMember(
                "requested_shaders",
                "static std::vector<ShaderType>",
            )
        )

        initializer_list = ", ".join(initializer_list)

        # Add constructor with updated initializer list
        # batcher_class.add_constructor("ShaderCache& shader_cache", initializer_list, "requested_shaders = {\n" + ",\n".join(requested_shader_types) + f"\n{TAB}}};")
        batcher_class.add_constructor(
            [CppParameter("shader_cache", "ShaderCache", "", True)],
            initializer_list,
            "",
        )

        return batcher_class


def list_available_shaders(shader_to_used_vertex_attribute_variables):
    print("Available Shaders:")
    shader_list = list(shader_to_used_vertex_attribute_variables.keys())
    for i, shader_type in enumerate(shader_list):
        print(f"{i + 1}. {shader_type.name}")

    selected_indices = input(
        "Enter the numbers of the shaders you want to generate, separated by spaces: "
    ).split()
    selected_shaders = [
        shader_list[int(index) - 1] for index in selected_indices if index.isdigit()
    ]

    print("\nYou have selected the following shaders:")
    for shader in selected_shaders:
        print(f"- {shader.name}")

    confirm = input("Are you okay with this selection? (y/n): ")
    if confirm.lower() != "y":
        return list_available_shaders(
            shader_to_used_vertex_attribute_variables
        )  # Re-run selection if not confirmed
    return selected_shaders


import os
import shutil


def wipe_generated_directory():
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Define the path for the 'generated' directory relative to the script's location
    generated_dir = os.path.join(script_dir, "generated")

    # Remove 'generated' if it exists and recreate it
    if os.path.exists(generated_dir):
        shutil.rmtree(generated_dir)
    os.makedirs(generated_dir)


@dataclass
class ShaderRequest:
    shader_type: ShaderType
    num_elements_in_buffer: int


def get_required_shaders(config_file) -> List[ShaderRequest]:
    """Read the configuration file and return a list of ShaderRequest objects after validation."""
    with open(config_file, "r") as file:
        shader_specs = [line.strip() for line in file if line.strip()]

    return validate_shader_specs(shader_specs)


def validate_shader_specs(shader_specs: List[str]) -> List["ShaderRequest"]:
    """Validate shader specs and return a list of ShaderRequest objects (shader + buffer size)."""
    valid_shader_names = {
        shader.name.lower(): shader for shader in ShaderType
    }  # Map enum names to enum values
    shader_requests = []

    pattern_with_size = re.compile(r"^([a-zA-Z0-9_]+)\((\d+)\)$")
    pattern_no_size = re.compile(r"^([a-zA-Z0-9_]+)$")

    DEFAULT_NUM_ELEMENTS = 100000

    for spec in shader_specs:
        match_with_size = pattern_with_size.match(spec)
        match_no_size = pattern_no_size.match(spec)

        if match_with_size:
            shader_name, num_elements_str = match_with_size.groups()
            num_elements = int(num_elements_str)
        elif match_no_size:
            shader_name = match_no_size.group(1)
            num_elements = DEFAULT_NUM_ELEMENTS
        else:
            print(
                f"Error: Invalid format '{spec}'. Expected 'shader_name' or 'shader_name(num_elements)'."
            )
            exit(1)

        shader_name = shader_name.lower()

        if shader_name not in valid_shader_names:
            print(f"Error: '{shader_name}' is not a valid shader type.")
            exit(1)

        if num_elements <= 0:
            print(f"Error: buffer size must be positive in '{spec}'.")
            exit(1)

        shader_requests.append(
            ShaderRequest(valid_shader_names[shader_name], num_elements)
        )

    print("All shader specs are valid.")
    return shader_requests


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Generate C++ shader batcher classes.")
    parser.add_argument(
        "--generate-config",
        "-gc",
        action="store_true",
        help="Generate a config file for the requested shaders.",
    )
    parser.add_argument(
        "--config-file",
        "-c",
        type=str,
        help="Path to the configuration file to read from.",
    )
    parser.add_argument(
        "--config-file-output-dir",
        "-cfod",
        type=str,
        default=".",
        help="Directory to save the generated config file (default: current directory).",
    )

    args = parser.parse_args()

    # we assume that submodules can define their own required shader batchers and then we compile all those here.
    concatenate_files(
        find_all_instances_of_file_in_directory_recursively(
            ".", ".required_shader_batchers.txt"
        ),
        ".all_required_shader_batchers.txt",
    )

    if args.generate_config:
        # NOTE: I don't think we have really used this recently? and I think this logic can be ignored and is old
        user_shader_requests = list_available_shaders(
            shader_to_used_vertex_attribute_variables
        )
        config_file_path = os.path.join(
            args.config_file_output_dir, ".all_required_shader_batchers.txt"
        )
        with open(config_file_path, "w") as config_file:
            for shader in user_shader_requests:
                shader_name = str(shader).split(".")[-1].lower()
                config_file.write(f"{shader_name}\n")
        print(f"Configuration written to {config_file_path}")
    else:
        if args.config_file:
            # NOTE: I think this is the only used logic path
            if not os.path.exists(args.config_file):
                print(f"Configuration file {args.config_file} not found.")
                sys.exit(1)

            user_shader_requests: List[ShaderRequest] = get_required_shaders(
                args.config_file
            )
            print(f"Selected shaders from config file: {user_shader_requests}")
        else:
            user_shader_requests = list_available_shaders(
                shader_to_used_vertex_attribute_variables
            )

        constructed_class_names: List[str] = []
        constructed_header_files: List[str] = []

        wipe_generated_directory()

        # Get the directory where the script exists
        script_directory = os.path.dirname(os.path.abspath(__file__)) + "/generated"

        # NOTE: this is the main logic that starts off everything
        for (
            shader_type,
            vertex_attributes,
        ) in shader_to_used_vertex_attribute_variables.items():

            # TODO: then just iterate over this instead of this check...
            if shader_type not in [usr.shader_type for usr in user_shader_requests]:
                continue

            num_elements_in_buffer = 100000
            for shader_request in user_shader_requests:
                if shader_request.shader_type == shader_type:
                    num_elements_in_buffer = shader_request.num_elements_in_buffer

            header_file = f"{shader_type.name.lower()}_shader_batcher.hpp"
            constructed_header_files.append(header_file)

            # Create file paths relative to the script's directory
            header_filename = os.path.join(
                script_directory, f"{shader_type.name.lower()}_shader_batcher.hpp"
            )
            source_filename = os.path.join(
                script_directory, f"{shader_type.name.lower()}_shader_batcher.cpp"
            )

            shader_batcher_header_and_source = CppHeaderAndSource(
                f"{shader_type.name.lower()}_shader_batcher"
            )

            shader_batcher_header_and_source.add_include(
                '#include <iostream>\n#include <string>\n#include "../fixed_size_array_tracker/fixed_size_array_tracker.hpp"\n#include "../sbpt_generated_includes.hpp"\n\n'
            )

            shader_batcher = ShaderBatcherCppClass(
                shader_type, num_elements_in_buffer, vertex_attributes
            )
            batcher_class = shader_batcher.generate_cpp_class()
            shader_batcher_header_and_source.add_class(batcher_class)

            # shader_batcher_draw_info_struct = ShaderBatcherCppStruct(shader_type, vertex_attributes)
            # struct = shader_batcher_draw_info_struct.generate_cpp_struct()
            # shader_batcher_header_and_source.add_struct(struct)

            # shader_batcher_header_and_source.add_extra_header_code(generate_hashing_code_for_draw_data(vertex_attributes, shader_type))

            source_content = shader_batcher_header_and_source.generate_source_content()
            header_content = shader_batcher_header_and_source.generate_header_content()

            # Write the header content to the header file
            with open(header_filename, "w") as header_file:
                header_file.write(header_content)

            # Write the source content to the source file
            with open(source_filename, "w") as source_file:
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

        include_statements = (
            "\n".join(
                [
                    f'#include "{header_file}"'
                    for header_file in constructed_header_files
                ]
            )
            + "\n\n"
        )

        batcher_class.add_include(include_statements)

        batcher_header_and_source = CppHeaderAndSource("batcher")
        batcher_header_and_source.add_class(batcher_class)

        header_content = batcher_header_and_source.generate_header_content()
        source_content = batcher_header_and_source.generate_source_content()

        # Write the header content to the header file
        with open(header_filename, "w") as header_file:
            header_file.write(header_content)

        # Write the source content to the source file
        with open(source_filename, "w") as source_file:
            source_file.write(source_content)

        # Optional: Print confirmation message
        print(f"Header written to {header_filename}")
        print(f"Source written to {source_filename}")
