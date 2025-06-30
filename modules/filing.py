import streamlit as st
import os
import json
import hashlib
import uuid
from datetime import datetime
from pathlib import Path
import re
import logging
import requests
import base64
import shutil

# Configure logging
logger = logging.getLogger(__name__)

# LLM Provider Configuration
LLM_PROVIDERS = {
    "OpenAI": {
        "name": "OpenAI",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
        "env_key": "OPENAI_API_KEY",
        "available": True
    },
    "Anthropic": {
        "name": "Anthropic",
        "models": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"],
        "env_key": "ANTHROPIC_API_KEY",
        "available": True
    },
    "Mistral": {
        "name": "Mistral",
        "models": ["mistral-large-latest", "mistral-medium-latest", "mistral-small-latest"],
        "env_key": "MISTRAL_API_KEY",
        "available": True
    }
}

def get_common_filing_directories():
    """Get common filing directory suggestions based on OS-level access"""
    import platform
    import os
    from pathlib import Path
    
    system = platform.system()
    home = Path.home()
    common_dirs = {}
    
    # Add home directory
    common_dirs["Home"] = str(home)
    
    # Add Documents directory
    if (home / "Documents").exists():
        common_dirs["Documents"] = str(home / "Documents")
    
    # Add Desktop directory
    if (home / "Desktop").exists():
        common_dirs["Desktop"] = str(home / "Desktop")
    
    # Add Downloads directory
    if (home / "Downloads").exists():
        common_dirs["Downloads"] = str(home / "Downloads")
    
    # Add system-specific directories
    if system == "Windows":
        # Windows specific directories
        if 'USERPROFILE' in os.environ:
            user_profile = Path(os.environ['USERPROFILE'])
            
            # OneDrive
            onedrive = user_profile / "OneDrive"
            if onedrive.exists():
                common_dirs["OneDrive"] = str(onedrive)
            
            # Pictures
            pictures = user_profile / "Pictures"
            if pictures.exists():
                common_dirs["Pictures"] = str(pictures)
            
            # Public Documents
            public = Path(os.environ.get('PUBLIC', 'C:/Users/Public'))
            if (public / "Documents").exists():
                common_dirs["Public Documents"] = str(public / "Documents")
    
    elif system == "Darwin":  # macOS
        # macOS specific directories
        
        # Library
        library = home / "Library"
        if library.exists():
            common_dirs["Library"] = str(library)
        
        # Applications
        applications = Path("/Applications")
        if applications.exists():
            common_dirs["Applications"] = str(applications)
        
        # iCloud Drive
        icloud = home / "Library/Mobile Documents/com~apple~CloudDocs"
        if icloud.exists():
            common_dirs["iCloud Drive"] = str(icloud)
    
    elif system == "Linux":
        # Linux specific directories
        xdg_config_home = os.environ.get('XDG_CONFIG_HOME', str(home / '.config'))
        if Path(xdg_config_home).exists():
            common_dirs["Config"] = xdg_config_home
        
        # Common Linux directories
        for dir_name in ['Pictures', 'Music', 'Videos']:
            dir_path = home / dir_name
            if dir_path.exists():
                common_dirs[dir_name] = str(dir_path)
    
    # Always add Custom option last
    common_dirs["Custom"] = "Enter custom path..."
    
    return common_dirs

def create_folder_structure(base_path, folder_path):
    """Create the folder structure if it doesn't exist"""
    try:
        full_path = Path(base_path) / folder_path
        full_path.mkdir(parents=True, exist_ok=True)
        return str(full_path)
    except Exception as e:
        return None

def open_file_path(path):
    """Open a file path in the system file explorer"""
    try:
        import platform
        import subprocess
        
        # Convert to absolute path if needed
        abs_path = Path(path).resolve()
        
        if platform.system() == "Darwin":  # macOS
            subprocess.run(["open", str(abs_path)])
        elif platform.system() == "Windows":
            subprocess.run(["explorer", str(abs_path)])
        elif platform.system() == "Linux":
            subprocess.run(["xdg-open", str(abs_path)])
        else:
            return False
        
        return True
    except Exception as e:
        return False

