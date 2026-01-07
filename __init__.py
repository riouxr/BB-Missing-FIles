bl_info = {
    "name": "BB Missing File Manager",
    "author": "Blender Bob & Claude.ai",
    "version": (1, 0, 9),
    "blender": (3, 0, 0),
    "location": "Shader Editor > Sidebar > Missing Files",
    "description": "Manage and relink all missing files (textures, videos, sounds, etc.) in your scene",
    "category": "Material",
}

import bpy
import os
import glob
from bpy.props import StringProperty, IntProperty, BoolProperty
from bpy.types import Operator, Panel, PropertyGroup


def check_udim_exists(filepath):
    """Check if a UDIM texture exists by looking for any tile (1001, 1002, etc.)"""
    if "<UDIM>" not in filepath:
        # Not a UDIM texture, check normally
        return os.path.exists(bpy.path.abspath(filepath))
    
    # Replace <UDIM> with glob pattern to find any tile
    abs_path = bpy.path.abspath(filepath)
    pattern = abs_path.replace("<UDIM>", "[0-9][0-9][0-9][0-9]")
    
    # Check if any files match the pattern
    matches = glob.glob(pattern)
    return len(matches) > 0


def find_udim_file(filepath, search_directory):
    """Find a UDIM texture in the search directory"""
    if "<UDIM>" not in filepath:
        # Not a UDIM texture, check normally
        filename = os.path.basename(filepath)
        potential_path = os.path.join(search_directory, filename)
        return potential_path if os.path.exists(potential_path) else None
    
    # For UDIM textures, search for any tile
    filename = os.path.basename(filepath)
    pattern_filename = filename.replace("<UDIM>", "[0-9][0-9][0-9][0-9]")
    pattern = os.path.join(search_directory, pattern_filename)
    
    matches = glob.glob(pattern)
    if matches:
        # Return the path with <UDIM> placeholder, not a specific tile
        return os.path.join(search_directory, filename)
    
    return None


class MissingFileItem(PropertyGroup):
    """Property group to store missing file information"""
    filepath: StringProperty(name="File Path")
    file_name: StringProperty(name="File Name")
    file_type: StringProperty(name="File Type")  # 'IMAGE', 'MOVIE', 'SOUND', 'LINKED', etc.
    material_names: StringProperty(name="Materials")
    object_names: StringProperty(name="Objects")
    node_names: StringProperty(name="Nodes")
    is_used: BoolProperty(name="Is Used", default=True)
    is_linked: BoolProperty(name="Is Linked", default=False)
    library_path: StringProperty(name="Library Path", default="")
    new_filepath: StringProperty(
        name="New Path",
        description="New file path for the file",
        subtype='FILE_PATH'
    )



class MissingFileSettings(PropertyGroup):
    """Settings for filtering missing files"""
    show_used: BoolProperty(
        name="Show Used",
        description="Show files that are used in the scene",
        default=True
    )
    show_unused: BoolProperty(
        name="Show Unused",
        description="Show files that are not used in the scene",
        default=True
    )
    # Collapse/expand state for each file type
    show_images: BoolProperty(name="Show Images", default=True)
    show_movies: BoolProperty(name="Show Movies", default=True)
    show_sounds: BoolProperty(name="Show Sounds", default=True)
    show_caches: BoolProperty(name="Show Caches", default=True)
    show_linked: BoolProperty(name="Show Linked Files", default=True)



