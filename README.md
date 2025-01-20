# batcher
a class which helps manage batching over shaders, note that there are no source files stored, but instead must be generated with the python script.

## setup
1. the batcher relies on the shader standard project and you must link in `shader_standard.py` and `standard.py` in to this directory for it to operate correctly
2. run `batcher.py` and generate the batchers for each shaders you need

**WARNING**: the `queue_draw` call parameter list order is generated based on the order of vertex attribute variables encountered in the shader file, thus if you change the order, your `queue_draw` calls will break, keep this in mind.

## how it works
the purpose of the batcher is to reduce the number of draw calls made by opengl, the method we employ for doing that is allowing the programmer to make `queue_draw` calls that don't actually draw anything, but attempt to store the data into a bunch of pre-allocated buffers, additionally if the user is requested a `queue_draw` with the same information again, then the data that is already stored should be used instead of re-uploading that data.


### draw object ids
A draw object is a collection of information required to draw something. Most of the time all of this information moves together through space somehow, which is to say that it only needs one `local_to_world` matrix associated with all the data. When you draw something, you must submit an object id of what you want to draw, along with all the information to draw it, if the object id is already cached, it will not re-upload the information.


An object id is a unique id associated with a collection of drawing information, which for the most part should stay static

## example
Since the batcher is generated code, it's good to look at some real code which is immediately readable to understand how this sytem works, `batcher_visualization.py` was created for that purpose, and here is the output: 

```
$ python batcher_visualization.py 
queuing up aaa with id: id1 for printing
Adding string with ID 'id1': aaa
Array after adding string with ID 'id1'
Array: ['a', 'a', 'a', '', '', '', '', '', '', '']
Metadata: {'id1': (0, 3)}
queuing up bbb with id: id2 for printing
Adding string with ID 'id2': bbb
Array after adding string with ID 'id2'
Array: ['a', 'a', 'a', 'b', 'b', 'b', '', '', '', '']
Metadata: {'id1': (0, 3), 'id2': (3, 3)}
=== PRINTING EVERYTHING ===
Retrieving string with ID 'id1'
aaa
Retrieving string with ID 'id2'
bbb
queuing up cc with id: id3 for printing with replacement
Adding string with ID 'id3': cc
Array after adding string with ID 'id3'
Array: ['a', 'a', 'a', 'b', 'b', 'b', 'c', 'c', '', '']
Metadata: {'id1': (0, 3), 'id2': (3, 3), 'id3': (6, 2)}
queuing up ddd with id: id1 for printing with replacement
Adding string with ID 'id1': ddd
Removed old string with ID 'id1'.
Array after adding string with ID 'id1'
Array: ['d', 'd', 'd', 'b', 'b', 'b', 'c', 'c', '', '']
Metadata: {'id2': (3, 3), 'id3': (6, 2), 'id1': (0, 3)}
=== PRINTING EVERYTHING ===
Retrieving string with ID 'id3'
cc
Retrieving string with ID 'id1'
ddd
```

To understand the batcher do this conversion
- Fixed Array -> Vertex Buffer Object
- Strings -> Geometry you want to draw
- Printing -> Drawing


## todo
* We need to allow more operations for an object id, such as clearing information out, forcing it to upload new data, and so on, as well as the ability to not cache something, or to remove it later on.
* also for the most part we just update the model matrices, so there's no need to overwrite all infomration, perhaps we can pass in null for those and that way we only update what is required.
* also for text, we need to assign each character a unique id, and then we just have to submit what we need, in this case we know the same drawing geometry will be re-used throughout the lifetime of our program so its fine to upload that at the start, but for ui elements, I'm not sure, also if a ui element ever got resized, we would want to clobber/replace that object id, or just use a transform for it I think.
* the batcher needs to allow for the clearing out of data possibly, this only needs to be done if we start running out of space in our buffers, don't look into that until it occurs
* the batcher possibly needs to allow for updating a single component of an existant object such as just the normals or something, don't have a usecase yet though