def crawl_file_system(base_directory, max_depth=3, max_files=100):
    """Crawl the file system to understand existing organization patterns"""
    try:
        base_path = Path(base_directory)
        if not base_path.exists():
            return {"error": f"Base directory does not exist: {base_directory}"}
        
        structure = {
            "base_directory": str(base_path),
            "folders": {},
            "file_patterns": {},
            "common_extensions": {},
            "naming_patterns": [],
            "depth_analysis": {},
            "debug_info": {
                "total_dirs_found": 0,
                "total_files_found": 0,
                "crawl_depth": 0,
                "folders_by_depth": {},
                "os_walk_samples": []
            }
        }
        
        file_count = 0
        dir_count = 0
        
        # Debug: Check what's in the base directory
        try:
            base_contents = list(base_path.iterdir())
            structure["debug_info"]["base_directory_contents"] = [f"{item.name} ({'dir' if item.is_dir() else 'file'})" for item in base_contents]
            
            # Directly count folders in base directory
            base_folders = [item for item in base_contents if item.is_dir()]
            structure["debug_info"]["base_folders_count"] = len(base_folders)
            structure["debug_info"]["base_folders"] = [folder.name for folder in base_folders]
            
        except PermissionError as e:
            structure["debug_info"]["base_directory_error"] = f"PermissionError: {str(e)}"
            logger.error(f"PermissionError: {str(e)}")
            return {"error": f"Permission denied: {base_directory}. See your OS settings to allow access."}
        except Exception as e:
            structure["debug_info"]["base_directory_error"] = str(e)
            logger.error(f"Error: {str(e)}")
        
        # Initialize depth 0 for the base directory itself
        structure["folders"][0] = {"base": 1}
        
        # Add special handling for depth 1 (immediate children)
        structure["folders"][1] = {}
        for item in base_contents:
            if item.is_dir():
                dir_name = item.name
                structure["folders"][1][dir_name] = 1
                dir_count += 1
                
                # Track folders by depth for debugging
                if 1 not in structure["debug_info"]["folders_by_depth"]:
                    structure["debug_info"]["folders_by_depth"][1] = []
                structure["debug_info"]["folders_by_depth"][1].append(dir_name)
        
        # Crawl the directory structure with os.walk for deeper levels
        walk_count = 0
        for root, dirs, files in os.walk(base_path):
            # Store sample os.walk data for debugging
            if walk_count < 5:  # Store first 5 samples
                structure["debug_info"]["os_walk_samples"].append({
                    "root": str(root),
                    "dirs": dirs.copy(),
                    "files": [f for f in files[:10]]  # First 10 files
                })
                walk_count += 1
            
            if file_count >= max_files:
                break
                
            try:
                rel_path = Path(root).relative_to(base_path)
                depth = len(rel_path.parts)
            except ValueError:
                # Handle case where rel_path can't be determined
                depth = 0
            
            if depth > max_depth:
                continue
            
            # Debug: Track what we're finding
            structure["debug_info"]["crawl_depth"] = max(structure["debug_info"]["crawl_depth"], depth)
            
            # Skip depth 1 since we already handled it directly
            if depth >= 2:
                # Analyze folder structure
                for dir_name in dirs:
                    dir_count += 1
                    if depth not in structure["folders"]:
                        structure["folders"][depth] = {}
                    if dir_name not in structure["folders"][depth]:
                        structure["folders"][depth][dir_name] = 0
                    structure["folders"][depth][dir_name] += 1
                    
                    # Track folders by depth for debugging
                    if depth not in structure["debug_info"]["folders_by_depth"]:
                        structure["debug_info"]["folders_by_depth"][depth] = []
                    structure["debug_info"]["folders_by_depth"][depth].append(dir_name)
            
            # Analyze files
            for file_name in files:
                if file_count >= max_files:
                    break
                    
                file_count += 1
                file_path = Path(root) / file_name
                file_ext = file_path.suffix.lower()
                
                # Count file extensions
                if file_ext not in structure["common_extensions"]:
                    structure["common_extensions"][file_ext] = 0
                structure["common_extensions"][file_ext] += 1
                
                # Analyze naming patterns
                name_without_ext = file_path.stem
                if name_without_ext:
                    # Look for common patterns (dates, numbers, underscores, etc.)
                    if any(char.isdigit() for char in name_without_ext):
                        structure["naming_patterns"].append("contains_numbers")
                    if "_" in name_without_ext:
                        structure["naming_patterns"].append("uses_underscores")
                    if "-" in name_without_ext:
                        structure["naming_patterns"].append("uses_hyphens")
                    if any(char.isupper() for char in name_without_ext):
                        structure["naming_patterns"].append("uses_capitals")
        
        # Update debug info
        structure["debug_info"]["total_dirs_found"] = dir_count
        structure["debug_info"]["total_files_found"] = file_count
        
        # Analyze depth patterns
        for depth, folders in structure["folders"].items():
            structure["depth_analysis"][depth] = {
                "total_folders": len(folders),
                "most_common": sorted(folders.items(), key=lambda x: x[1], reverse=True)[:5]
            }
        
        # Get most common patterns
        structure["naming_patterns"] = list(set(structure["naming_patterns"]))
        structure["common_extensions"] = dict(sorted(
            structure["common_extensions"].items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:10])
        
        return structure
        
    except Exception as e:
        logger.error(f"Error crawling file system: {str(e)}")
        return {"error": f"Error crawling file system: {str(e)}"}

def analyze_existing_structure(base_directory):
    """Analyze existing file system structure for filing patterns"""
    structure = crawl_file_system(base_directory)
    
    if "error" in structure:
        return structure
    
    # Extract insights from the structure
    insights = {
        "base_directory": structure["base_directory"],
        "folder_hierarchy": {},
        "naming_conventions": [],
        "file_types": [],
        "suggestions": [],
        "debug_info": structure["debug_info"]  # Include debug info
    }
    
    # Analyze folder hierarchy
    for depth, folders in structure["folders"].items():
        insights["folder_hierarchy"][f"depth_{depth}"] = {
            "all_folders": list(folders.keys()),
            "common_folders": [name for name, count in folders.items() if count > 1],
            "total_unique": len(folders)
        }
    
    # Analyze naming conventions
    pattern_counts = {}
    for pattern in structure["naming_patterns"]:
        pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
    
    insights["naming_conventions"] = [
        pattern for pattern, count in sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)
    ]
    
    # Analyze file types
    insights["file_types"] = [
        ext for ext, count in structure["common_extensions"].items() 
        if count > 1
    ]
    
    # Generate suggestions based on existing patterns
    if structure["folders"].get(1):
        level1_folders = structure["folders"][1]
        insights["suggestions"].append(f"Top-level folders: {', '.join(list(level1_folders.keys())[:5])}")
    
    if structure["naming_patterns"]:
        insights["suggestions"].append(f"Naming patterns: {', '.join(structure['naming_patterns'][:3])}")
    
    return insights 