class FILE_OT_scan_missing(Operator):
    """Scan the scene for all missing files"""
    bl_idname = "file.scan_missing"
    bl_label = "Scan for Missing Files"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        # Clear existing list
        context.scene.missing_files.clear()
        
        missing_files = {}
        
        # Scan for missing IMAGE files
        for material in bpy.data.materials:
            if material.use_nodes and material.node_tree:
                for node in material.node_tree.nodes:
                    # Image textures
                    if node.type == 'TEX_IMAGE' and node.image:
                        image = node.image
                        
                        # Skip packed images - they're embedded in the file, not missing!
                        if image.packed_file is not None:
                            continue
                        
                        if image.filepath and not check_udim_exists(image.filepath):
                            filepath = image.filepath
                            
                            if filepath not in missing_files:
                                # Determine if it's linked and what type
                                is_linked = image.library is not None
                                file_type = 'LINKED' if is_linked else 'IMAGE'
                                
                                missing_files[filepath] = {
                                    'file_name': image.name,
                                    'file_type': file_type,
                                    'materials': set(),
                                    'objects': set(),
                                    'node_names': set(),
                                    'is_linked': is_linked,
                                    'library_path': image.library.filepath if is_linked else ''
                                }
                            
                            missing_files[filepath]['materials'].add(material.name)
                            missing_files[filepath]['node_names'].add(node.name)
                            
                            for obj in bpy.data.objects:
                                if obj.type == 'MESH' and obj.data.materials:
                                    if material.name in [mat.name for mat in obj.data.materials if mat]:
                                        missing_files[filepath]['objects'].add(obj.name)
        
        # Scan for missing MOVIE files (video textures)
        for material in bpy.data.materials:
            if material.use_nodes and material.node_tree:
                for node in material.node_tree.nodes:
                    if node.type == 'TEX_IMAGE' and node.image and node.image.source == 'MOVIE':
                        image = node.image
                        
                        # Skip packed movie files
                        if image.packed_file is not None:
                            continue
                        
                        if image.filepath and not check_udim_exists(image.filepath):
                            filepath = image.filepath
                            
                            if filepath not in missing_files:
                                missing_files[filepath] = {
                                    'file_name': image.name,
                                    'file_type': 'MOVIE',
                                    'materials': set(),
                                    'objects': set(),
                                    'node_names': set()
                                }
        
        # Scan for missing movie clips (sequencer, motion tracking)
        for clip in bpy.data.movieclips:
            if clip.filepath and not os.path.exists(bpy.path.abspath(clip.filepath)):
                filepath = clip.filepath
                if filepath not in missing_files:
                    missing_files[filepath] = {
                        'file_name': clip.name,
                        'file_type': 'MOVIE CLIP',
                        'materials': set(),
                        'objects': set(),
                        'node_names': set()
                    }
        
        # Scan for missing SOUND files
        for sound in bpy.data.sounds:
            if sound.filepath and not os.path.exists(bpy.path.abspath(sound.filepath)):
                filepath = sound.filepath
                if filepath not in missing_files:
                    missing_files[filepath] = {
                        'file_name': sound.name,
                        'file_type': 'SOUND',
                        'materials': set(),
                        'objects': set(),
                        'node_names': set()
                    }
        
        # Scan for cache files (Alembic, USD, etc.)
        for obj in bpy.data.objects:
            for modifier in obj.modifiers:
                # Check Mesh Cache modifier
                if modifier.type == 'MESH_CACHE':
                    filepath = modifier.filepath
                    if filepath and not os.path.exists(bpy.path.abspath(filepath)):
                        # Get filename - handle cases where filepath is just a directory
                        filename = os.path.basename(filepath)
                        if not filename:  # filepath is a directory or empty
                            # Try to get filename from the full path
                            abs_path = bpy.path.abspath(filepath)
                            filename = os.path.basename(abs_path.rstrip('/\\'))
                            if not filename:
                                filename = f"{modifier.name}_cache"
                        
                        if filepath not in missing_files:
                            missing_files[filepath] = {
                                'file_name': filename,
                                'file_type': 'CACHE',
                                'materials': set(),
                                'objects': {obj.name},
                                'node_names': set(),
                                'modifier_name': modifier.name  # Store modifier name for reference
                            }

        
        # Add to the collection property
        for filepath, data in missing_files.items():
            item = context.scene.missing_files.add()
            item.filepath = filepath
            item.file_name = data['file_name']
            item.file_type = data['file_type']
            item.material_names = ", ".join(sorted(data['materials'])) if data['materials'] else "(none)"
            item.object_names = ", ".join(sorted(data['objects'])) if data['objects'] else "(unused)"
            item.node_names = ", ".join(sorted(data['node_names'])) if data['node_names'] else "(none)"
            item.is_used = len(data['objects']) > 0
            item.is_linked = data.get('is_linked', False)
            item.library_path = data.get('library_path', '')
        
        self.report({'INFO'}, f"Found {len(missing_files)} missing files")
        return {'FINISHED'}


