# Mistral Document AI OCR App with LLM Analysis & Filing Agent

A comprehensive document processing application that combines Mistral's OCR capabilities with advanced LLM analysis and intelligent document filing for complete document management.

## Features

### 📄 OCR Processing
- Extract text from PDF and image files using Mistral Document AI
- Support for multiple file formats (PDF, PNG, JPG, JPEG)
- Multi-page document processing
- Structured data extraction with metadata

### 🤖 LLM Analysis
- **Multi-Provider Support**: OpenAI, Anthropic, and Mistral
- **Analysis Types**:
  - Comprehensive Analysis: Full document overview with insights
  - Risk Assessment: Legal, financial, operational, and security risks
  - Business Insights: Market opportunities and strategic recommendations
  - Custom Analysis: User-defined focus areas

### 📁 Document Filing Agent
- **Intelligent Organization**: AI-powered folder structure suggestions based on existing file system
- **File System Crawling**: Analyzes existing organization patterns and naming conventions
- **Automatic Categorization**: Documents sorted by type, date, client, and priority
- **Smart Naming**: Descriptive filenames based on document content and existing patterns
- **One-Click Filing**: Save documents to AI-suggested locations
- **Custom Base Directories**: Choose from common locations or specify custom paths
- **Structure Analysis**: Understand your current file organization before filing

## Setup

### 1. Install Dependencies
   ```bash
   pip install -r requirements.txt
   ```

### 2. Configure API Keys
Create a `.env` file in the project root with your API keys:

