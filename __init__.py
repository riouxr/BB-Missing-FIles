bl_info = {
    "name": "BB Missing File Manager",
    "author": "Blender Bob & Claude.ai",
    "version": (1, 0, 1),
    "blender": (3, 0, 0),
    "location": "Shader Editor > Sidebar > Missing Files",
    "description": "Manage and relink all missing files (textures, videos, sounds, etc.) in your scene",
    "category": "Material",
}

import bpy
import os
from bpy.props import StringProperty, IntProperty, BoolProperty
from bpy.types import Operator, Panel, PropertyGroup


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
                        
                        if image.filepath and not os.path.exists(bpy.path.abspath(image.filepath)):
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
                        
                        if image.filepath and not os.path.exists(bpy.path.abspath(image.filepath)):
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
        
        # Scan for missing CACHE files
        for obj in bpy.data.objects:
            # Check modifiers
            for modifier in obj.modifiers:
                if hasattr(modifier, 'filepath'):
                    filepath = modifier.filepath
                    if filepath and not os.path.exists(bpy.path.abspath(filepath)):
                        if filepath not in missing_files:
                            missing_files[filepath] = {
                                'file_name': os.path.basename(filepath),
                                'file_type': 'CACHE',
                                'materials': set(),
                                'objects': {obj.name},
                                'node_names': set()
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
        
        # If file doesn't exist, show error
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
        
        # Remember if this was a folder selection (before we modify new_filepath)
        was_folder_selection = os.path.isdir(new_path)
        original_search_root = new_path if was_folder_selection else None
        
        # If user selected a folder, look for the file with the same name recursively
        if was_folder_selection:
            original_filename = os.path.basename(item.filepath)
            found_path = None
            
            # Search recursively through all subfolders
            for root, dirs, files in os.walk(new_path):
                if original_filename in files:
                    found_path = os.path.join(root, original_filename)
                    break
            
            if found_path:
                # Update the new_filepath to the actual file
                try:
                    item.new_filepath = bpy.path.relpath(found_path)
                except:
                    item.new_filepath = found_path
                
                # Show relative path from selected folder
                rel_to_selected = os.path.relpath(found_path, new_path)
                self.report({'INFO'}, f"Found file: {rel_to_selected}")
                new_path = found_path
            else:
                self.report({'ERROR'}, f"File '{original_filename}' not found in selected folder or subfolders")
                return {'CANCELLED'}
        elif not os.path.exists(new_path):
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
        
        # Update cache file modifiers
        for obj in bpy.data.objects:
            for modifier in obj.modifiers:
                if hasattr(modifier, 'filepath') and modifier.filepath == old_filepath:
                    try:
                        modifier.filepath = item.new_filepath
                        updated_count += 1
                    except Exception as e:
                        self.report({'ERROR'}, f"Failed to update cache: {str(e)}")
        
        # AUTO-RELINK: Check if there are other missing files
        # If we used folder selection, search the entire folder tree
        new_directory = os.path.dirname(bpy.path.abspath(item.new_filepath))
        auto_relinked = 0
        
        # Use the original folder if it was a folder selection, otherwise just the file's directory
        if original_search_root:
            search_root = original_search_root
        else:
            search_root = new_directory
        
        for other_item in context.scene.missing_files:
            if other_item.filepath == old_filepath:
                continue  # Skip the one we just relinked
            
            # Get the filename of the missing file
            missing_filename = os.path.basename(other_item.filepath)
            
            # Search recursively in the root folder
            found_path = None
            for root, dirs, files in os.walk(search_root):
                if missing_filename in files:
                    found_path = os.path.join(root, missing_filename)
                    break
            
            # If we found the file somewhere, relink it
            if found_path:
                # Convert to relative path if possible
                try:
                    relative_path = bpy.path.relpath(found_path)
                except:
                    relative_path = found_path
                
                # Relink this file automatically
                old_path = other_item.filepath
                
                # Update all datablocks with this filepath
                for image in bpy.data.images:
                    if image.filepath == old_path:
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
    """Search for missing file in common folders"""
    bl_idname = "file.auto_search"
    bl_label = "Auto Search"
    bl_options = {'REGISTER', 'UNDO'}
    
    index: IntProperty()
    
    def execute(self, context):
        item = context.scene.missing_files[self.index]
        
        # Get the filename from the original path
        original_filename = os.path.basename(item.filepath)
        
        if not original_filename:
            self.report({'ERROR'}, "Cannot extract filename from path")
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
        
        # Search for the file
        for search_path in search_paths:
            for root, dirs, files in os.walk(search_path):
                if original_filename in files:
                    found_path = os.path.join(root, original_filename)
                    # Convert to relative path if possible
                    if bpy.data.filepath:
                        try:
                            found_path = bpy.path.relpath(found_path)
                        except:
                            pass
                    item.new_filepath = found_path
                    self.report({'INFO'}, f"Found: {found_path}")
                    return {'FINISHED'}
        
        self.report({'WARNING'}, f"Could not find '{original_filename}' in common locations")
        return {'CANCELLED'}


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
            bpy.data.objects.remove(obj)
            removed_count += 1
        
        # Step 2: Run Blender's purge again to clean up anything freed by removing those objects
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
        
        # Step 3: Final cleanup - remove any remaining orphaned datablocks
        # (This is redundant after recursive purge, but ensures everything is clean)
        
        # Remove orphaned meshes
        meshes_to_remove = []
        for mesh in bpy.data.meshes:
            if mesh.users == 0:
                meshes_to_remove.append(mesh)
        
        for mesh in meshes_to_remove:
            bpy.data.meshes.remove(mesh)
            removed_count += 1
        
        # Remove orphaned materials
        materials_to_remove = []
        for mat in bpy.data.materials:
            if mat.users == 0:
                materials_to_remove.append(mat)
        
        for mat in materials_to_remove:
            bpy.data.materials.remove(mat)
            removed_count += 1
        
        # Remove orphaned images
        images_to_remove = []
        for img in bpy.data.images:
            if img.users == 0:
                images_to_remove.append(img)
        
        for img in images_to_remove:
            bpy.data.images.remove(img)
            removed_count += 1
        
        # Remove orphaned sounds
        sounds_to_remove = []
        for sound in bpy.data.sounds:
            if sound.users == 0:
                sounds_to_remove.append(sound)
        
        for sound in sounds_to_remove:
            bpy.data.sounds.remove(sound)
            removed_count += 1
        
        # Remove orphaned movie clips
        clips_to_remove = []
        for clip in bpy.data.movieclips:
            if clip.users == 0:
                clips_to_remove.append(clip)
        
        for clip in clips_to_remove:
            bpy.data.movieclips.remove(clip)
            removed_count += 1
        
        if removed_count > 0:
            self.report({'INFO'}, f"Purged all orphaned data + removed {removed_count} object(s) not in any scene")
        else:
            self.report({'INFO'}, f"Purged all orphaned data (file is clean)")
        
        # Re-scan to update the list
        bpy.ops.file.scan_missing()
        
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)
    
    def draw(self, context):
        layout = self.layout
        layout.label(text="This will perform:")
        layout.label(text="1. Blender's recursive purge (standard cleanup)")
        layout.label(text="2. Remove objects not in any scene")
        layout.label(text="3. Final cleanup pass")
        layout.separator()
        layout.label(text="Are you sure?")