class FILE_OT_relink_single(Operator):
    """Relink a single missing file and auto-relink other files in the same directory"""
    bl_idname = "file.relink_single"
    bl_label = "Relink File"
    bl_options = {'REGISTER', 'UNDO'}
    
    index: IntProperty()
    
    def invoke(self, context, event):
        item = context.scene.missing_files[self.index]
        
        if not item.new_filepath:
            self.report({'ERROR'}, "Please specify a new file path")
            return {'CANCELLED'}
        
        # Check if path exists
        new_path = bpy.path.abspath(item.new_filepath)
        
        # If it's a folder, proceed directly to execute (no warning needed)
        if os.path.isdir(new_path):
            return self.execute(context)
        
        # Check if file exists (handle UDIM patterns)
        if "<UDIM>" in item.new_filepath:
            # For UDIM, check if any tiles exist
            if not check_udim_exists(item.new_filepath):
                self.report({'ERROR'}, f"No UDIM tiles found for: {new_path}")
                return {'CANCELLED'}
        else:
            # Regular file check
            if not os.path.exists(new_path):
                self.report({'ERROR'}, f"File does not exist: {new_path}")
                return {'CANCELLED'}
        
        # It's a file - check for name/type differences
        old_filename = os.path.basename(item.filepath)
        old_name, old_ext = os.path.splitext(old_filename)
        
        new_filename = os.path.basename(item.new_filepath)
        new_name, new_ext = os.path.splitext(new_filename)
        
        # Check for differences
        name_different = old_name.lower() != new_name.lower()
        ext_different = old_ext.lower() != new_ext.lower()
        
        # Special case: if original has no extension and new file has same base name, allow it
        if not old_ext and old_name.lower() == new_name.lower():
            # Base names match, extension was added - this is OK
            return self.execute(context)
        
        # If different, show warning with custom dialog
        if name_different or ext_different:
            return context.window_manager.invoke_props_dialog(self, width=450)
        
        # No differences, proceed directly
        return self.execute(context)
    
    def draw(self, context):
        item = context.scene.missing_files[self.index]
        layout = self.layout
        
        old_filename = os.path.basename(item.filepath)
        old_name, old_ext = os.path.splitext(old_filename)
        
        # Get the actual new filepath (resolve if it's a folder)
        new_path = bpy.path.abspath(item.new_filepath)
        if os.path.isdir(new_path):
            # If it's a folder, the actual file would be the original filename in that folder
            new_filename = old_filename
        else:
            new_filename = os.path.basename(item.new_filepath)
        
        new_name, new_ext = os.path.splitext(new_filename)
        
        layout.label(text="Warning: File mismatch detected!", icon='ERROR')
        layout.separator()
        
        # Show differences
        if old_name.lower() != new_name.lower():
            box = layout.box()
            box.label(text="Different filename:", icon='INFO')
            col = box.column(align=True)
            col.label(text=f"  Original: {old_name}")
            col.label(text=f"  New:      {new_name}")
        
        if old_ext.lower() != new_ext.lower():
            box = layout.box()
            box.label(text="Different file type:", icon='INFO')
            col = box.column(align=True)
            col.label(text=f"  Original: {old_ext.upper() if old_ext else '(none)'}")
            col.label(text=f"  New:      {new_ext.upper() if new_ext else '(none)'}")
        
        layout.separator()
        layout.label(text="Are you sure you want to relink?")
    
    def execute(self, context):
        item = context.scene.missing_files[self.index]
        
        if not item.new_filepath:
            self.report({'ERROR'}, "Please specify a new file path")
            return {'CANCELLED'}
        
        new_path = bpy.path.abspath(item.new_filepath)
        
        # If user selected a folder, search recursively for all missing files
        if os.path.isdir(new_path):
            print("\n" + "="*80)
            print("RELINK BUTTON - RECURSIVE FOLDER SEARCH")
            print("="*80)
            print(f"Searching folder: {new_path}")
            print(f"Total missing files: {len(context.scene.missing_files)}")
            print()
            
            # Dictionary to store found files: {missing_filepath: found_path}
            found_files = {}
            directories_searched = 0
            
            # Search recursively through the entire folder
            for root, dirs, files in os.walk(new_path):
                directories_searched += 1
                print(f"  [{directories_searched}] Checking: {root}")
                
                # Check each missing file
                for missing_item in context.scene.missing_files:
                    if missing_item.filepath in found_files:
                        continue
                    
                    # Use UDIM-aware search
                    found_path = find_udim_file(missing_item.filepath, root)
                    
                    if found_path:
                        print(f"      ✓ FOUND: {os.path.basename(missing_item.filepath)}")
                        # Convert to relative path if possible
                        if bpy.data.filepath:
                            try:
                                found_path = bpy.path.relpath(found_path)
                            except:
                                pass
                        found_files[missing_item.filepath] = found_path
            
            print(f"\nSearch complete!")
            print(f"Directories searched: {directories_searched}")
            print(f"Files found: {len(found_files)}")
            print("="*80 + "\n")
            
            # Check if we found the primary file at least
            if item.filepath not in found_files:
                self.report({'ERROR'}, f"File '{os.path.basename(item.filepath)}' not found in selected folder or its subdirectories")
                return {'CANCELLED'}
            
            # Relink all found files
            relinked_count = 0
            
            for missing_item in context.scene.missing_files:
                if missing_item.filepath not in found_files:
                    continue
                
                found_path = found_files[missing_item.filepath]
                old_filepath = missing_item.filepath
                
                # Update images
                for image in bpy.data.images:
                    if image.filepath == old_filepath and image.library is None:
                        try:
                            image.filepath = found_path
                            image.reload()
                            relinked_count += 1
                        except:
                            pass
                
                # Update movie clips
                for clip in bpy.data.movieclips:
                    if clip.filepath == old_filepath and clip.library is None:
                        try:
                            clip.filepath = found_path
                            relinked_count += 1
                        except:
                            pass
                
                # Update sounds
                for sound in bpy.data.sounds:
                    if sound.filepath == old_filepath and sound.library is None:
                        try:
                            sound.filepath = found_path
                            relinked_count += 1
                        except:
                            pass
                
                # Update cache modifiers
                for obj in bpy.data.objects:
                    for modifier in obj.modifiers:
                        if hasattr(modifier, 'filepath') and modifier.filepath == old_filepath:
                            try:
                                modifier.filepath = found_path
                                relinked_count += 1
                            except:
                                pass
            
            # Re-scan to update the list
            bpy.ops.file.scan_missing()
            
            num_files = len(found_files)
            if num_files == 1:
                self.report({'INFO'}, f"Found and relinked 1 file ({relinked_count} datablock(s))")
            else:
                self.report({'INFO'}, f"Found and relinked {num_files} files ({relinked_count} datablock(s))")
            
            return {'FINISHED'}
        
        # If it's a specific file (not a folder), use the original logic
        else:
            # Check existence (handle UDIM)
            file_exists = check_udim_exists(item.new_filepath) if "<UDIM>" in item.new_filepath else os.path.exists(new_path)
            if not file_exists:
                self.report({'ERROR'}, f"File does not exist: {new_path}")
                return {'CANCELLED'}
        
        old_filepath = item.filepath
        updated_count = 0
        
        # Update images
        linked_count = 0
        for image in bpy.data.images:
            if image.filepath == old_filepath:
                # Check if this is a linked datablock (read-only)
                if image.library is not None:
                    print(f"DEBUG: Skipping linked image: {image.name} from library: {image.library.filepath}")
                    linked_count += 1
                    continue  # Skip linked datablocks
                try:
                    image.filepath = item.new_filepath
                    image.reload()
                    updated_count += 1
                except Exception as e:
                    self.report({'ERROR'}, f"Failed to reload image: {str(e)}")
                    return {'CANCELLED'}
        
        # Update movie clips
        for clip in bpy.data.movieclips:
            if clip.filepath == old_filepath:
                if clip.library is not None:
                    linked_count += 1
                    continue
                try:
                    clip.filepath = item.new_filepath
                    updated_count += 1
                except Exception as e:
                    self.report({'ERROR'}, f"Failed to update movie clip: {str(e)}")
        
        # Update sounds
        for sound in bpy.data.sounds:
            if sound.filepath == old_filepath:
                if sound.library is not None:
                    linked_count += 1
                    continue
                try:
                    sound.filepath = item.new_filepath
                    updated_count += 1
                except Exception as e:
                    self.report({'ERROR'}, f"Failed to update sound: {str(e)}")
        
        # Update cache modifiers
        for obj in bpy.data.objects:
            for modifier in obj.modifiers:
                if hasattr(modifier, 'filepath') and modifier.filepath == old_filepath:
                    try:
                        modifier.filepath = item.new_filepath
                        updated_count += 1
                    except Exception as e:
                        self.report({'ERROR'}, f"Failed to update cache: {str(e)}")
        
        # Auto-relink other files in the same directory
        new_dir = os.path.dirname(bpy.path.abspath(item.new_filepath))
        auto_relinked = 0
        
        if os.path.exists(new_dir):
            # Get all missing files
            for other_item in context.scene.missing_files:
                if other_item.filepath == old_filepath:
                    continue  # Skip the file we just relinked
                
                # Check if this file exists in the same directory
                other_filename = os.path.basename(other_item.filepath)
                potential_path = os.path.join(new_dir, other_filename)
                
                # Check existence (handle UDIM)
                file_exists = check_udim_exists(potential_path) if "<UDIM>" in potential_path else os.path.exists(potential_path)
                
                if file_exists:
                    # Convert to relative path
                    try:
                        relative_path = bpy.path.relpath(potential_path)
                    except:
                        relative_path = potential_path
                    
                    old_path = other_item.filepath
                    
                    # Update the datablocks
                    for image in bpy.data.images:
                        if image.filepath == old_path and image.library is None:
                            try:
                                image.filepath = relative_path
                                image.reload()
                                auto_relinked += 1
                            except:
                                pass
                    
                    for clip in bpy.data.movieclips:
                        if clip.filepath == old_path:
                            try:
                                clip.filepath = relative_path
                                auto_relinked += 1
                            except:
                                pass
                    
                    for sound in bpy.data.sounds:
                        if sound.filepath == old_path:
                            try:
                                sound.filepath = relative_path
                                auto_relinked += 1
                            except:
                                pass
                    
                    for obj in bpy.data.objects:
                        for modifier in obj.modifiers:
                            if hasattr(modifier, 'filepath') and modifier.filepath == old_path:
                                try:
                                    modifier.filepath = relative_path
                                    auto_relinked += 1
                                except:
                                    pass
        
        # Build success message
        message = f"Relinked {updated_count} file(s)"
        if auto_relinked > 0:
            message += f" + auto-relinked {auto_relinked} other file(s)"
        if linked_count > 0:
            message += f" (WARNING: {linked_count} linked file(s) skipped - they're read-only)"
            self.report({'WARNING'}, message)
        else:
            self.report({'INFO'}, message)
        
        # Re-scan to update the list
        bpy.ops.file.scan_missing()
        
        return {'FINISHED'}


