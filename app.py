import streamlit as st
import requests
import base64
import json
import hashlib
import os
import uuid
from datetime import datetime
from dotenv import load_dotenv
import shutil
from pathlib import Path
import re
import logging
import time

# Configure logging
log_file = 'app.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Log to console
        logging.FileHandler(log_file)  # Log to file
    ]
)
logger = logging.getLogger(__name__)

# Log the start of the application
logger.info("Starting Mistral Document AI OCR App")

# Import the filing module
from modules.filing import (
    LLM_PROVIDERS,
    get_common_filing_directories,
    analyze_document_for_filing,
    display_filing_results,
    save_file,
    open_file_path
)

# Import the OCR module
from modules.ocr import (
    process_single_chunk,
    process_single_page,
    process_document_pages,
    combine_page_results,
    display_file_result
)

# Initialize global session state for file operations
if 'file_operations' not in st.session_state:
    st.session_state.file_operations = {
        'save_requested': False,
        'save_file_index': None,
        'save_params': None,
        'last_save_result': None,
        'open_folder_requested': False,
        'open_folder_path': None
    }

# Try to import LLM libraries with error handling
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

# Load environment variables from .env file
load_dotenv()

st.title("Mistral Document AI OCR App")

# Process any pending save requests
perform_save_operation()

# Process any pending file operations
perform_save_operation()
perform_open_folder()

# Show save operation results if available
if st.session_state.file_operations.get('last_save_result'):
    save_result = st.session_state.file_operations['last_save_result']
    if save_result.get('success'):
        st.success(f"✅ Document saved successfully to: {save_result['path']}")
        # Clear the result after showing
        st.session_state.file_operations['last_save_result'] = None
    else:
        st.error(f"❌ Failed to save file: {save_result.get('error', 'Unknown error')}")
        # Clear the result after showing
        st.session_state.file_operations['last_save_result'] = None

# Show folder open results if available
if st.session_state.file_operations.get('open_folder_result'):
    folder_result = st.session_state.file_operations['open_folder_result']
    if folder_result.get('success'):
        st.success(f"✅ Opened folder: {folder_result['path']}")
    else:
        st.error(f"❌ Failed to open folder: {folder_result['path']}")
    # Clear the result after showing
    st.session_state.file_operations['open_folder_result'] = None

st.write("Upload PDF or image files to extract text using Mistral Document AI.")

# Get API key from environment variable or user input
default_api_key = os.getenv('MISTRAL_API_KEY', '')
api_key = st.text_input("Enter your Mistral API Key", value=default_api_key, type="password", help="You can also set this as MISTRAL_API_KEY in a .env file")
files = st.file_uploader("Upload Documents (PDF or Image)", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)

# Initialize session state for storing results
if 'all_results' not in st.session_state:
    st.session_state.all_results = []

