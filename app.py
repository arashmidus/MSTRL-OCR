import streamlit as st
import requests
import base64
import json
import hashlib

def display_file_result(result):
    """Display the results for a single file"""
    st.subheader(f"Results for: {result['filename']}")
    
    if result['error']:
        st.error(result['error'])
        if 'raw_response' in result:
            st.write("Raw response:", result['raw_response'])
    else:
        # Display structured results
        st.subheader("Extracted Information:")
        
        if result['structured_data']:
            # Display the structured data in a nice format
            st.json(result['structured_data'])
            
            # Also show it in a more readable format
            st.subheader("Key Information:")
            for key, value in result['structured_data'].items():
                if isinstance(value, dict):
                    st.write(f"**{key.replace('_', ' ').title()}:**")
                    for sub_key, sub_value in value.items():
                        st.write(f"  - {sub_key.replace('_', ' ').title()}: {sub_value}")
                else:
                    st.write(f"**{key.replace('_', ' ').title()}:** {value}")
        
        # Show original OCR text
        if result['ocr_text']:
            st.subheader("Original OCR Text:")
            st.text_area("", result['ocr_text'], height=300, key=f"ocr_{result['filename']}")

st.title("Mistral Document AI OCR App")

st.write("Upload PDF or image files to extract text using Mistral Document AI.")

api_key = st.text_input("Enter your Mistral API Key", type="password")
files = st.file_uploader("Upload Documents (PDF or Image)", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)

if st.button("Run OCR"):
    if not api_key:
        st.error("Please enter your Mistral API key.")
    elif not files:
        st.error("Please upload at least one document.")
    else:
        with st.spinner(f"Processing {len(files)} document(s)..."):
            all_results = []
            
            for i, file in enumerate(files):
                st.write(f"Processing file {i+1}/{len(files)}: {file.name}")
                
                try:
                    # Read file content and encode as base64
                    file_content = file.read()
                    file_base64 = base64.b64encode(file_content).decode('utf-8')
                    
                    # First, get OCR results
                    ocr_url = "https://api.mistral.ai/v1/ocr"
                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    }
                    
                    ocr_payload = {
                        "model": "mistral-ocr-latest",
                        "document": {
                            "type": "document_url",
                            "document_url": f"data:{file.type};base64,{file_base64}"
                        },
                        "include_image_base64": True
                    }
                    
                    ocr_response = requests.post(ocr_url, headers=headers, json=ocr_payload)
                    
                    if ocr_response.status_code == 200:
                        ocr_result = ocr_response.json()
                        
                        # Extract markdown content from OCR
                        markdown_content = ""
                        if 'pages' in ocr_result:
                            for page in ocr_result['pages']:
                                if 'markdown' in page:
                                    markdown_content += page['markdown'] + "\n\n"
                        
                        # Now use Document Understanding to get structured output
                        du_url = "https://api.mistral.ai/v1/chat/completions"
                        
                        # Calculate file size and SHA256 hash
                        file_size = len(file_content)
                        file_hash = hashlib.sha256(file_content).hexdigest()
                        
                        # Get file extension
                        file_extension = file.name.split('.')[-1].lower() if '.' in file.name else 'unknown'
                        
                        du_payload = {
                            "model": "mistral-large-latest",
                            "messages": [
                                {
                                    "role": "user",
                                    "content": f"""Analyze this document and extract all the important information in a structured JSON format. 

Your JSON response should start with these metadata fields at the top:
- doc_id: Generate a unique identifier (UUID format)
- sha256: The SHA256 hash of the file
- filename: The original filename
- file_type: The file extension/type
- size: File size in bytes
- metadata: Document metadata (author, creation date, etc. if available)
- summary: A brief summary of the document content
- intent: The purpose/intent of the document (e.g., Complaint, Invoice, Contract, etc.)
- key_entities: Important people, organizations, products, or concepts mentioned
- sentiment: Overall sentiment (Positive, Negative, Neutral, Mixed)
- analysis_notes: Any important observations or notes about the document


Then include all other extracted information from the document in a logical structure below these metadata fields.

Here's the OCR text:

{markdown_content}

Return a JSON object with the metadata fields first, followed by all other extracted information."""
                                }
                            ],
                            "response_format": {"type": "json_object"}
                        }
                        
                        du_response = requests.post(du_url, headers=headers, json=du_payload)
                        
                        if du_response.status_code == 200:
                            du_result = du_response.json()
                            
                            file_result = {
                                "filename": file.name,
                                "ocr_text": markdown_content,
                                "structured_data": None,
                                "error": None
                            }
                            
                            if 'choices' in du_result and len(du_result['choices']) > 0:
                                choice = du_result['choices'][0]
                                if 'message' in choice and 'content' in choice['message']:
                                    try:
                                        structured_data = json.loads(choice['message']['content'])
                                        file_result["structured_data"] = structured_data
                                    except json.JSONDecodeError:
                                        file_result["error"] = "Failed to parse structured data"
                                        file_result["raw_response"] = choice['message']['content']
                            else:
                                file_result["error"] = "No structured data received from the API"
                            
                            all_results.append(file_result)
                        else:
                            all_results.append({
                                "filename": file.name,
                                "ocr_text": markdown_content,
                                "structured_data": None,
                                "error": f"Document Understanding API Error: {du_response.status_code} - {du_response.text}"
                            })
                    else:
                        all_results.append({
                            "filename": file.name,
                            "ocr_text": None,
                            "structured_data": None,
                            "error": f"OCR API Error: {ocr_response.status_code} - {ocr_response.text}"
                        })
                        
                except Exception as e:
                    all_results.append({
                        "filename": file.name,
                        "ocr_text": None,
                        "structured_data": None,
                        "error": f"Error: {e}"
                    })
            
            # Display results
            st.success(f"Processed {len(files)} document(s)")
            
            # Create tabs for each file
            if len(all_results) > 1:
                tab_names = [f"File {i+1}: {result['filename']}" for i, result in enumerate(all_results)]
                tabs = st.tabs(tab_names)
                
                for i, (tab, result) in enumerate(zip(tabs, all_results)):
                    with tab:
                        display_file_result(result)
            else:
                display_file_result(all_results[0]) 