def suggest_filing_location(structured_data, base_directory, existing_structure):
    """Dynamically suggest filing location based on actual file system content analysis"""
    
    # Extract document information
    doc_type = structured_data.get('intent', '').lower()
    doc_category = structured_data.get('category', '').lower()
    entities = structured_data.get('key_entities', [])
    summary = structured_data.get('summary', '').lower()
    
    # Get ALL discovered folders and files from the crawl
    all_folders = existing_structure.get('folders', {})
    all_files = existing_structure.get('file_patterns', {})
    common_extensions = existing_structure.get('common_extensions', {})
    
    # Analyze the document content more deeply
    doc_keywords = []
    if doc_type:
        doc_keywords.append(doc_type)
    if doc_category:
        doc_keywords.append(doc_category)
    if summary:
        # Extract key words from summary
        words = summary.split()
        doc_keywords.extend([w for w in words if len(w) > 3 and w.isalpha()])
    if entities:
        doc_keywords.extend([str(e).lower() for e in entities if isinstance(e, str)])
    
    # Find the best matching folder by analyzing ALL folders
    best_folder_path = ""
    best_score = 0
    best_evidence = []
    is_new_folder = True
    
    # First, check if any existing folders match
    for depth, folders in all_folders.items():
        for folder_name, folder_count in folders.items():
            folder_lower = folder_name.lower()
            score = 0
            evidence = []
            
            # Score based on direct keyword matching
            for keyword in doc_keywords:
                if keyword in folder_lower:
                    score += 5
                    evidence.append(f"Keyword '{keyword}' found in existing folder '{folder_name}'")
            
            # Score based on semantic similarity
            if doc_type in ['invoice', 'receipt', 'payment', 'bill']:
                if any(word in folder_lower for word in ['financial', 'finance', 'money', 'billing', 'invoice', 'receipt', 'payment', 'expense', 'accounting']):
                    score += 8
                    evidence.append(f"Financial document matches existing folder '{folder_name}'")
            
            if doc_type in ['contract', 'agreement', 'legal']:
                if any(word in folder_lower for word in ['legal', 'contract', 'agreement', 'law', 'compliance', 'terms']):
                    score += 8
                    evidence.append(f"Legal document matches existing folder '{folder_name}'")
            
            if doc_type in ['report', 'analysis', 'study']:
                if any(word in folder_lower for word in ['report', 'analysis', 'study', 'research', 'data', 'analytics']):
                    score += 8
                    evidence.append(f"Report document matches existing folder '{folder_name}'")
            
            # Score based on entity matching (client names, companies)
            if entities:
                for entity in entities:
                    if isinstance(entity, str):
                        entity_lower = entity.lower()
                        if entity_lower in folder_lower or any(word in folder_lower for word in entity_lower.split()):
                            score += 6
                            evidence.append(f"Entity '{entity}' matches existing folder '{folder_name}'")
            
            # Score based on folder frequency (more established folders get higher scores)
            score += min(folder_count, 5)  # Cap at 5 points for frequency
            
            # Score based on depth (prefer shallower folders for general organization)
            depth_penalty = depth * 0.5
            score -= depth_penalty
            
            # Check if this folder contains similar file types
            if common_extensions:
                doc_ext = structured_data.get('file_type', '').lower()
                if doc_ext in common_extensions:
                    score += 3
                    evidence.append(f"Existing folder contains similar file types ({doc_ext})")
            
            if score > best_score:
                best_score = score
                best_folder_path = folder_name
                best_evidence = evidence
                is_new_folder = False
    
    # If no good match found or score is too low, suggest a new folder
    if best_score < 5:
        # Create a new folder based on document type and content
        if doc_type in ['invoice', 'receipt', 'payment', 'bill']:
            best_folder_path = "Financial_Documents"
            best_evidence = ["Creating new Financial Documents folder for financial documents"]
        elif doc_type in ['contract', 'agreement', 'legal']:
            best_folder_path = "Legal_Documents"
            best_evidence = ["Creating new Legal Documents folder for legal documents"]
        elif doc_type in ['report', 'analysis', 'study']:
            best_folder_path = "Reports_and_Analysis"
            best_evidence = ["Creating new Reports and Analysis folder for reports"]
        elif doc_type in ['policy', 'handbook', 'procedure']:
            best_folder_path = "Policies_and_Procedures"
            best_evidence = ["Creating new Policies and Procedures folder for policy documents"]
        else:
            # Use the most relevant keyword from the document
            if doc_keywords:
                folder_name = "_".join([kw.title() for kw in doc_keywords[:2]])
                best_folder_path = f"{folder_name}_Documents"
                best_evidence = [f"Creating new folder based on document keywords: {folder_name}"]
            else:
                best_folder_path = "Other_Documents"
                best_evidence = ["Creating new general documents folder"]
        
        is_new_folder = True
        best_evidence.insert(0, "⚠️ No matching existing folders found")
    
    # Add year subfolder for time-sensitive documents
    if doc_type in ['invoice', 'receipt', 'contract', 'report']:
        current_year = str(datetime.now().year)
        # Check if year-based organization exists
        year_folder_exists = False
        for depth, folders in all_folders.items():
            for folder in folders.keys():
                if current_year in folder or any(str(year) in folder for year in range(2020, datetime.now().year + 1)):
                    year_folder_exists = True
                    break
        
        if year_folder_exists:
            best_folder_path = f"{best_folder_path}/{current_year}"
            best_evidence.append(f"Added year folder '{current_year}' based on existing pattern")
        else:
            best_folder_path = f"{best_folder_path}/{current_year}"
            best_evidence.append(f"Creating new year folder '{current_year}' for organization")
            is_new_folder = True
    
    return best_folder_path, best_evidence, is_new_folder