if st.button("Run OCR"):
    if not api_key:
        logger.error("No API key provided")
        st.error("Please enter your Mistral API key.")
    elif not files:
        logger.error("No files uploaded")
        st.error("Please upload at least one document.")
    else:
        logger.info(f"Starting OCR process for {len(files)} document(s)")
        with st.spinner(f"Processing {len(files)} document(s)..."):
            all_results = []
            
            # Create overall progress bar for multiple files
            if len(files) > 1:
                overall_progress = st.progress(0)
                overall_status = st.empty()
                overall_status.text(f"Processing files: 0/{len(files)} completed")
            
            for i, file in enumerate(files):
                logger.info(f"Processing file {i+1}/{len(files)}: {file.name}")
                st.write(f"Processing file {i+1}/{len(files)}: {file.name}")
                
                # Create progress bar for overall file processing
                file_progress = st.progress(0)
                file_status = st.empty()
                
                try:
                    # Read file content and encode as base64
                    file_status.text("Reading file...")
                    file_content = file.read()
                    file_base64 = base64.b64encode(file_content).decode('utf-8')
                    file_progress.progress(0.1)
                    logger.info(f"File read successfully: {file.name}")
                    
                    # First, get OCR results
                    file_status.text("Running OCR...")
                    logger.info("Sending OCR request to Mistral API")
                    ocr_url = "https://api.mistral.ai/v1/ocr"
                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    }
                    
                    # Fix the data URL format to match API requirements
                    # API expects: data:application/<format>;base64,<document-base64>
                    # We were sending: data:image/jpeg;base64,<document-base64>
                    mime_type = file.type or f"application/{file.name.split('.')[-1].lower()}"
                    if mime_type.startswith('image/'):
                        # Convert image MIME types to application format
                        mime_type = f"application/{mime_type.split('/')[-1]}"
                    elif not mime_type.startswith('application/'):
                        # Ensure it starts with application/
                        mime_type = f"application/{mime_type}"
                    
                    data_url = f"data:{mime_type};base64,{file_base64}"
                    
                    ocr_payload = {
                        "model": "mistral-ocr-latest",
                        "document": {
                            "type": "document_url",
                            "document_url": data_url
                        },
                        "include_image_base64": True
                    }
                    
                    ocr_response = requests.post(ocr_url, headers=headers, json=ocr_payload, timeout=60)
                    file_progress.progress(0.3)
                    
                    if ocr_response.status_code == 200:
                        ocr_result = ocr_response.json()
                        logger.info("OCR request successful")
                        
                        # Extract markdown content from OCR
                        file_status.text("Extracting text...")
                        markdown_content = ""
                        if 'pages' in ocr_result:
                            for page in ocr_result['pages']:
                                if 'markdown' in page:
                                    markdown_content += page['markdown'] + "\n\n"
                        file_progress.progress(0.5)
                        logger.info("Text extracted successfully")
                        
                        # Calculate file metadata
                        file_status.text("Calculating metadata...")
                        file_size = len(file_content)
                        file_hash = hashlib.sha256(file_content).hexdigest()
                        file_extension = file.name.split('.')[-1].lower() if '.' in file.name else 'unknown'
                        mime_type = file.type or f"application/{file_extension}"
                        word_count = len(markdown_content.split()) if markdown_content else 0
                        char_count = len(markdown_content) if markdown_content else 0
                        line_count = len(markdown_content.split('\n')) if markdown_content else 0
                        page_count = len(ocr_result.get('pages', [])) if 'pages' in ocr_result else 0
                        processing_timestamp = datetime.now().isoformat()
                        doc_id = str(uuid.uuid4())
                        
                        file_info = {
                            "doc_id": doc_id,
                            "file_hash": file_hash,
                            "filename": file.name,
                            "file_extension": file_extension,
                            "mime_type": mime_type,
                            "file_size": file_size,
                            "page_count": page_count,
                            "word_count": word_count,
                            "char_count": char_count,
                            "line_count": line_count,
                            "processing_timestamp": processing_timestamp
                        }
                        file_progress.progress(0.6)
                        logger.info(f"File metadata calculated: {page_count} pages, {word_count} words")
                        
                        # Check if document has multiple pages and needs page-by-page processing
                        if page_count > 1:
                            logger.info(f"Processing multi-page document with {page_count} pages")
                            file_status.text("Multi-page document detected. Processing page by page...")
                            result = process_document_pages(api_key, ocr_result, file_info, headers, file_progress, file_status)
                        else:
                            logger.info("Processing single-page document")
                            file_status.text("Analyzing document...")
                            result = process_single_chunk(api_key, markdown_content, file_info, headers)
                            file_progress.progress(0.9)
                        
                        file_status.text("Finalizing results...")
                        if result and result.get('error') is None:
                            logger.info("Document processed successfully")
                            file_result = {
                                "filename": file.name,
                                "ocr_text": markdown_content,
                                "structured_data": result.get('structured_data'),
                                "file_content": file_content,
                                "error": None
                            }
                            all_results.append(file_result)
                        elif result and result.get('error'):
                            logger.error(f"Error processing document: {result['error']}")
                            all_results.append({
                                "filename": file.name,
                                "ocr_text": markdown_content,
                                "structured_data": None,
                                "file_content": file_content,
                                "error": result['error']
                            })
                        else:
                            logger.error("Failed to process document")
                            all_results.append({
                                "filename": file.name,
                                "ocr_text": markdown_content,
                                "structured_data": None,
                                "file_content": file_content,
                                "error": "Failed to process document"
                            })
                        
                        file_progress.progress(1.0)
                        file_status.text("✅ File processed successfully!")
                        
                        # Update overall progress for multiple files
                        if len(files) > 1:
                            progress_value = min(1.0, max(0.0, (i + 1) / len(files)))
                            overall_progress.progress(progress_value)
                            overall_status.text(f"Processing files: {i + 1}/{len(files)} completed")
                        
                    elif ocr_response.status_code == 504:
                        logger.error(f"OCR API timeout (504) for {file.name}")
                        file_progress.progress(1.0)
                        file_status.text("❌ OCR timeout error")
                        all_results.append({
                            "filename": file.name,
                            "ocr_text": None,
                            "structured_data": None,
                            "file_content": None,
                            "error": f"OCR API Timeout (504): The document may be too large or complex. Try with a smaller document or contact support if this persists."
                        })
                        
                        # Update overall progress for multiple files
                        if len(files) > 1:
                            progress_value = min(1.0, max(0.0, (i + 1) / len(files)))
                            overall_progress.progress(progress_value)
                            overall_status.text(f"Processing files: {i + 1}/{len(files)} completed")
                    else:
                        logger.error(f"OCR API error: {ocr_response.status_code} - {ocr_response.text}")
                        file_progress.progress(1.0)
                        file_status.text("❌ OCR processing error")
                        all_results.append({
                            "filename": file.name,
                            "ocr_text": None,
                            "structured_data": None,
                            "file_content": None,
                            "error": f"OCR API Error: {ocr_response.status_code} - {ocr_response.text}"
                        })
                        
                        # Update overall progress for multiple files
                        if len(files) > 1:
                            progress_value = min(1.0, max(0.0, (i + 1) / len(files)))
                            overall_progress.progress(progress_value)
                            overall_status.text(f"Processing files: {i + 1}/{len(files)} completed")
                        
                except Exception as e:
                    logger.error(f"Error processing {file.name}: {str(e)}")
                    file_progress.progress(1.0)
                    file_status.text("❌ Processing error")
                    all_results.append({
                        "filename": file.name,
                        "ocr_text": None,
                        "structured_data": None,
                        "file_content": None,
                        "error": f"Error: {e}"
                    })
                    
                    # Update overall progress for multiple files
                    if len(files) > 1:
                        progress_value = min(1.0, max(0.0, (i + 1) / len(files)))
                        overall_progress.progress(progress_value)
                        overall_status.text(f"Processing files: {i + 1}/{len(files)} completed")
            
            # Store results in session state
            st.session_state.all_results = all_results
            logger.info(f"Processed {len(files)} document(s)")
            
            # Display results
            st.success(f"Processed {len(files)} document(s)")

    # Display OCR results if available
