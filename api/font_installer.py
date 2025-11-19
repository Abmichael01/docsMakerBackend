"""
Utility to install fonts on the system for CairoSVG to use
CairoSVG uses Fontconfig, so fonts must be installed on the system
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List
from .models import Font


def get_system_font_directories():
    """Get system font directories based on OS"""
    font_dirs = []
    
    # Linux font directories
    if os.name == 'posix':
        home = os.path.expanduser("~")
        font_dirs = [
            f"{home}/.local/share/fonts",  # User fonts
            f"{home}/.fonts",  # Legacy user fonts
            "/usr/local/share/fonts",  # System-wide fonts
            "/usr/share/fonts",  # System fonts
        ]
    # Windows (if needed)
    elif os.name == 'nt':
        home = os.path.expanduser("~")
        font_dirs = [
            os.path.join(home, "AppData", "Local", "Microsoft", "Windows", "Fonts"),
            "C:\\Windows\\Fonts",
        ]
    
    return font_dirs


def install_font_to_system(font: Font) -> bool:
    """
    Install a font file to the system so CairoSVG can use it
    
    Args:
        font: Font model instance
        
    Returns:
        True if successful, False otherwise
    """
    if not font.font_file:
        return False
    
    try:
        # Get user font directory (preferred location)
        home = os.path.expanduser("~")
        user_font_dir = Path(f"{home}/.local/share/fonts")
        user_font_dir.mkdir(parents=True, exist_ok=True)
        
        # Get font file data
        try:
            # Try to get path first (works for local storage)
            font_path = font.font_file.path
            if os.path.exists(font_path):
                # File exists on filesystem, copy it
                dest_path = user_font_dir / os.path.basename(font.font_file.name)
                if not dest_path.exists():
                    shutil.copy2(font_path, dest_path)
            else:
                # File not on filesystem, read from storage
                font.font_file.open('rb')
                font_data = font.font_file.read()
                font.font_file.close()
                
                # Write to user font directory
                dest_path = user_font_dir / os.path.basename(font.font_file.name)
                with open(dest_path, 'wb') as f:
                    f.write(font_data)
        except Exception:
            # Fallback: read from storage
            font.font_file.open('rb')
            font_data = font.font_file.read()
            font.font_file.close()
            
            # Write to user font directory
            dest_path = user_font_dir / os.path.basename(font.font_file.name)
            with open(dest_path, 'wb') as f:
                f.write(font_data)
        
        # Update font cache (Linux)
        if os.name == 'posix':
            try:
                # Run fc-cache to update font cache
                subprocess.run(
                    ['fc-cache', '-f', '-v'],
                    capture_output=True,
                    timeout=30,
                    check=False
                )
            except (subprocess.TimeoutExpired, FileNotFoundError):
                # fc-cache not available, that's okay
                pass
        
        return True
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to install font {font.name}: {str(e)}")
        return False


def get_font_family_name_from_file(font: Font) -> str:
    """
    Extract the actual font family name from the font file
    This is what Fontconfig will recognize
    
    Args:
        font: Font model instance
        
    Returns:
        Font family name as recognized by Fontconfig
    """
    if not font.font_file:
        return font.name
    
    try:
        # Use fc-query to get font family name (Linux)
        if os.name == 'posix':
            # Try to get font path
            font_path = None
            try:
                font_path = font.font_file.path
            except:
                # If path doesn't work, check if font is installed
                home = os.path.expanduser("~")
                user_font_dir = Path(f"{home}/.local/share/fonts")
                installed_path = user_font_dir / os.path.basename(font.font_file.name)
                if installed_path.exists():
                    font_path = str(installed_path)
            
            if font_path and os.path.exists(font_path):
                result = subprocess.run(
                    ['fc-query', '--format=%{family}', font_path],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0 and result.stdout.strip():
                    # Fontconfig returns family names separated by commas, take first
                    family_name = result.stdout.strip().split(',')[0].strip()
                    if family_name:
                        return family_name
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        pass
    
    # Fallback: use font name or filename
    if font.name:
        # Remove common suffixes like "Bold", "Regular", etc.
        name = font.name.replace('-Bold', '').replace('-Regular', '').replace('-Medium', '')
        return name
    
    # Last resort: use filename without extension
    if font.font_file:
        filename = os.path.basename(font.font_file.name)
        return os.path.splitext(filename)[0]
    
    return "Arial"  # Ultimate fallback


def ensure_fonts_installed(fonts: List[Font]) -> dict:
    """
    Ensure all fonts are installed on the system
    
    Args:
        fonts: List of Font objects
        
    Returns:
        Dictionary mapping font IDs to their system font family names
    """
    font_map = {}
    
    for font in fonts:
        # Install font to system
        if install_font_to_system(font):
            # Get the actual font family name that Fontconfig recognizes
            family_name = get_font_family_name_from_file(font)
            font_map[font.id] = family_name
        else:
            # Fallback to font name
            font_map[font.id] = font.name
    
    return font_map

