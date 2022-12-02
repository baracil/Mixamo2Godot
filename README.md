# Mixamo2Godot

Script to merge several Mixamo animations into one GLB file.
This script does what is described in this [video](https://www.youtube.com/watch?v=3Hk9ljcS1Ro&list=PLeeIiJXUfIElY53ghhM8sb-5GSKo86oQZ&index=2)
The script:

* scales the animations (object and hips location)
* rename the bones
* add root motion
* add one strip for each animations

It requires that all the animations from Mixamo are saved in one directory and one is the T pose named TPose.fbx. You can then launch the script within Blender or from the command line with <code>Blender --background --python /path/to/the/script -- /path/to/directory/of/animation</code>. The base name of the directory containing the FBX file will be used for the export file (with .glb added).