def generate_filename(structured_data, existing_structure):
    """Generate filename based on document content and existing naming conventions"""
    
    # Extract document information
    doc_type = structured_data.get('intent', '').lower()
    entities = structured_data.get('key_entities', [])
    original_name = structured_data.get('filename', 'document')
    
    # Get existing naming conventions
    naming_conventions = existing_structure.get('naming_conventions', [])
    
    # Build filename
    filename_parts = []
    
    # Add document type
    if doc_type:
        filename_parts.append(doc_type)
    
    # Add entity/client name
    if entities:
        for entity in entities:
            if isinstance(entity, str) and any(word in entity.lower() for word in ['corp', 'inc', 'ltd', 'company', 'llc']):
                clean_entity = "".join(c for c in entity if c.isalnum() or c in (' ', '-', '_')).strip()
                filename_parts.append(clean_entity.replace(' ', '_'))
                break
    
    # Add date
    current_date = datetime.now().strftime("%Y%m%d")
    filename_parts.append(current_date)
    
    # Combine parts based on existing conventions
    if "uses_underscores" in naming_conventions:
        filename = "_".join(filename_parts)
    elif "uses_hyphens" in naming_conventions:
        filename = "-".join(filename_parts)
    else:
        filename = "_".join(filename_parts)  # Default to underscores
    
    # Add extension
    original_ext = Path(original_name).suffix
    if original_ext:
        filename += original_ext
    else:
        filename += ".pdf"  # Default extension
    
    return filename.lower() 

