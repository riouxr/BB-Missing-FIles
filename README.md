# BB Missing File Manager

**Authors:** Blender Bob & Claude.ai  
**Version:** 1.0.0

## Features

- **Scan for Missing Files** - Find all missing images, videos, sounds, and cache files
- **Warning Dialogs** - Get warned when relinking files with different names or types
- **Folder Support** - Browse to a folder and automatically find files by name
- **Auto-Relink** - When you relink one file, other missing files in the same directory are automatically relinked
- **Filter by Status** - Show only used or unused files
- **Purge All Orphans** - Remove all orphaned data (objects not in scene, unused meshes, materials, images, etc.)
- **Export Report** - Generate a text file with all missing file details

## Installation

1. Download `bb_missing_file_manager.zip`
2. In Blender, go to Edit → Preferences → Add-ons
3. Click "Install from Disk" and select the ZIP file
4. Enable the "BB Missing File Manager" addon

## Usage

1. Open the Shader Editor
2. Press **N** to show the sidebar
3. Look for the **"BB Missing Files"** tab
4. Click **"Scan for Missing Files"** to find all missing files
5. For each file, you can:
   - Browse to a specific file or folder
   - Use "Auto Find" to search common directories
   - Delete unused file datablocks
6. Click **"Purge All Orphans"** to clean up all orphaned data

## Location

Shader Editor > Sidebar (N) > BB Missing Files tab

## Requirements

Blender 4.2.0 or higher