class FILE_OT_export_report(Operator):
    """Export missing files report to a text file"""
    bl_idname = "file.export_report"
    bl_label = "Export Report"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        if not bpy.data.filepath:
            self.report({'ERROR'}, "Save your .blend file first")
            return {'CANCELLED'}
        
        blend_dir = os.path.dirname(bpy.data.filepath)
        report_path = os.path.join(blend_dir, "missing_files_report.txt")
        
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("MISSING FILES REPORT\n")
                f.write(f"Blender File: {bpy.data.filepath}\n")
                f.write("=" * 80 + "\n\n")
                
                for idx, item in enumerate(context.scene.missing_files, 1):
                    f.write(f"{idx}. MISSING FILE:\n")
                    f.write(f"   File Name: {item.file_name}\n")
                    f.write(f"   File Type: {item.file_type}\n")
                    f.write(f"   Original Path: {item.filepath}\n")
                    f.write(f"   Used in Materials: {item.material_names}\n")
                    f.write(f"   Assigned to Objects: {item.object_names}\n")
                    f.write(f"   Node Names: {item.node_names}\n\n")
                
                f.write("=" * 80 + "\n")
                f.write(f"Total missing files: {len(context.scene.missing_files)}\n")
                f.write("=" * 80 + "\n")
            
            self.report({'INFO'}, f"Report exported to: {report_path}")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to export report: {str(e)}")
            return {'CANCELLED'}
        
        return {'FINISHED'}


class FILE_PT_missing_panel_shader(Panel):
    """Panel for managing missing files in Shader Editor"""
    bl_label = "BB Missing File Manager"
    bl_idname = "FILE_PT_missing_panel_shader"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'BB Missing Files'
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        settings = scene.missing_file_settings
        
        # Purge All Orphans button (at the very top - clean first!)
        row = layout.row()
        row.scale_y = 1.3
        row.operator("file.purge_all_orphans", icon='TRASH')
        
        # Scan button
        row = layout.row()
        row.scale_y = 1.5
        row.operator("file.scan_missing", icon='VIEWZOOM')
        
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