def save_file(file_content, filename, destination_path):
    """Save a file to the specified path with OS-level awareness"""
    try:
        # Convert to Path object and resolve to absolute path
        dest_path = Path(destination_path).resolve()
        
        # Check if destination exists and is writable
        if not dest_path.exists():
            try:
                dest_path.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                return {
                    "success": False,
                    "error": f"Permission denied: Cannot create directory {dest_path}"
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to create directory {dest_path}: {str(e)}"
                }
        elif not os.access(str(dest_path), os.W_OK):
            return {
                "success": False,
                "error": f"Permission denied: Directory {dest_path} is not writable"
            }
        
        # Create the full file path
        file_path = dest_path / filename
        
        # Check if file already exists
        if file_path.exists():
            # Get file info
            stat_info = file_path.stat()
            size = stat_info.st_size
            modified = datetime.fromtimestamp(stat_info.st_mtime)
            
            # Add timestamp to filename
            name_part = file_path.stem
            ext_part = file_path.suffix
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_filename = f"{name_part}_{timestamp}{ext_part}"
            file_path = dest_path / new_filename
            
            logger.info(f"File {filename} already exists (size: {size}, modified: {modified}). Using {new_filename}")
        
        # Try to write the file
        try:
            with open(file_path, 'wb') as f:
                f.write(file_content)
        except PermissionError:
            return {
                "success": False,
                "error": f"Permission denied: Cannot write to {file_path}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to write file {file_path}: {str(e)}"
            }
        
        # Get saved file info
        stat_info = file_path.stat()
        
        return {
            "success": True,
            "path": str(file_path),
            "size": stat_info.st_size,
            "modified": datetime.fromtimestamp(stat_info.st_mtime),
            "renamed": file_path.name != filename
        }
        
    except Exception as e:
        logger.error(f"Error saving file: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def browse_for_folder():
    """Open a folder browser dialog using the native OS file dialog"""
    import platform
    import subprocess
    import tempfile
    
    system = platform.system()
    
    try:
        if system == "Darwin":  # macOS
            # Use AppleScript to show folder selection dialog
            script = '''
            tell application "System Events"
                activate
                set folderPath to choose folder with prompt "Select a folder to save the file"
                return POSIX path of folderPath
            end tell
            '''
            proc = subprocess.Popen(['osascript', '-e', script], 
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE)
            path, err = proc.communicate()
            if path:
                return path.decode('utf-8').strip()
                
        elif system == "Windows":
            # Use PowerShell to show folder selection dialog
            script = '''
            Add-Type -AssemblyName System.Windows.Forms
            $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
            $dialog.Description = "Select a folder to save the file"
            $dialog.ShowNewFolderButton = $true
            if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
                Write-Output $dialog.SelectedPath
            }
            '''
            with tempfile.NamedTemporaryFile(suffix='.ps1', delete=False) as f:
                f.write(script.encode('utf-16'))
                ps_file = f.name
            
            proc = subprocess.Popen(['powershell', '-ExecutionPolicy', 'Bypass', '-File', ps_file],
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE)
            path, err = proc.communicate()
            os.unlink(ps_file)
            if path:
                return path.decode('utf-8').strip()
                
        elif system == "Linux":
            # Use zenity for folder selection
            proc = subprocess.Popen(['zenity', '--file-selection', '--directory', 
                                   '--title=Select a folder to save the file'],
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE)
            path, err = proc.communicate()
            if path:
                return path.decode('utf-8').strip()
    
    except Exception as e:
        logger.error(f"Error in folder browser: {str(e)}")
        return None
    
    return None

def display_filing_results(filing_result, original_filename, file_content, base_directory):
    """Display the filing analysis results and allow user to confirm"""
    logger.info(f"Starting display_filing_results for {original_filename}")
    logger.info(f"Initial file_content size: {len(file_content) if file_content else 'None'}")
    
    # Initialize session state for filing results if not exists
    if 'filing_state' not in st.session_state:
        logger.info("Initializing filing_state in session state")
        st.session_state.filing_state = {}
    
    # Generate a unique key for this file
    file_key = hashlib.md5(f"{original_filename}_{base_directory}".encode()).hexdigest()
    logger.info(f"Generated file_key: {file_key}")
    
    # Initialize the state for this file if not exists
    if file_key not in st.session_state.filing_state:
        logger.info(f"Initializing state for file_key: {file_key}")
        st.session_state.filing_state[file_key] = {
            'show_save_ui': True,
            'selected_folder': None,
            'current_filename': original_filename,
            'save_attempted': False,
            'save_result': None,
            'save_clicked': False,
            'file_content': file_content  # Store file content in session state
        }
        logger.info(f"Stored file_content size in state: {len(file_content) if file_content else 'None'}")
    elif file_content is not None:  # Update file content if provided
        logger.info(f"Updating file_content for existing state: {file_key}")
        logger.info(f"New file_content size: {len(file_content)}")
        st.session_state.filing_state[file_key]['file_content'] = file_content
    
    # Log current state
    current_state = st.session_state.filing_state[file_key]
    logger.info(f"Current state for {file_key}:")
    logger.info(f"- save_clicked: {current_state['save_clicked']}")
    logger.info(f"- save_attempted: {current_state['save_attempted']}")
    logger.info(f"- file_content size: {len(current_state['file_content']) if current_state.get('file_content') else 'None'}")
    
    # If we have a new filing result, update the state
    if filing_result:
        if filing_result.get("error"):
            logger.error(f"Filing Analysis Error: {filing_result['error']}")
            st.error(f"Filing Analysis Error: {filing_result['error']}")
            return None
        
        if filing_result.get("success"):
            try:
                filing_data = json.loads(filing_result['analysis'])
                logger.info("Successfully parsed filing analysis")
                st.session_state.filing_state[file_key].update({
                    'filing_data': filing_data,
                    'provider': filing_result['provider'],
                    'model': filing_result['model']
                })
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse filing analysis: {str(e)}")
                st.error("Failed to parse filing analysis response")
                return None
    
    # Get the current state for this file
    current_state = st.session_state.filing_state[file_key]
    if 'filing_data' not in current_state:
        logger.warning(f"No filing_data found in state for {file_key}")
        return None
    
    filing_data = current_state['filing_data']
    
    # Always show the success message and UI if we have filing data
    st.success(f"✅ Filing analysis completed using {current_state['provider']} ({current_state['model']})")
    
    # Display filing suggestions
    st.subheader("📁 Document Filing Suggestions")
    
    # Use a form to handle the save action
    form_key = f"save_form_{file_key}"
    logger.info(f"Creating form with key: {form_key}")
    with st.form(key=form_key):
        # Create three columns for better layout
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            st.write("**Suggested Path:**")
            # Use the selected folder if exists, otherwise use the suggested path
            display_path = current_state['selected_folder'] or filing_data.get('suggested_path', 'N/A')
            full_path = Path(base_directory) / display_path
            
            if full_path.exists():
                st.code(display_path)
            else:
                st.code(f"📝 NEW: {display_path}")
                st.info("This folder will be created when you save the file")
            
            # Add folder browser button (outside form)
            if st.form_submit_button("📂 Browse for Different Folder"):
                logger.info("Folder browser button clicked")
                custom_path = browse_for_folder()
                if custom_path:
                    relative_path = str(Path(custom_path).relative_to(Path(base_directory)))
                    logger.info(f"Selected new path: {relative_path}")
                    st.session_state.filing_state[file_key]['selected_folder'] = relative_path
                    st.success(f"Selected folder: {custom_path}")
        
        with col2:
            st.write("**Filename:**")
            # Use the current filename from state
            new_filename = st.text_input(
                "Edit filename if needed",
                value=current_state['current_filename'],
                key=f"filename_input_{file_key}"
            )
            
            # Show file extension options if needed
            original_ext = Path(new_filename).suffix
            if not original_ext:
                extensions = ['.pdf', '.txt', '.doc', '.docx']
                selected_ext = st.selectbox(
                    "Select file extension",
                    extensions,
                    index=0,
                    key=f"ext_select_{file_key}"
                )
                new_filename = f"{new_filename}{selected_ext}"
            
            # Update filename in state
            logger.info(f"Updating filename in state: {new_filename}")
            st.session_state.filing_state[file_key]['current_filename'] = new_filename
        
        with col3:
            st.write("**Actions:**")
            # Save button inside form
            save_submitted = st.form_submit_button("💾 Save Document")
            if save_submitted:
                logger.info("Save button clicked")
                st.session_state.filing_state[file_key]['save_clicked'] = True
                logger.info(f"Updated save_clicked to True for {file_key}")
    
    # Handle save action outside the form
    if st.session_state.filing_state[file_key]['save_clicked']:
        logger.info("Processing save action")
        # Get file content from session state
        saved_file_content = st.session_state.filing_state[file_key]['file_content']
        logger.info(f"Retrieved file_content from state, size: {len(saved_file_content) if saved_file_content else 'None'}")
        
        if saved_file_content:
            # Get the save path from state
            save_path = Path(base_directory) / (current_state['selected_folder'] or filing_data.get('suggested_path', 'Documents'))
            logger.info(f"Save path: {save_path}")
            
            # Save the file with enhanced error handling
            logger.info("Attempting to save file")
            result = save_file(saved_file_content, new_filename, save_path)
            logger.info(f"Save result: {result}")
            
            # Update state with save result
            st.session_state.filing_state[file_key].update({
                'save_attempted': True,
                'save_result': result,
                'save_clicked': False  # Reset the click state
            })
            logger.info("Updated state with save result")
            
            # Show save result
            if result['success']:
                logger.info("File saved successfully")
                st.success("✅ File saved successfully!")
                # Show file details
                st.info(
                    f"📄 File: {result['path']}\n"
                    f"📊 Size: {result['size']} bytes\n"
                    f"🕒 Modified: {result['modified']}\n"
                    f"{'🔄 Renamed' if result.get('renamed') else '✍️ Original name'}"
                )
                
                # Add button to open containing folder (outside form)
                if st.button("📂 Open Containing Folder", key=f"open_folder_{file_key}"):
                    logger.info(f"Opening folder: {Path(result['path']).parent}")
                    open_file_path(Path(result['path']).parent)
            else:
                logger.error(f"Failed to save file: {result.get('error')}")
                st.error(f"❌ Failed to save file: {result.get('error', 'Unknown error')}")
                # Show troubleshooting info
                with st.expander("🔍 Troubleshooting Information"):
                    st.write("**Error Details:**")
                    st.code(result.get('error', 'No detailed error information available'))
                    st.write("**Possible Solutions:**")
                    st.write("1. Check if you have write permissions")
                    st.write("2. Ensure the path is accessible")
                    st.write("3. Try a different location using the Browse button")
        else:
            logger.error(f"No file content available in state for {original_filename}")
            st.error("❌ No file content available to save")
    
    # Display additional file information
    with st.expander("📋 Additional Information", expanded=True):
        st.write("**Category:**", filing_data.get('category', 'N/A'))
        st.write("**Priority:**", filing_data.get('priority', 'N/A'))
        st.write("**Tags:**", ", ".join(filing_data.get('tags', [])))
        st.write("**Confidence:**", filing_data.get('confidence', 'N/A'))
        
        if filing_data.get('alternatives'):
            st.write("**Alternative Locations:**")
            for i, alt in enumerate(filing_data['alternatives']):
                if st.button(f"📁 Use {alt}", key=f"alt_{file_key}_{i}"):
                    logger.info(f"Selected alternative path: {alt}")
                    st.session_state.filing_state[file_key]['selected_folder'] = alt
    
    logger.info(f"Completed display_filing_results for {original_filename}")
    return filing_data

def request_save_file(doc_index, result, filing_data, base_directory, rename_file=True, custom_filename=None):
    """Request a file save operation to be performed after Streamlit rerun"""
    # Store parameters in session state
    st.session_state.file_operations['save_requested'] = True
    st.session_state.file_operations['save_file_index'] = doc_index
    st.session_state.file_operations['save_params'] = {
        'result': result,
        'filing_data': filing_data,
        'base_directory': base_directory,
        'rename_file': rename_file,
        'custom_filename': custom_filename
    }

def perform_save_operation():
    """Perform the actual save operation using parameters from session state"""
    logger.info("Starting perform_save_operation")
    
    if not st.session_state.file_operations['save_requested']:
        logger.info("No save operation requested")
        return
    
    # Get parameters from session state
    doc_index = st.session_state.file_operations['save_file_index']
    params = st.session_state.file_operations['save_params']
    
    logger.info(f"Save operation requested for document index {doc_index}")
    
    if not params:
        logger.warning("No save parameters found")
        st.session_state.file_operations['save_requested'] = False
        return
    
    result = params['result']
    filing_data = params['filing_data']
    base_directory = params['base_directory']
    rename_file = params['rename_file']
    custom_filename = params['custom_filename']
    
    logger.info(f"Save parameters: base_directory={base_directory}, rename_file={rename_file}, custom_filename={custom_filename}")
    
    try:
        # Create folder structure
        suggested_path = filing_data.get('suggested_path', 'Documents')
        folder_path = create_folder_structure(base_directory, suggested_path)
        logger.info(f"Created folder structure: {folder_path}")
        
        if folder_path:
            # Determine filename
            if rename_file and custom_filename:
                filename = custom_filename
            else:
                filename = result['filename']
            
            logger.info(f"Using filename: {filename}")
            
            # Ensure filename has extension
            if not Path(filename).suffix and Path(result['filename']).suffix:
                filename = f"{filename}{Path(result['filename']).suffix}"
                logger.info(f"Added extension to filename: {filename}")
            
            # Save the file
            if result.get('file_content'):
                logger.info("File content available, proceeding with save")
                save_result = save_file(
                    file_content=result['file_content'],
                    filename=filename,
                    destination_path=folder_path
                )
                
                logger.info(f"Save result: {save_result}")
                
                # Store the result
                st.session_state.file_operations['last_save_result'] = {
                    'success': save_result.get('success', False),
                    'path': save_result.get('path', ''),
                    'size': save_result.get('size', 0),
                    'renamed': save_result.get('renamed', False),
                    'type': result.get('structured_data', {}).get('file_type', 'Unknown'),
                    'error': save_result.get('error', '')
                }
                
                # Update document state for persistence
                doc_state_key = f"doc_state_{doc_index}"
                if doc_state_key not in st.session_state:
                    st.session_state[doc_state_key] = {}
                
                st.session_state[doc_state_key]["save_attempted"] = True
                st.session_state[doc_state_key]["save_success"] = True
                st.session_state[doc_state_key]["saved_path"] = save_result.get('path', '')
                logger.info("Document state updated")
            else:
                logger.error("No file content available")
                st.session_state.file_operations['last_save_result'] = {
                    'success': False,
                    'error': 'Original file content not available'
                }
        else:
            logger.error("Failed to create folder structure")
            st.session_state.file_operations['last_save_result'] = {
                'success': False,
                'error': 'Failed to create folder structure'
            }
    
    except Exception as e:
        logger.error(f"Error in perform_save_operation: {str(e)}")
        st.session_state.file_operations['last_save_result'] = {
            'success': False,
            'error': str(e)
        }
    
    # Reset the request flag
    st.session_state.file_operations['save_requested'] = False
    logger.info("Save operation completed")

def request_open_folder(folder_path):
    """Request to open a folder after Streamlit rerun"""
    st.session_state.file_operations['open_folder_requested'] = True
    st.session_state.file_operations['open_folder_path'] = folder_path

def perform_open_folder():
    """Perform the folder open operation using path from session state"""
    if not st.session_state.file_operations['open_folder_requested']:
        return
    
    folder_path = st.session_state.file_operations['open_folder_path']
    if folder_path:
        success = open_file_path(folder_path)
        st.session_state.file_operations['open_folder_result'] = {
            'success': success,
            'path': folder_path
        }
    
    # Reset the request flag
    st.session_state.file_operations['open_folder_requested'] = False 

def analyze_document_for_filing(provider, model, api_key, structured_data, base_directory):
    """Analyze document to determine the best folder for filing based on existing structure"""
    
    # Check if provider is available
    if provider not in LLM_PROVIDERS:
        return {"error": f"Unsupported provider: {provider}"}
    
    provider_config = LLM_PROVIDERS[provider]
    if not provider_config.get("available", False):
        return {"error": f"{provider} is not available. Please install the required library: pip install {provider.lower()}"}
    
    # First, analyze the existing file system structure
    existing_structure = analyze_existing_structure(base_directory)
    
    if "error" in existing_structure:
        return {"error": f"Failed to analyze existing structure: {existing_structure['error']}"}
    
    # Use the actual file system structure to suggest filing location
    suggested_path, best_evidence, is_new_folder = suggest_filing_location(structured_data, base_directory, existing_structure)
    suggested_filename = generate_filename(structured_data, existing_structure)
    
    # Create the full path
    full_path = f"{base_directory}/{suggested_path}/{suggested_filename}"
    
    # Add information about whether this is a new folder
    if is_new_folder:
        best_evidence.insert(0, "📝 This will create new folders in your file system")
    
    # Prepare analysis for LLM to validate and enhance the file system-based suggestion
    prompt = f"""You are an expert document filing assistant. Review the AI-generated filing suggestion that was based on DYNAMIC analysis of your actual file system.

Base Directory: {base_directory}

ACTUAL File System Analysis (from crawling your computer):
{json.dumps(existing_structure, indent=2)}

Document Information:
{json.dumps(structured_data, indent=2)}

Dynamic File System-Based Suggestion:
- Suggested Path: {suggested_path}
- Suggested Filename: {suggested_filename}
- Full Path: {full_path}
- Creating New Folders: {"Yes" if is_new_folder else "No"}
- Evidence for Choice: {best_evidence}

Your task is to:
1. Review the dynamic file system-based suggestion
2. Validate it against the actual existing structure
3. Suggest improvements if needed
4. Provide reasoning based on the real file system analysis
5. Assess confidence in the suggestion

IMPORTANT: You must respond with ONLY a valid JSON object. Do not include any explanatory text before or after the JSON.

Return your response as a JSON object with this exact structure:
{{
    "suggested_path": "path/to/suggested/folder",
    "filename": "descriptive_filename.pdf",
    "full_path": "base_directory/path/to/suggested/folder/descriptive_filename.pdf",
    "reasoning": "Detailed explanation of why this location was chosen based on DYNAMIC file system analysis",
    "category": "Document category (e.g., Financial, Legal, HR, etc.)",
    "priority": "High/Medium/Low",
    "tags": ["tag1", "tag2", "tag3"],
    "existing_structure_analysis": "How this fits with the ACTUAL existing organization patterns found on your computer",
    "confidence": "High/Medium/Low - confidence in the suggestion based on real file system",
    "alternatives": ["alternative_path_1", "alternative_path_2"],
    "file_system_evidence": "Specific evidence from the crawled file system that supports this suggestion",
    "dynamic_analysis": "How the AI dynamically analyzed your file system to make this decision"
}}

Focus on the DYNAMIC analysis of your actual file system structure and explain how the suggestion was derived from real folder content analysis."""
    
    try:
        # Direct implementation of LLM API calls for filing analysis
        if provider == "OpenAI":
            # OpenAI implementation
            try:
                import openai
                client = openai.OpenAI(api_key=api_key)
                
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are an expert document filing assistant with deep knowledge of file organization systems."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=4000,
                    response_format={"type": "json_object"}
                )
                
                return {
                    "success": True,
                    "analysis": response.choices[0].message.content,
                    "model": model,
                    "provider": "OpenAI"
                }
            except Exception as e:
                return {"error": f"OpenAI API error: {str(e)}"}
                
        elif provider == "Anthropic":
            # Anthropic implementation
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=api_key)
                
                response = client.messages.create(
                    model=model,
                    max_tokens=4000,
                    temperature=0.3,
                    system="You are an expert document filing assistant with deep knowledge of file organization systems. Respond with ONLY a valid JSON object.",
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                
                return {
                    "success": True,
                    "analysis": response.content[0].text,
                    "model": model,
                    "provider": "Anthropic"
                }
            except Exception as e:
                return {"error": f"Anthropic API error: {str(e)}"}
                
        elif provider == "Mistral":
            # Mistral implementation
            try:
                url = "https://api.mistral.ai/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "You are an expert document filing assistant with deep knowledge of file organization systems."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 4000,
                    "response_format": {"type": "json_object"}
                }
                
                response = requests.post(url, headers=headers, json=payload, timeout=120)
                
                if response.status_code == 200:
                    result = response.json()
                    return {
                        "success": True,
                        "analysis": result['choices'][0]['message']['content'],
                        "model": model,
                        "provider": "Mistral"
                    }
                else:
                    return {"error": f"Mistral API error: {response.status_code} - {response.text}"}
            except Exception as e:
                return {"error": f"Mistral API error: {str(e)}"}
        else:
            return {"error": f"Unsupported provider: {provider}"}
    
    except Exception as e:
        return {"error": f"Filing analysis failed: {str(e)}"}

