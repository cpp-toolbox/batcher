# batcher
a class which helps manage batching over shaders, note that there are no source files stored, but instead must be generated with the python script.

## setup
1. the batcher relies on the shader standard project and you must link in `shader_standard.py` and `standard.py` in to this directory for it to operate correctly
2. run `batcher.py` and generate the shaders you need

## how it works
the purpose of the batcher is to reduce the number of draw calls made by opengl, the method we employ for doing that is allowing the programmer to make `queue_draw` calls that don't actually draw anything, but attempt to store the data into a bunch of pre-allocated buffers, additionally if the user is requested a `queue_draw` with the same information again, then the data that is already stored should be used instead of re-uploading that data.

### draw object ids
A draw object is a collection of information required to draw something. Most of the time all of this information moves together through space somehow, which is to say that it only needs one `local_to_world` matrix associated with all the data. When you draw something, you must submit an object id of what you want to draw, along with all the information to draw it, if the object id is already cached, it will not re-upload the information.


An object id is a unique id associated with a collection of drawing information, which for the most part should stay static


## todo
* We need to allow more operations for an object id, such as clearing information out, forcing it to upload new data, and so on, as well as the ability to not cache something, or to remove it later on.
* also for the most part we just update the model matrices, so there's no need to overwrite all infomration, perhaps we can pass in null for those and that way we only update what is required.
* also for text, we need to assign each character a unique id, and then we just have to submit what we need, in this case we know the same drawing geometry will be re-used throughout the lifetime of our program so its fine to upload that at the start, but for ui elements, I'm not sure, also if a ui element ever got resized, we would want to clobber/replace that object id, or just use a transform for it I think.
* the batcher needs to allow for the clearing out of data possibly, this only needs to be done if we start running out of space in our buffers, don't look into that until it occurs
* the batcher possibly needs to allow for updating a single component of an existant object such as just the normals or something, don't have a usecase yet though

