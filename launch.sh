#!/bin/bash

if [ $# -lt 0 ]; then
   echo "Usage $0 (-ne|--no-export) [directory]"
   exit 1
fi

dir=~/.local/opt/mixamo2godot4

blender --background --python ${dir}/mixamo2godot4.py -- "$@"

exit 0
