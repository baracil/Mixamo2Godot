# MIT License
#
# Copyright (c) 2022 Bastien Aracil
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
import bpy
import bpy.types
import sys
from mathutils import Matrix

# Script that will automatically
#  1 - scales the FBX files from Mixamo (Object and keyframes)
#  2 - Rename bones
#  3 - Join several animations into strips
#  4 - Add a RootMotion node
#
# The FBX files containing the animations must be in the same directory. One of them
# must be the TPose and the file must be named "TPose.fbx".
# All the animation strips will be named from the name of the file containing the animation.
# You can add "-loop" at the name so that Godot will automatically make it a loop.
#
# The script can be launch from Blender, you need to modify the value of the FBX_DIR variable
# to your setup. It can also be launched from the command line like :
#
# blender --background --python /path/to/this/script -- /path/to/the/directory/with/fbx_files
#
# The directory name will be used for the name of the library (with .glb added)
#
# Set it to the directory containing the FBX files that will be joined
# The final directory name will be used for the name of the library (with .glb added)
FBX_DIR = "/path_to/basic_movement"


def main():
    clear_all()
    argv = sys.argv

    export_gtlf = True
    source_dir = FBX_DIR

    if "--" in argv:
        argv = argv[argv.index("--")+1:]
        if len(argv) == 0:
            print("Arguments missing :  -- directory_with_fbx_files [output_file.glb]")
            return
        for a in argv:
            if a == "--no-export" or a == "-ne":
                 export_gtlf=False
            else:
               source_dir = os.path.normpath(a)


    basedir = os.path.dirname(source_dir)
    library = os.path.basename(source_dir)

    print(f"Base Dir : {basedir}")
    print(f"Library  : {library}")

    exporter = Mixamo2Godot(basedir)
    exporter.process(library,export_gtlf)
    return


def clear_collection(collection):
    for o in collection:
        collection.remove(o)


def clear_all():
    clear_collection(bpy.data.objects)
    clear_collection(bpy.data.actions)
    clear_collection(bpy.data.armatures)
    clear_collection(bpy.data.meshes)
    clear_collection(bpy.data.materials)


def list_fbx_name(directory):
    return list(map(lambda x: x.removesuffix(".fbx"), filter(lambda x: x.endswith(".fbx"), os.listdir(directory))))


def switch_to_edit_mode(armature_object):
    switch_to_mode(armature_object, 'EDIT')


def switch_to_object_mode(armature_object):
    switch_to_mode(armature_object, 'OBJECT')


def switch_to_pose_mode(armature_object):
    switch_to_mode(armature_object, 'POSE')


def switch_to_mode(armature_object, mode):
    bpy.context.view_layer.objects.active = armature_object
    bpy.ops.object.mode_set(mode=mode)


def is_hips_location_curve(data_path: str) -> bool:
    return ('"Hips"' in data_path or "'Hips'" in data_path) and '.location' in data_path


def is_root_location_curve(data_path: str) -> bool:
    return ('"RootMotion"' in data_path or "'RootMotion'" in data_path) and '.location' in data_path


def copy_one_fcurve(source, target):
    source_len = len(source.keyframe_points)
    target_len = len(target.keyframe_points)
    target.keyframe_points.add(count=(source_len - target_len))
    for k in range(source_len):
        source_key = source.keyframe_points[k]
        target_key = target.keyframe_points[k]
        # WARNING, only coordinates are copied, might need more properties
        target_key.co = source_key.co