def display_debug_info(structure):
    """Display detailed debug information about the file system crawl"""
    with st.expander("🔍 Detailed Debug Information"):
        st.write("### OS Walk Samples")
        if "os_walk_samples" in structure["debug_info"] and structure["debug_info"]["os_walk_samples"]:
            for i, sample in enumerate(structure["debug_info"]["os_walk_samples"]):
                st.write(f"**Sample {i+1}:**")
                st.write(f"- Root: `{sample['root']}`")
                st.write(f"- Dirs: {sample['dirs']}")
                st.write(f"- Files: {sample['files'][:5]}...")
        else:
            st.write("No OS walk samples collected")
        
        st.write("### Base Directory Analysis")
        if "base_directory_contents" in structure["debug_info"]:
            st.write(f"**Base directory:** `{structure['base_directory']}`")
            st.write(f"**Contents ({len(structure['debug_info']['base_directory_contents'])}):**")
            for item in structure["debug_info"]["base_directory_contents"][:20]:  # Show first 20
                st.write(f"- {item}")
            
            if "base_folders_count" in structure["debug_info"]:
                st.write(f"**Folders directly in base directory:** {structure['debug_info']['base_folders_count']}")
                if structure["debug_info"]["base_folders"]:
                    st.write("**Folder names:**")
                    st.code(", ".join(structure["debug_info"]["base_folders"]))
        
        st.write("### Folder Analysis")
        st.write(f"**Total folders found:** {structure['debug_info']['total_dirs_found']}")
        st.write(f"**Total files found:** {structure['debug_info']['total_files_found']}")
        st.write(f"**Maximum crawl depth:** {structure['debug_info']['crawl_depth']}")
        
        # Show folders by depth
        st.write("**Folders by depth:**")
        for depth, folders in structure["debug_info"].get("folders_by_depth", {}).items():
            st.write(f"- Depth {depth}: {len(folders)} folders")
            if folders:
                st.code(", ".join(folders[:10]) + ("..." if len(folders) > 10 else ""))