if st.session_state.all_results:
    st.markdown("---")
    st.subheader("📄 OCR Results")
            
    # Create tabs for each file
    if len(st.session_state.all_results) > 1:
        tab_names = [f"File {i+1}: {result['filename']}" for i, result in enumerate(st.session_state.all_results)]
        tabs = st.tabs(tab_names)
        
        for i, (tab, result) in enumerate(zip(tabs, st.session_state.all_results)):
            with tab:
                display_file_result(result)
    else:
        display_file_result(st.session_state.all_results[0])
    
    # Get available providers (shared between analysis and filing)
    available_providers = {name: config for name, config in LLM_PROVIDERS.items() if config.get("available", False)}
    
    if not available_providers:
        st.error("❌ No LLM providers are available. Please install the required libraries.")
        st.stop()
    
    # Document Filing Section
    st.markdown("---")
    st.subheader("📁 Intelligent Document Filing")
    st.write("The AI will analyze your file system and suggest the best location for your documents.")
    
    # Filing configuration
    col1, col2 = st.columns(2)
    
    with col1:
        # Base directory selection
        common_dirs = get_common_filing_directories()
        base_dir_option = st.selectbox(
            "Select Base Directory",
            list(common_dirs.keys()),
            help="Choose where to start organizing your documents"
        )
        
        if base_dir_option == "Custom":
            base_directory = st.text_input(
                "Enter Custom Base Directory",
                placeholder="/path/to/your/documents",
                help="Enter the full path to your base directory"
            )
        else:
            base_directory = common_dirs[base_dir_option]
            st.info(f"Base Directory: {base_directory}")
    
    with col2:
        # LLM provider selection
        filing_provider = st.selectbox(
            "Select AI Model Provider",
            list(available_providers.keys()),
            index=0,
            help="Choose which AI model to use for intelligent filing"
        )
        
        # Get API key for provider
        filing_provider_config = available_providers[filing_provider]
        filing_api_key = st.text_input(
            f"Enter your {filing_provider} API Key",
            value=os.getenv(filing_provider_config['env_key'], ''),
            type="password",
            help=f"You can also set this as {filing_provider_config['env_key']} in a .env file"
        )
    
    # Model selection
    filing_model = st.selectbox(
        "Select Model",
        filing_provider_config['models'],
        help="Choose the specific model to use"
    )
    
    # Select which documents to analyze for filing
    if len(st.session_state.all_results) > 1:
        st.write("Select documents for filing analysis:")
        filing_selected_docs = []
        for i, result in enumerate(st.session_state.all_results):
            if st.checkbox(f"File: {result['filename']}", key=f"filing_{i}"):
                filing_selected_docs.append(i)
    else:
        filing_selected_docs = [0]  # Analyze the single document
    
    # Store file contents in session state for filing
    if 'file_contents' not in st.session_state:
        st.session_state.file_contents = {}
    
    # Run filing analysis button
    if st.button("📁 Run Filing Analysis", type="primary"):
        if not base_directory or base_directory == "Enter custom path...":
            st.error("Please select or enter a base directory for filing.")
        elif not filing_api_key:
            st.error(f"Please enter your {filing_provider} API key for filing.")
        elif not filing_selected_docs:
            st.error("Please select at least one document for filing analysis.")
        else:
            with st.spinner("Running filing analysis..."):
                for doc_index in filing_selected_docs:
                    result = st.session_state.all_results[doc_index]
                    
                    if result.get('error') or not result.get('structured_data'):
                        st.warning(f"⚠️ Skipping {result['filename']} - no structured data available")
                        continue
                    
                    st.write(f"📁 Analyzing filing for: {result['filename']}")
                    
                    # Generate filing suggestions
                    with st.spinner("🤖 Generating intelligent filing suggestions..."):
                        filing_result = analyze_document_for_filing(
                            provider=filing_provider,
                            model=filing_model,
                            api_key=filing_api_key,
                            structured_data=result['structured_data'],
                            base_directory=base_directory
                        )
                        
                        # Display filing results
                        st.markdown(f"### 📁 Filing Suggestions for: {result['filename']}")
                        filing_data = display_filing_results(filing_result, result['filename'], result['file_content'], base_directory)
                        
                        if filing_data:
                            st.success("✅ Filing suggestions generated successfully!")
                            st.info("You can now save your document using the suggestions above.")
                    
                    # Store filing data in session state for later use
                    if 'filing_data' not in st.session_state:
                        st.session_state.filing_data = {}
                    st.session_state.filing_data[doc_index] = filing_data
                    
                    # Offer to save the file
                    st.subheader("💾 Save Document")
                    
                    # Initialize session state for this document if not exists
                    doc_state_key = f"doc_state_{doc_index}"
                    if doc_state_key not in st.session_state:
                        st.session_state[doc_state_key] = {
                            "rename_file": True,
                            "custom_filename": filing_data.get('filename', result['filename']),
                            "save_attempted": False,
                            "save_success": False,
                            "saved_path": None,
                            "save_in_progress": False
                        }
                        
                    # Initialize action keys for this document
                    save_action_key = f"save_action_{doc_index}"
                    if save_action_key not in st.session_state:
                        st.session_state[save_action_key] = False
                    
                    # Create file options section
                    st.write("**File Options:**")
                    col1, col2 = st.columns([1, 2])
                    
                    with col1:
                        # Add rename checkbox
                        rename_file = st.checkbox("Rename file", 
                                                 value=st.session_state[doc_state_key]["rename_file"],
                                                 key=f"rename_checkbox_{doc_index}")
                        st.session_state[doc_state_key]["rename_file"] = rename_file
                    
                    with col2:
                        # Show filename input if rename is checked
                        if rename_file:
                            custom_filename = st.text_input("Filename:", 
                                                          value=st.session_state[doc_state_key]["custom_filename"],
                                                          key=f"filename_input_{doc_index}")
                            st.session_state[doc_state_key]["custom_filename"] = custom_filename
                        else:
                            st.text(f"Original filename: {result['filename']}")
                    
                    # Create save button section
                    col1, col2 = st.columns(2)
                    
                    # Handle save button with the new callback approach
                    with col1:
                        if st.button(f"✅ Save Document", key=f"save_{doc_index}"):
                            # Create a container for save progress
                            save_container = st.container()
                            with save_container:
                                st.write("**💾 Saving Document**")
                                
                                # Get the current filename based on rename checkbox
                                if rename_file:
                                    custom_filename = st.session_state[doc_state_key]["custom_filename"]
                                else:
                                    custom_filename = result['filename']
                                
                                # Request the save operation to be performed after rerun
                                request_save_file(
                                    doc_index=doc_index,
                                    result=result,
                                    filing_data=filing_data,
                                    base_directory=base_directory,
                                    rename_file=rename_file,
                                    custom_filename=custom_filename
                                )
                                
                                # Show initial save message
                                st.info("🔄 Save operation initiated... Please wait.")
                    
                    # Show file info if previously saved
                    if st.session_state[doc_state_key].get("save_success"):
                        saved_path = st.session_state[doc_state_key].get("saved_path")
                        if saved_path:
                            with col2:
                                st.success(f"✅ Previously saved to: {saved_path}")
                                
                                # Show file info if available
                                try:
                                    file_path = Path(saved_path)
                                    if file_path.exists():
                                        st.info(f"📊 **Size:** {file_path.stat().st_size} bytes")
                                        st.info(f"📅 **Last modified:** {datetime.fromtimestamp(file_path.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
                                except:
                                    pass
                    
                    # Show additional actions if file was saved successfully
                    if st.session_state[doc_state_key].get("save_success"):
                        saved_path = st.session_state[doc_state_key]["saved_path"]
                        if saved_path:
                            # Handle open folder button with the new callback approach
                            with col2:
                                if st.button("🗂️ Open containing folder", key=f"open_folder_{doc_index}"):
                                    parent_folder = Path(saved_path).parent
                                    request_open_folder(parent_folder)
                                    st.info("📂 Opening folder... Please wait.")
                    
                    # Show help text
                    with st.expander("💡 Help"):
                        st.write("""
                        - **Rename file**: Check this box to use the AI-suggested filename or enter your own.
                        - **Filename**: Enter a custom filename or use the suggested one.
                        - **Save Document**: Saves the file to the suggested location with the chosen name.
                        - **Open containing folder**: Opens the folder where the file was saved.
                        """)
                    
                    # Show note about file content
                    if not result.get('file_content'):
                        st.warning("⚠️ **Note:** Original file content not available. Only metadata will be saved.")
                
                    if doc_index < len(filing_selected_docs) - 1:
                        st.markdown("---")