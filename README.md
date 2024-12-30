# batcher
a class which helps manage batching over shaders, note that there are no source files stored, but instead must be generated with the python script.

## setup
1. the batcher reles on the shader standard project and you must link in `shader_standard.py` and `standard.py` in to this directory for it to operate correctly
2. run `batcher.py` and generate the shaders you need

## todo
* the batcher needs to allow for the clearing out of data possibly, this only needs to be done if we start running out of space in our buffers, don't look into that until it occurs
* the batcher possibly needs to allow for updating a single component of an existant object such as just the normals or something, don't have a usecase yet though