def display_filing_results(filing_result, original_filename, file_content, base_directory):
    """Display the filing analysis results and allow user to confirm"""
    if filing_result.get("error"):
        st.error(f"Filing Analysis Error: {filing_result['error']}")
        return None
    
    if filing_result.get("success"):
        try:
            # Try to parse the JSON response
            filing_data = json.loads(filing_result['analysis'])
            
            st.success(f"✅ Filing analysis completed using {filing_result['provider']} ({filing_result['model']})")
            
            # Display filing suggestions
            st.subheader("📁 Document Filing Suggestions")
            
            # Create three columns for better layout
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                st.write("**Suggested Path:**")
                # Check if the path exists
                full_path = Path(base_directory) / filing_data.get('suggested_path', 'N/A')
                if full_path.exists():
                    st.code(filing_data.get('suggested_path', 'N/A'))
                else:
                    st.code(f"📝 NEW: {filing_data.get('suggested_path', 'N/A')}")
                    st.info("This folder will be created when you save the file")
                
                # Add folder browser button
                if st.button("📂 Browse for Different Folder"):
                    custom_path = browse_for_folder()
                    if custom_path:
                        filing_data['suggested_path'] = str(Path(custom_path).relative_to(Path(base_directory)))
                        st.success(f"Selected folder: {custom_path}")
                        # Force a rerun to update the UI
                        st.rerun()
            
            with col2:
                st.write("**Filename:**")
                # Make filename editable
                new_filename = st.text_input(
                    "Edit filename if needed",
                    value=filing_data.get('filename', original_filename),
                    key="filename_input"
                )
                filing_data['filename'] = new_filename
                
                # Show file extension options if needed
                original_ext = Path(new_filename).suffix
                if not original_ext:
                    extensions = ['.pdf', '.txt', '.doc', '.docx']
                    selected_ext = st.selectbox(
                        "Select file extension",
                        extensions,
                        index=0
                    )
                    filing_data['filename'] = f"{new_filename}{selected_ext}"
            
            with col3:
                st.write("**Actions:**")
                # Save button with error handling
                if st.button("💾 Save Document"):
                    if file_content:
                        # Get the save path
                        save_path = Path(base_directory) / filing_data.get('suggested_path', 'Documents')
                        filename = filing_data.get('filename', original_filename)
                        
                        # Save the file with enhanced error handling
                        result = save_file(file_content, filename, save_path)
                        
                        if result["success"]:
                            st.success(f"✅ File saved successfully!")
                            # Show file details
                            st.info(
                                f"📄 File: {result['path']}\n"
                                f"📊 Size: {result['size']} bytes\n"
                                f"🕒 Modified: {result['modified']}\n"
                                f"{'🔄 Renamed' if result['renamed'] else '✍️ Original name'}"
                            )
                            # Add button to open containing folder
                            if st.button("📂 Open Containing Folder"):
                                open_file_path(Path(result['path']).parent)
                        else:
                            st.error(f"❌ Failed to save file: {result.get('error', 'Unknown error')}")
                            # Show troubleshooting info
                            with st.expander("🔍 Troubleshooting Information"):
                                st.write("**Error Details:**")
                                st.code(result.get('error', 'No detailed error information available'))
                                st.write("**Possible Solutions:**")
                                st.write("1. Check if you have write permissions")
                                st.write("2. Ensure the path is accessible")
                                st.write("3. Try a different location using the Browse button")
                    else:
                        st.error("❌ No file content available to save")
            
            # Display additional file information
            with st.expander("📋 Additional Information"):
                st.write("**Category:**", filing_data.get('category', 'N/A'))
                st.write("**Priority:**", filing_data.get('priority', 'N/A'))
                st.write("**Tags:**", ", ".join(filing_data.get('tags', [])))
                st.write("**Confidence:**", filing_data.get('confidence', 'N/A'))
                
                if filing_data.get('alternatives'):
                    st.write("**Alternative Locations:**")
                    for alt in filing_data['alternatives']:
                        if st.button(f"📁 Use {alt}", key=f"alt_{alt}"):
                            filing_data['suggested_path'] = alt
                            st.rerun()
            
            return filing_data
            
        except json.JSONDecodeError as e:
            st.error("Failed to parse filing analysis response")
            return None
    
    return None 