class TEXTURE_OT_browse_file(Operator):
    """Browse for a texture file"""
    bl_idname = "texture.browse_file"
    bl_label = "Browse"
    bl_options = {'REGISTER', 'UNDO'}
    
    filepath: StringProperty(subtype='FILE_PATH')
    index: IntProperty()
    
    def execute(self, context):
        item = context.scene.missing_textures[self.index]
        item.new_filepath = self.filepath
        return {'FINISHED'}
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class FILE_OT_auto_search(Operator):
    """Search recursively for all missing files in common folders and auto-relink them"""
    bl_idname = "file.auto_search"
    bl_label = "Auto Search"
    bl_options = {'REGISTER', 'UNDO'}
    
    index: IntProperty()
    
    def execute(self, context):
        print("\n" + "="*80)
        print("AUTO SEARCH OPERATOR CALLED!")
        print("="*80)
        
        item = context.scene.missing_files[self.index]
        print(f"Looking for: {item.filepath}")
        
        # Get the filename from the original path
        original_filename = os.path.basename(item.filepath)
        
        if not original_filename:
            self.report({'ERROR'}, "Cannot extract filename from path")
            return {'CANCELLED'}
        
        # Check if blend file is saved
        if not bpy.data.filepath:
            print("ERROR: Blend file is not saved!")
            self.report({'ERROR'}, "Please save your blend file first! Auto search needs a base directory to search from.")
            return {'CANCELLED'}
        
        # Search locations
        search_paths = []
        
        # Add blend file directory
        if bpy.data.filepath:
            blend_dir = os.path.dirname(bpy.data.filepath)
            search_paths.append(blend_dir)
            
            # Add common subdirectories
            for subdir in ['textures', 'Textures', 'tex', 'images', 'Images', 'maps', 'Maps']:
                subdir_path = os.path.join(blend_dir, subdir)
                if os.path.exists(subdir_path):
                    search_paths.append(subdir_path)
        
        print("\n" + "="*80)
        print("BB MISSING FILE MANAGER - AUTO SEARCH")
        print("="*80)
        print(f"Starting recursive search for missing files...")
        print(f"Total missing files to search for: {len(context.scene.missing_files)}")
        print(f"\nSearch paths configured: {len(search_paths)}")
        for sp in search_paths:
            print(f"  - {sp}")
        print()
        
        # Dictionary to store found files: {missing_filepath: found_path}
        found_files = {}
        
        # Search recursively through all locations
        directories_searched = 0
        for search_path in search_paths:
            print(f"Searching in: {search_path}")
            # Walk through the entire directory tree
            for root, dirs, files in os.walk(search_path):
                directories_searched += 1
                print(f"  [{directories_searched}] Checking: {root}")
                
                # Check each missing file to see if it exists in this directory
                for missing_item in context.scene.missing_files:
                    # Skip if we already found this file
                    if missing_item.filepath in found_files:
                        continue
                    
                    # Use UDIM-aware search
                    found_path = find_udim_file(missing_item.filepath, root)
                    
                    if found_path:
                        print(f"      ✓ FOUND: {os.path.basename(missing_item.filepath)} in {root}")
                        # Convert to relative path if possible
                        if bpy.data.filepath:
                            try:
                                found_path = bpy.path.relpath(found_path)
                            except:
                                pass
                        found_files[missing_item.filepath] = found_path
        
        print(f"\nSearch complete!")
        print(f"Directories searched: {directories_searched}")
        print(f"Files found: {len(found_files)}")
        if found_files:
            print("\nFound files:")
            for orig_path, new_path in found_files.items():
                print(f"  {os.path.basename(orig_path)} -> {new_path}")
        print("="*80 + "\n")
        
        # Now relink all found files
        relinked_count = 0
        primary_found = False
        
        for missing_item in context.scene.missing_files:
            if missing_item.filepath not in found_files:
                continue
            
            found_path = found_files[missing_item.filepath]
            
            # Track if we found the primary file (the one the user clicked on)
            if missing_item.filepath == item.filepath:
                primary_found = True
                missing_item.new_filepath = found_path
            
            print(f"Relinking: {os.path.basename(missing_item.filepath)}")
            
            # Relink all datablocks using this file
            old_filepath = missing_item.filepath
            
            # Update images
            for image in bpy.data.images:
                if image.filepath == old_filepath and image.library is None:
                    try:
                        image.filepath = found_path
                        image.reload()
                        relinked_count += 1
                    except:
                        pass
            
            # Update movie clips
            for clip in bpy.data.movieclips:
                if clip.filepath == old_filepath and clip.library is None:
                    try:
                        clip.filepath = found_path
                        relinked_count += 1
                    except:
                        pass
            
            # Update sounds
            for sound in bpy.data.sounds:
                if sound.filepath == old_filepath and sound.library is None:
                    try:
                        sound.filepath = found_path
                        relinked_count += 1
                    except:
                        pass
            
            # Update cache modifiers
            for obj in bpy.data.objects:
                for modifier in obj.modifiers:
                    if hasattr(modifier, 'filepath') and modifier.filepath == old_filepath:
                        try:
                            modifier.filepath = found_path
                            relinked_count += 1
                        except:
                            pass
        
        # Re-scan to update the list
        bpy.ops.file.scan_missing()
        
        # Report results
        if not primary_found:
            self.report({'WARNING'}, f"Could not find '{original_filename}' in common locations")
            return {'CANCELLED'}
        
        num_files_found = len(found_files)
        if num_files_found == 1:
            self.report({'INFO'}, f"Found and relinked 1 file ({relinked_count} datablock(s))")
        else:
            self.report({'INFO'}, f"Found and relinked {num_files_found} files ({relinked_count} datablock(s))")
        
        return {'FINISHED'}