class FBXModel:
    def __init__(self, source, library, name):
        self.input_path = os.path.join(source, library, name + ".fbx")
        self.name = name
        self.armature = None
        self.root_node = None

    def add_action(self, other_model):
        action = other_model.armature.animation_data.action
        self.armature.animation_data.action = action

    def push_animation(self):
        ad = self.armature.animation_data
        if ad is not None:
            action = ad.action
            if action is not None:
                track = ad.nla_tracks.new()
                track.strips.new(action.name, round(action.frame_range[0]), action)
                track.name = action.name
                ad.action = None

    def load_and_scale(self):
        self.load_armature()
        self.rename_bones()
        self.apply_all_transform()
        self.scale_animation()

    def load_armature(self):
        bpy.ops.import_scene.fbx(filepath=self.input_path)
        self.armature = bpy.context.object
        self.armature.name = self.name
        self.armature.animation_data.action.name = self.name
        self.armature.data.name = self.name

    def rename_bones(self):
        for bone in self.armature.pose.bones:
            name: str = bone.name
            name = name.removeprefix("mixamorig:")
            name = name.removeprefix("mixamorig1:")
            bone.name = name

    def apply_all_transform(self):
        mb = self.armature.matrix_basis
        if hasattr(self.armature.data, "transform"):
            self.armature.data.transform(mb)
        for c in self.armature.children:
            c.matrix_local = mb @ c.matrix_local

        self.armature.matrix_basis = Matrix()

    def scale_animation(self):
        curves = self.armature.animation_data.action.fcurves
        for c in curves:
            if is_hips_location_curve(c.data_path):
                for p in c.keyframe_points:
                    p.co.y *= 0.01

    def setup_root_node(self):
        armature = self.armature.data
        switch_to_edit_mode(self.armature)
        armature.edit_bones["Hips"].parent = self.root_node
        self.copy_xz_hips_location_to_root()

    def copy_xz_hips_location_to_root(self):
        switch_to_pose_mode(self.armature)
        root = self.armature.pose.bones['RootMotion']
        root.location = (0.0, 0.0, 0.0)
        root.keyframe_insert(data_path="location", frame=1)

        hips_curves = [None, None, None]
        root_curves = [None, None, None]

        curves = self.armature.animation_data.action.fcurves
        for c in curves:
            if is_hips_location_curve(c.data_path):
                hips_curves[c.array_index] = c
            if is_root_location_curve(c.data_path):
                root_curves[c.array_index] = c

        copy_one_fcurve(hips_curves[0], root_curves[0])
        copy_one_fcurve(hips_curves[2], root_curves[2])

        curves.remove(hips_curves[0])
        curves.remove(hips_curves[2])

    def delete(self):
        bpy.data.objects.remove(self.armature)

    def add_root_node(self):
        switch_to_edit_mode(self.armature)
        root = self.armature.data.edit_bones.new("RootMotion")
        root.head = (0., 0., 0.)
        root.tail = (0., 0., 0.2)
        self.root_node = root


###########################################################################################################
class Mixamo2Godot:
    def __init__(self, source_dir):
        self.source_dir = source_dir

    def process(self, library, export_gtlf):
        directory = os.path.join(self.source_dir, library);
        names = list_fbx_name(directory)
        if "TPose" not in names:
            raise Exception(f"No 'TPose' found in the directory {directory}")

        print("Processing 'TPose'")

        t_pose = self.create_model(library, "TPose", add_root_node=True)
        t_pose.setup_root_node()
        t_pose.push_animation()

        for name in names:
            if name == "TPose":
                continue
            print(f"Processing '${name}'")
            model = self.create_model(library, name, add_root_node=False)
            t_pose.add_action(model)
            model.delete()
            t_pose.copy_xz_hips_location_to_root()
            t_pose.push_animation()

        switch_to_object_mode(t_pose.armature)

        output = os.path.join(self.source_dir, library+".blend")
        print(f"Save to {output}")
        bpy.ops.wm.save_mainfile(filepath=output)

        if export_gtlf:
	        output_glb = os.path.join(self.source_dir, library+".glb")
        	print(f"Export to {output_glb}")
        	bpy.ops.export_scene.gltf(filepath=output_glb ,export_format='GLB')

    def create_model(self, library, name, add_root_node) -> FBXModel:
        model = FBXModel(self.source_dir, library, name)
        model.load_and_scale()
        if add_root_node:
            model.add_root_node()
        return model


if __name__ == '__main__':
    try:
        main()
        print('DONE')
    except Exception as err:
        raise err
