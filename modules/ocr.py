import streamlit as st
import requests
import json
import base64
from datetime import datetime
from pathlib import Path
import logging

# Configure logging
logger = logging.getLogger(__name__)

def process_single_chunk(api_key, markdown_content, file_info, headers):
    """Process a single document or page"""
    try:
        logger.info(f"Processing single chunk for {file_info['filename']}")
        du_url = "https://api.mistral.ai/v1/chat/completions"
        
        prompt = f"""Analyze this document and extract all the important information in a structured JSON format. 

Your JSON response should start with these metadata fields at the top:
- doc_id: {file_info['doc_id']}
- sha256: {file_info['file_hash']}
- filename: {file_info['filename']}
- file_type: {file_info['file_extension']}
- mime_type: {file_info['mime_type']}
- size: {file_info['file_size']}
- page_count: {file_info['page_count']}
- word_count: {file_info['word_count']}
- char_count: {file_info['char_count']}
- line_count: {file_info['line_count']}
- processing_timestamp: {file_info['processing_timestamp']}
- is_page: false
- metadata: Document metadata (author, creation date, etc. if available)
- summary: A brief summary of the document content
- intent: The purpose/intent of the document (e.g., Complaint, Invoice, Contract, etc.)
- key_entities: Important people, organizations, products, or concepts mentioned
- analysis_notes: Any important observations or notes about the document

Then include all other extracted information from the document in a logical structure below these metadata fields.

Here's the OCR text:

{markdown_content}

Return a JSON object with the metadata fields first, followed by all other extracted information."""
        
        du_payload = {
            "model": "mistral-large-latest",
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"}
        }
        
        logger.info("Sending request to Mistral API")
        # Use standard timeout for single documents
        du_response = requests.post(du_url, headers=headers, json=du_payload, timeout=120)
        
        if du_response.status_code == 200:
            du_result = du_response.json()
            logger.info("Received successful response from Mistral API")
            
            if 'choices' in du_result and len(du_result['choices']) > 0:
                choice = du_result['choices'][0]
                if 'message' in choice and 'content' in choice['message']:
                    try:
                        structured_data = json.loads(choice['message']['content'])
                        logger.info("Successfully parsed structured data")
                        return {
                            "structured_data": structured_data,
                            "error": None
                        }
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse structured data: {str(e)}")
                        return {
                            "structured_data": {
                                "error": f"Failed to parse structured data: {str(e)}",
                                "raw_response": choice['message']['content'][:500] + "..." if len(choice['message']['content']) > 500 else choice['message']['content']
                            },
                            "error": f"Failed to parse structured data: {str(e)}"
                        }
                else:
                    logger.error("No content in API response")
                    return {
                        "structured_data": {
                            "error": "No content in API response"
                        },
                        "error": "No content in API response"
                    }
            else:
                logger.error("No choices in API response")
                return {
                    "structured_data": {
                        "error": "No choices in API response"
                    },
                    "error": "No choices in API response"
                }
        
        elif du_response.status_code == 504:
            logger.error("API timeout (504)")
            return {
                "structured_data": {
                    "error": "API timeout (504) - document may be too large"
                },
                "error": f"API timeout (504): {du_response.text}"
            }
        else:
            logger.error(f"API Error: {du_response.status_code} - {du_response.text}")
            return {
                "structured_data": {
                    "error": f"API Error {du_response.status_code}"
                },
                "error": f"API Error: {du_response.status_code} - {du_response.text}"
            }
            
    except requests.exceptions.Timeout:
        logger.error("Request timeout - the API call took too long")
        return {
            "structured_data": {
                "error": "Request timeout"
            },
            "error": "Request timeout - the API call took too long"
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        return {
            "structured_data": {
                "error": f"Request error: {str(e)}"
            },
            "error": f"Request error: {str(e)}"
        }
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {
            "structured_data": {
                "error": f"Unexpected error: {str(e)}"
            },
            "error": f"Unexpected error: {str(e)}"
        }

def process_single_page(api_key, page_markdown, page_file_info, headers):
    """Process a single page of the document"""
    try:
        logger.info(f"Processing single page {page_file_info.get('page_number', 1)} of {page_file_info.get('total_pages', 1)} for {page_file_info['filename']}")
        du_url = "https://api.mistral.ai/v1/chat/completions"
        
        prompt = f"""Analyze this document page and extract all the important information in a structured JSON format. 

Your JSON response should start with these metadata fields at the top:
- doc_id: {page_file_info['doc_id']}
- sha256: {page_file_info['file_hash']}
- filename: {page_file_info['filename']}
- file_type: {page_file_info['file_extension']}
- mime_type: {page_file_info['mime_type']}
- size: {page_file_info['file_size']}
- page_count: {page_file_info['page_count']}
- page_number: {page_file_info.get('page_number', 1)}
- total_pages: {page_file_info.get('total_pages', 1)}
- word_count: {page_file_info['word_count']}
- char_count: {page_file_info['char_count']}
- line_count: {page_file_info['line_count']}
- processing_timestamp: {page_file_info['processing_timestamp']}
- is_page: true
- metadata: Document metadata (author, creation date, etc. if available)
- summary: A brief summary of this page
- intent: The purpose/intent of the document (e.g., Complaint, Invoice, Contract, etc.)
- key_entities: Important people, organizations, products, or concepts mentioned on this page
- analysis_notes: Any important observations or notes about this page

Then include all other extracted information from this page in a logical structure below these metadata fields.

Here's the OCR text for this page:

{page_markdown}

Return a JSON object with the metadata fields first, followed by all other extracted information."""
        
        du_payload = {
            "model": "mistral-large-latest",
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"}
        }
        
        logger.info("Sending request to Mistral API for page processing")
        # Use longer timeout for page processing
        du_response = requests.post(du_url, headers=headers, json=du_payload, timeout=180)
        
        if du_response.status_code == 200:
            du_result = du_response.json()
            logger.info("Received successful response from Mistral API for page")
            
            if 'choices' in du_result and len(du_result['choices']) > 0:
                choice = du_result['choices'][0]
                if 'message' in choice and 'content' in choice['message']:
                    try:
                        structured_data = json.loads(choice['message']['content'])
                        logger.info("Successfully parsed structured data for page")
                        return {
                            "structured_data": structured_data,
                            "error": None
                        }
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse structured data for page: {str(e)}")
                        return {
                            "structured_data": {
                                "error": f"Failed to parse structured data: {str(e)}",
                                "raw_response": choice['message']['content'][:500] + "..." if len(choice['message']['content']) > 500 else choice['message']['content']
                            },
                            "error": f"Failed to parse structured data: {str(e)}"
                        }
                else:
                    logger.error("No content in API response for page")
                    return {
                        "structured_data": {
                            "error": "No content in API response"
                        },
                        "error": "No content in API response"
                    }
            else:
                logger.error("No choices in API response for page")
                return {
                    "structured_data": {
                        "error": "No choices in API response"
                    },
                    "error": "No choices in API response"
                }
        
        elif du_response.status_code == 504:
            logger.error("API timeout (504) for page")
            return {
                "structured_data": {
                    "error": "API timeout (504) - page may be too large"
                },
                "error": f"API timeout (504): {du_response.text}"
            }
        else:
            logger.error(f"API Error for page: {du_response.status_code} - {du_response.text}")
            return {
                "structured_data": {
                    "error": f"API Error {du_response.status_code}"
                },
                "error": f"API Error: {du_response.status_code} - {du_response.text}"
            }
            
    except requests.exceptions.Timeout:
        logger.error("Request timeout for page - the API call took too long")
        return {
            "structured_data": {
                "error": "Request timeout"
            },
            "error": "Request timeout - the API call took too long"
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error for page: {str(e)}")
        return {
            "structured_data": {
                "error": f"Request error: {str(e)}"
            },
            "error": f"Request error: {str(e)}"
        }
    except Exception as e:
        logger.error(f"Unexpected error processing page: {str(e)}")
        return {
            "structured_data": {
                "error": f"Unexpected error: {str(e)}"
            },
            "error": f"Unexpected error: {str(e)}"
        }

def combine_page_results(page_results, file_info, combined_entities, combined_notes):
    """Combine results from multiple pages into a single comprehensive result"""
    logger.info(f"Combining results from {len(page_results)} pages for {file_info['filename']}")
    
    # Create a comprehensive summary from all pages
    all_summaries = []
    all_intents = []
    all_sentiments = []
    successful_pages = 0
    
    for result in page_results:
        if result and 'structured_data' in result and result['structured_data']:
            data = result['structured_data']
            
            # Skip pages that have errors
            if 'error' in data and data['error']:
                logger.warning(f"Skipping page with error: {data['error']}")
                continue
                
            successful_pages += 1
            
            # Safely extract summary with type checking
            if 'summary' in data and data['summary']:
                summary = data['summary']
                if isinstance(summary, str):
                    all_summaries.append(summary)
                elif isinstance(summary, dict):
                    # Convert dict to string representation
                    all_summaries.append(str(summary))
                else:
                    # Convert any other type to string
                    all_summaries.append(str(summary))
            
            # Safely extract intent with type checking
            if 'intent' in data and data['intent']:
                intent = data['intent']
                if isinstance(intent, str):
                    all_intents.append(intent)
                elif isinstance(intent, dict):
                    all_intents.append(str(intent))
                else:
                    all_intents.append(str(intent))
            
            # Safely extract sentiment with type checking
            if 'sentiment' in data and data['sentiment']:
                sentiment = data['sentiment']
                if isinstance(sentiment, str):
                    all_sentiments.append(sentiment)
                elif isinstance(sentiment, dict):
                    all_sentiments.append(str(sentiment))
                else:
                    all_sentiments.append(str(sentiment))
    
    logger.info(f"Successfully processed {successful_pages} out of {len(page_results)} pages")
    
    # Combine the results with safe string operations
    combined_data = {
        "doc_id": file_info['doc_id'],
        "sha256": file_info['file_hash'],
        "filename": file_info['filename'],
        "file_type": file_info['file_extension'],
        "mime_type": file_info['mime_type'],
        "size": file_info['file_size'],
        "page_count": file_info['page_count'],
        "word_count": file_info['word_count'],
        "char_count": file_info['char_count'],
        "line_count": file_info['line_count'],
        "processing_timestamp": file_info['processing_timestamp'],
        "is_page": False,
        "pages_processed": len(page_results),
        "successful_pages": successful_pages,
        "failed_pages": len(page_results) - successful_pages,
        "summary": " ".join(all_summaries) if all_summaries else "Document processed page by page",
        "intent": max(set(all_intents), key=all_intents.count) if all_intents else "Unknown",
        "key_entities": list(combined_entities),
        "sentiment": max(set(all_sentiments), key=all_sentiments.count) if all_sentiments else "Neutral",
        "analysis_notes": combined_notes,
        "page_analysis": [result.get('structured_data', {}) for result in page_results if result and result.get('structured_data')]
    }
    
    logger.info(f"Combined results: {successful_pages} successful pages, {len(page_results) - successful_pages} failed pages")
    
    return {
        "structured_data": combined_data,
        "error": None
    }

def process_document_pages(api_key, ocr_result, file_info, headers, file_progress, file_status):
    """Process large documents by analyzing each page separately"""
    logger.info(f"Processing document pages for {file_info['filename']}")
    
    if 'pages' not in ocr_result or not ocr_result['pages']:
        # No pages found, process as single document
        logger.info("No pages found, processing as single document")
        file_status.text("Analyzing document...")
        result = process_single_chunk(api_key, "", file_info, headers)
        file_progress.progress(0.9)
        return result
    
    pages = ocr_result['pages']
    logger.info(f"Found {len(pages)} pages")
    
    if len(pages) == 1:
        # Single page, process normally
        logger.info("Single page document, processing normally")
        file_status.text("Analyzing document...")
        markdown_content = pages[0].get('markdown', '')
        result = process_single_chunk(api_key, markdown_content, file_info, headers)
        file_progress.progress(0.9)
        return result
    
    # Process multiple pages
    logger.info(f"Processing {len(pages)} pages")
    all_results = []
    combined_entities = set()
    combined_notes = []
    
    # Create page progress tracking
    page_progress = st.progress(0)
    page_status = st.empty()
    
    for i, page in enumerate(pages):
        page_status.text(f"Processing page {i+1}/{len(pages)}...")
        logger.info(f"Processing page {i+1}/{len(pages)}")
        
        # Extract markdown content from this page
        page_markdown = page.get('markdown', '')
        if not page_markdown.strip():
            logger.warning(f"Page {i+1}/{len(pages)} is empty")
            page_status.text(f"⚠️ Page {i+1}/{len(pages)} is empty")
            continue
        
        try:
            # Create page-specific file info
            page_file_info = file_info.copy()
            page_file_info['page_number'] = i + 1
            page_file_info['total_pages'] = len(pages)
            
            page_result = process_single_page(api_key, page_markdown, page_file_info, headers)
            
            if page_result and page_result.get('error') is None and 'structured_data' in page_result:
                logger.info(f"Successfully processed page {i+1}")
                # Extract entities and notes from this page
                structured_data = page_result['structured_data']
                if structured_data:  # Make sure structured_data is not None
                    if 'key_entities' in structured_data:
                        entities = structured_data['key_entities']
                        if isinstance(entities, list):
                            combined_entities.update(entities)
                        elif isinstance(entities, str):
                            combined_entities.add(entities)
                    
                    if 'analysis_notes' in structured_data:
                        notes = structured_data['analysis_notes']
                        if isinstance(notes, str):
                            combined_notes.append(f"Page {i+1}: {notes}")
                        elif isinstance(notes, list):
                            # Ensure all items in the list are strings
                            for note in notes:
                                if isinstance(note, str):
                                    combined_notes.append(f"Page {i+1}: {note}")
                                elif isinstance(note, dict):
                                    combined_notes.append(f"Page {i+1}: {str(note)}")
                                else:
                                    combined_notes.append(f"Page {i+1}: {str(note)}")
                        elif isinstance(notes, dict):
                            combined_notes.append(f"Page {i+1}: {str(notes)}")
                        else:
                            combined_notes.append(f"Page {i+1}: {str(notes)}")
                
                all_results.append(page_result)
                page_status.text(f"✅ Page {i+1}/{len(pages)} completed")
            else:
                # Handle error or missing data
                error_msg = page_result.get('error', 'Unknown error') if page_result else 'No result returned'
                logger.error(f"Error processing page {i+1}: {error_msg}")
                page_status.text(f"⚠️ Page {i+1}/{len(pages)} had issues: {error_msg}")
                
                # Still add the result to track what happened
                if page_result:
                    all_results.append(page_result)
                else:
                    # Create a placeholder result for failed pages
                    all_results.append({
                        "structured_data": {
                            "page_number": i+1,
                            "error": "Page processing failed",
                            "summary": f"Page {i+1} could not be processed"
                        },
                        "error": "Page processing failed"
                    })
            
        except Exception as e:
            logger.error(f"Error processing page {i+1}: {str(e)}")
            page_status.text(f"❌ Error in page {i+1}/{len(pages)}")
            st.warning(f"Error processing page {i+1}: {str(e)}")
            
            # Add a placeholder result for failed pages
            all_results.append({
                "structured_data": {
                    "page_number": i+1,
                    "error": f"Exception: {str(e)}",
                    "summary": f"Page {i+1} failed due to exception"
                },
                "error": f"Exception: {str(e)}"
            })
            continue
        
        # Update page progress
        page_progress.progress((i + 1) / len(pages))
        
        # Update overall file progress (60% to 85% for page processing)
        page_progress_percentage = (i + 1) / len(pages)
        page_progress_contribution = page_progress_percentage * 0.25  # 25% of total progress
        total_progress = min(0.85, 0.60 + page_progress_contribution)  # Clamp to 85%
        file_progress.progress(total_progress)
    
    # Clear page progress indicators
    page_progress.empty()
    page_status.empty()
    
    # Combine all page results into a single comprehensive result
    if all_results:
        logger.info("Combining page results")
        file_status.text("Combining page results...")
        return combine_page_results(all_results, file_info, list(combined_entities), combined_notes)
    else:
        logger.warning("No page results to combine")
        return None

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