class FILE_OT_remove_file(Operator):
    """Remove the unused file datablock from the blend file"""
    bl_idname = "file.remove_file"
    bl_label = "Remove File"
    bl_options = {'REGISTER', 'UNDO'}
    
    index: IntProperty()
    
    def execute(self, context):
        item = context.scene.missing_files[self.index]
        
        removed_count = 0
        
        # Remove images
        images_to_remove = [img for img in bpy.data.images if img.filepath == item.filepath]
        for image in images_to_remove:
            bpy.data.images.remove(image)
            removed_count += 1
        
        # Remove movie clips
        clips_to_remove = [clip for clip in bpy.data.movieclips if clip.filepath == item.filepath]
        for clip in clips_to_remove:
            bpy.data.movieclips.remove(clip)
            removed_count += 1
        
        # Remove sounds
        sounds_to_remove = [sound for sound in bpy.data.sounds if sound.filepath == item.filepath]
        for sound in sounds_to_remove:
            bpy.data.sounds.remove(sound)
            removed_count += 1
        
        self.report({'INFO'}, f"Removed {removed_count} file datablock(s)")
        
        # Re-scan to update the list
        bpy.ops.file.scan_missing()
        
        return {'FINISHED'}
    
    def invoke(self, context, event):
        item = context.scene.missing_files[self.index]
        if item.is_used:
            return context.window_manager.invoke_confirm(self, event)
        return self.execute(context)
    
    def draw(self, context):
        layout = self.layout
        layout.label(text="This file is used in the scene!")
        layout.label(text="Are you sure you want to remove it?")