```env
# Required for OCR
MISTRAL_API_KEY=your_mistral_api_key_here

# Optional - for LLM analysis and filing
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

### 3. Run the Application
   ```bash
   streamlit run app.py
   ```

## Usage

### Step 1: OCR Processing
1. Enter your Mistral API key
2. Upload one or more documents (PDF or images)
3. Click "Run OCR" to extract text and structured data

### Step 2: LLM Analysis
1. After OCR processing, scroll down to the "AI Analysis" section
2. Select your preferred LLM provider and model
3. Choose the analysis type:
   - **Comprehensive**: Full document analysis
   - **Risk Assessment**: Focus on risks and compliance
   - **Business Insights**: Market and strategic analysis
   - **Custom**: Define your own analysis focus
4. Select which documents to analyze
5. Click "Run AI Analysis"

### Step 3: Document Filing
1. Scroll down to the "Document Filing Agent" section
2. Select a base directory (Documents, Desktop, Downloads, or Custom)
3. Choose your preferred LLM provider for filing analysis
4. Select which documents to organize
5. Click "Run Filing Analysis"
6. Review the AI suggestions and click "Save" to organize your documents

## Document Filing Agent

The filing agent analyzes your documents and existing file system to suggest optimal organization:

### **🔍 File System Analysis**
- **Structure Crawling**: Scans your existing folders and files to understand organization patterns
- **Naming Convention Detection**: Identifies how files are currently named (underscores, hyphens, etc.)
- **Folder Hierarchy Analysis**: Maps existing folder structures and common categories
- **File Type Analysis**: Understands what types of files you typically store
- **Pattern Recognition**: Learns from your existing organization habits

### **Smart Folder Structure**
- **By Document Type**: Invoices, contracts, reports, etc.
- **By Date/Year**: Organized chronologically
- **By Client/Project**: Grouped by business relationships
- **By Priority**: High, Medium, Low priority documents
- **By Category**: Financial, Legal, HR, Technical, etc.

### **Intelligent Features**
- **Automatic Categorization**: Documents are classified based on content
- **Descriptive Filenames**: AI suggests meaningful file names based on existing patterns
- **Priority Assessment**: Identifies urgent or important documents
- **Tagging System**: Adds relevant tags for easy searching
- **Reasoning**: Explains why each location was chosen based on existing structure
- **Confidence Scoring**: Shows how confident the AI is in its suggestions
- **Alternative Suggestions**: Provides backup filing options

### **Example Filing Suggestions**
```
Invoice from ABC Corp → Documents/Financial/Invoices/2024/ABC_Corp/invoice_abc_corp_20241229.pdf
Contract with XYZ Ltd → Documents/Legal/Contracts/2024/XYZ_Ltd/contract_xyz_ltd_20241229.pdf
Employee Handbook → Documents/HR/Policies/employee_handbook_20241229.pdf
```

### **File System Crawling Process**
1. **Directory Scanning**: Crawls up to 3 levels deep in your chosen base directory
2. **Pattern Analysis**: Identifies common folder names, file naming conventions, and file types
3. **Structure Mapping**: Creates a map of your existing organization
4. **Intelligent Suggestions**: Uses learned patterns to suggest consistent filing locations
5. **Validation**: LLM validates suggestions against existing structure

## Supported LLM Providers

### OpenAI
- Models: GPT-4o, GPT-4o-mini, GPT-4-turbo, GPT-3.5-turbo
- Best for: General analysis, creative insights

### Anthropic
- Models: Claude 3.5 Sonnet, Claude 3.5 Haiku, Claude 3 Opus
- Best for: Detailed analysis, safety-focused insights

### Mistral
- Models: Mistral Large, Mistral Medium, Mistral Small
- Best for: Cost-effective analysis, multilingual support

## Analysis Types

### Comprehensive Analysis
Provides a complete document overview including:
- Document summary and key insights
- Risk assessment and compliance check
- Action items and recommendations
- Business impact analysis
- Data quality assessment

### Risk Assessment
Focuses on identifying potential risks:
- Legal and compliance risks
- Financial implications
- Operational challenges
- Reputational risks
- Security concerns
- Risk mitigation strategies

### Business Insights
Extracts actionable business intelligence:
- Market opportunities
- Customer insights
- Competitive analysis
- Operational efficiency improvements
- Revenue potential
- Strategic recommendations

### Custom Analysis
Allows you to define specific focus areas such as:
- Legal compliance review
- Financial analysis
- Technical assessment
- Regulatory compliance
- Industry-specific analysis

## File Structure
```
MSTRL-OCR/
├── app.py              # Main application
├── requirements.txt    # Python dependencies
├── README.md          # This file
└── .env              # API keys (create this file)
```

## API Key Setup

### Mistral API Key
1. Sign up at [Mistral AI](https://mistral.ai/)
2. Navigate to your API keys section
3. Create a new API key
4. Add it to your `.env` file

### OpenAI API Key
1. Sign up at [OpenAI](https://platform.openai.com/)
2. Go to API keys section
3. Create a new API key
4. Add it to your `.env` file

### Anthropic API Key
1. Sign up at [Anthropic](https://console.anthropic.com/)
2. Navigate to API keys
3. Create a new API key
4. Add it to your `.env` file

## Tips for Best Results

1. **Document Quality**: Ensure documents are clear and readable for better OCR results
2. **Analysis Type**: Choose the analysis type that matches your specific needs
3. **Model Selection**: Use more powerful models (like GPT-4o or Claude 3.5 Sonnet) for complex documents
4. **Custom Analysis**: Be specific in your custom analysis prompts for better results
5. **Multiple Documents**: Process multiple related documents together for comprehensive analysis
6. **Filing Organization**: Start with a clean base directory for better organization
7. **Review Suggestions**: Always review AI filing suggestions before saving

## Troubleshooting

### OCR Issues
- Ensure documents are not corrupted
- Check that file formats are supported
- Verify your Mistral API key is valid
- For large documents, try processing smaller sections

### LLM Analysis Issues
- Verify your chosen provider's API key is valid
- Check your API usage limits and billing
- Try different models if one fails
- Ensure you have sufficient API credits

### Filing Issues
- Ensure you have write permissions to the base directory
- Check that the suggested folder path is valid
- Verify the LLM provider is available and configured
- Make sure the original file content is preserved during OCR processing

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is open source and available under the MIT License. 