class FILE_OT_purge_all_orphans(Operator):
    """Remove ALL orphaned data including objects not in any scene (more thorough than Blender's built-in purge)"""
    bl_idname = "file.purge_all_orphans"
    bl_label = "Purge All Orphans"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        removed_count = 0
        
        # Step 0: Run Blender's built-in recursive purge first
        # This removes standard orphaned datablocks (meshes, materials, images with 0 users)
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
        
        # Step 1: Now remove objects not in any scene (Blender's purge doesn't do this)
        objects_to_remove = []
        for obj in bpy.data.objects:
            in_scene = False
            for scene in bpy.data.scenes:
                try:
                    if obj.name in scene.objects.keys():
                        in_scene = True
                        break
                except:
                    pass
            
            if not in_scene:
                objects_to_remove.append(obj)
        
        for obj in objects_to_remove:
            try:
                bpy.data.objects.remove(obj, do_unlink=True)
                removed_count += 1
            except:
                pass
        
        # Step 2: Run the built-in purge again to clean up dependencies
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
        
        self.report({'INFO'}, f"Purged {removed_count} orphaned object(s) + standard orphaned data")
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)
    
    def draw(self, context):
        layout = self.layout
        layout.label(text="This will remove ALL unused data:")
        layout.label(text="- Objects not in any scene")
        layout.label(text="- Materials, images, meshes with 0 users")
        layout.label(text="- Other orphaned datablocks")
        layout.separator()
        layout.label(text="This cannot be easily undone!")


class FILE_OT_export_report(Operator):
    """Export a text file report of all missing files"""
    bl_idname = "file.export_report"
    bl_label = "Export Report"
    bl_options = {'REGISTER'}
    
    filepath: StringProperty(subtype='FILE_PATH')
    
    def execute(self, context):
        if not self.filepath:
            self.report({'ERROR'}, "No filepath specified")
            return {'CANCELLED'}
        
        try:
            with open(self.filepath, 'w') as f:
                f.write("=" * 80 + "\n")
                f.write("MISSING FILES REPORT\n")
                f.write("=" * 80 + "\n\n")
                
                if bpy.data.filepath:
                    f.write(f"Blend File: {bpy.data.filepath}\n\n")
                
                f.write(f"Total Missing Files: {len(context.scene.missing_files)}\n\n")
                
                # Group by type
                files_by_type = {}
                for item in context.scene.missing_files:
                    file_type = item.file_type
                    if file_type not in files_by_type:
                        files_by_type[file_type] = []
                    files_by_type[file_type].append(item)
                
                # Write each type group
                for file_type, items in sorted(files_by_type.items()):
                    f.write("=" * 80 + "\n")
                    f.write(f"{file_type} FILES ({len(items)})\n")
                    f.write("=" * 80 + "\n\n")
                    
                    for item in items:
                        f.write(f"File: {item.file_name}\n")
                        f.write(f"Path: {item.filepath}\n")
                        f.write(f"Status: {'USED' if item.is_used else 'UNUSED'}\n")
                        
                        if item.is_linked:
                            f.write(f"Linked from: {item.library_path}\n")
                        
                        if item.material_names != "(none)":
                            f.write(f"Materials: {item.material_names}\n")
                        if item.object_names != "(unused)":
                            f.write(f"Objects: {item.object_names}\n")
                        if item.node_names != "(none)":
                            f.write(f"Nodes: {item.node_names}\n")
                        
                        f.write("\n" + "-" * 80 + "\n\n")
                
                f.write("\n" + "=" * 80 + "\n")
                f.write("END OF REPORT\n")
                f.write("=" * 80 + "\n")
            
            self.report({'INFO'}, f"Report exported to: {self.filepath}")
            return {'FINISHED'}
        
        except Exception as e:
            self.report({'ERROR'}, f"Failed to export report: {str(e)}")
            return {'CANCELLED'}
    
    def invoke(self, context, event):
        # Set default filename
        if bpy.data.filepath:
            blend_name = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
            self.filepath = os.path.join(os.path.dirname(bpy.data.filepath), f"{blend_name}_missing_files_report.txt")
        else:
            self.filepath = "missing_files_report.txt"
        
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class FILE_PT_missing_panel_shader(Panel):
    """Panel in Shader Editor for missing file management"""
    bl_label = "Missing Files"
    bl_idname = "FILE_PT_missing_panel_shader"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'Missing Files'
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        settings = scene.missing_file_settings
        
        # Purge button (on top)
        row = layout.row()
        row.operator("file.purge_all_orphans", icon='TRASH')
        
        # Main control buttons
        row = layout.row(align=True)
        row.scale_y = 1.5
        row.operator("file.scan_missing", text="Scan for Missing Files", icon='VIEWZOOM')
        
        # Export button
        row = layout.row()
        row.operator("file.export_report", icon='EXPORT')
        
        # Filter buttons
        row = layout.row(align=True)
        row.prop(settings, "show_used", text="Used", toggle=True, icon='CHECKMARK')
        row.prop(settings, "show_unused", text="Unused", toggle=True, icon='X')
        
        layout.separator()
        
        # Display missing files
        if len(scene.missing_files) == 0:
            box = layout.box()
            box.label(text="No missing files found", icon='CHECKMARK')
            box.label(text="Click 'Scan' to check for issues")
        else:
            # Group files by type
            files_by_type = {
                'IMAGE': [],
                'MOVIE': [],
                'SOUND': [],
                'CACHE': [],
                'LINKED': []
            }
            
            for idx, item in enumerate(scene.missing_files):
                # Apply filter
                if item.is_used and not settings.show_used:
                    continue
                if not item.is_used and not settings.show_unused:
                    continue
                
                # Add to appropriate group
                file_type = item.file_type
                if file_type not in files_by_type:
                    file_type = 'IMAGE'  # Default
                files_by_type[file_type].append((idx, item))
            
            # Count total
            total_filtered = sum(len(files) for files in files_by_type.values())
            layout.label(text=f"Missing Files: {len(scene.missing_files)} (Showing: {total_filtered})", icon='ERROR')
            
            # Display each type group
            type_info = [
                ('IMAGE', 'Images', 'IMAGE_DATA', settings.show_images),
                ('MOVIE', 'Movies', 'SEQUENCE', settings.show_movies),
                ('SOUND', 'Sounds', 'SOUND', settings.show_sounds),
                ('CACHE', 'Caches', 'FILE_CACHE', settings.show_caches),
                ('LINKED', 'Linked Files', 'LINK_BLEND', settings.show_linked)
            ]
            
            for file_type, label, icon, show_prop in type_info:
                files = files_by_type[file_type]
                if len(files) == 0:
                    continue
                
                # Type header with collapse button
                type_box = layout.box()
                header_row = type_box.row()
                
                # Determine the correct property name
                if file_type == 'IMAGE':
                    prop_name = "show_images"
                elif file_type == 'MOVIE':
                    prop_name = "show_movies"
                elif file_type == 'SOUND':
                    prop_name = "show_sounds"
                elif file_type == 'CACHE':
                    prop_name = "show_caches"
                elif file_type == 'LINKED':
                    prop_name = "show_linked"
                
                header_row.prop(settings, prop_name,
                               icon='TRIA_DOWN' if show_prop else 'TRIA_RIGHT',
                               text="", emboss=False)
                header_row.label(text=f"{label}: {len(files)}", icon=icon)
                
                # Show files if expanded
                if show_prop:
                    for idx, item in files:
                        box = type_box.box()
                        col = box.column(align=True)
                        
                        # Status indicator row
                        status_row = col.row(align=True)
                        if item.is_used:
                            status_row.label(text="Status: USED IN SCENE", icon='CHECKMARK')
                        else:
                            status_row.label(text="Status: UNUSED", icon='X')
                        
                        # File name
                        col.label(text=f"File: {item.file_name}", icon='TEXTURE')
                        
                        # For linked files, show library path
                        if item.is_linked and item.library_path:
                            split_box = col.box()
                            split_col = split_box.column(align=True)
                            split_col.scale_y = 0.7
                            split_col.label(text="Linked from:")
                            lib_parts = item.library_path.split(os.sep)
                            if len(lib_parts) > 3:
                                split_col.label(text="..." + os.sep + os.sep.join(lib_parts[-3:]))
                            else:
                                split_col.label(text=item.library_path)
                            split_col.label(text="(Read-only - fix in original file)", icon='INFO')
                        
                        # Original path
                        split_box = col.box()
                        split_col = split_box.column(align=True)
                        split_col.scale_y = 0.7
                        split_col.label(text="Original Path:")
                        path_parts = item.filepath.split(os.sep)
                        if len(path_parts) > 3:
                            split_col.label(text="..." + os.sep + os.sep.join(path_parts[-3:]))
                        else:
                            split_col.label(text=item.filepath)
                        split_col.label(text=f"Materials: {item.material_names}")
                        split_col.label(text=f"Objects: {item.object_names}")
                        
                        col.separator(factor=0.5)
                        
                        # Only show relink options for non-linked files
                        if item.is_linked:
                            col.label(text="Linked files cannot be relinked here", icon='INFO')
                        elif item.is_used:
                            # New path input
                            col.prop(item, "new_filepath", text="New Path")
                            
                            # Relink button
                            row = col.row()
                            row.scale_y = 1.3
                            op = row.operator("file.relink_single", text="Relink This File", icon='LINKED')
                            op.index = idx
                            
                            # Auto Find and Delete buttons
                            row = col.row(align=True)
                            op = row.operator("file.auto_search", text="Auto Find", icon='VIEWZOOM')
                            op.index = idx
                            op = row.operator("file.remove_file", text="Delete", icon='TRASH')
                            op.index = idx
                        else:
                            # Unused file
                            col.label(text="This file is not used in any objects")
                            row = col.row()
                            row.scale_y = 1.3
                            op = row.operator("file.remove_file", text="Remove from File", icon='TRASH')
                            op.index = idx
                        
                        type_box.separator(factor=0.5)



classes = (
    MissingFileItem,
    MissingFileSettings,
    FILE_OT_scan_missing,
    FILE_OT_relink_single,
    FILE_OT_auto_search,
    FILE_OT_remove_file,
    FILE_OT_purge_all_orphans,
    FILE_OT_export_report,
    FILE_PT_missing_panel_shader,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Scene.missing_files = bpy.props.CollectionProperty(type=MissingFileItem)
    bpy.types.Scene.missing_file_settings = bpy.props.PointerProperty(type=MissingFileSettings)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    del bpy.types.Scene.missing_files
    del bpy.types.Scene.missing_file_settings


if __name__ == "__main__":
    register()
