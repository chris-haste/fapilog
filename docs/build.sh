#!/bin/bash

# fapilog Documentation Build Script
# This script builds the Sphinx documentation for the fapilog project

set -e  # Exit on any error

echo "🚀 Building fapilog documentation..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the right directory
if [ ! -f "conf.py" ]; then
    print_error "This script must be run from the docs/ directory"
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is required but not installed"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    print_error "Python 3.8 or higher is required (found $PYTHON_VERSION)"
    exit 1
fi

print_status "Using Python $PYTHON_VERSION"

# Clean previous builds
print_status "Cleaning previous builds..."
rm -rf _build/
rm -rf _static/custom.css _static/custom.js

# Create static files directory if it doesn't exist
mkdir -p _static

# Create minimal custom CSS and JS files
cat > _static/custom.css << 'EOF'
/* Custom CSS for fapilog documentation */
.custom-admonition {
    border-left: 4px solid #2980B9;
    background-color: #f8f9fa;
    padding: 1rem;
    margin: 1rem 0;
    border-radius: 4px;
}

.custom-admonition-title {
    font-weight: bold;
    color: #2980B9;
    margin-bottom: 0.5rem;
}

/* Improve code block styling */
.highlight {
    border-radius: 4px;
    border: 1px solid #e1e4e8;
}

/* Better table styling */
.wy-table-responsive table {
    border-collapse: collapse;
    width: 100%;
}

.wy-table-responsive th,
.wy-table-responsive td {
    border: 1px solid #e1e4e8;
    padding: 8px 12px;
    text-align: left;
}

.wy-table-responsive th {
    background-color: #f6f8fa;
    font-weight: 600;
}
EOF

cat > _static/custom.js << 'EOF'
// Custom JavaScript for fapilog documentation
document.addEventListener('DOMContentLoaded', function() {
    // Add custom functionality here
    console.log('fapilog documentation loaded');
    
    // Add copy button functionality for code blocks
    const codeBlocks = document.querySelectorAll('pre code');
    codeBlocks.forEach(block => {
        if (!block.parentElement.querySelector('.copy-button')) {
            const copyButton = document.createElement('button');
            copyButton.className = 'copy-button';
            copyButton.textContent = 'Copy';
            copyButton.style.cssText = `
                position: absolute;
                top: 5px;
                right: 5px;
                background: #2980B9;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 2px 8px;
                font-size: 12px;
                cursor: pointer;
            `;
            
            copyButton.addEventListener('click', function() {
                navigator.clipboard.writeText(block.textContent);
                copyButton.textContent = 'Copied!';
                setTimeout(() => {
                    copyButton.textContent = 'Copy';
                }, 2000);
            });
            
            block.parentElement.style.position = 'relative';
            block.parentElement.appendChild(copyButton);
        }
    });
});
EOF

# Install dependencies
print_status "Installing documentation dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    print_warning "requirements.txt not found, installing basic dependencies..."
    pip install sphinx sphinx-rtd-theme myst-parser sphinx-autodoc-typehints
fi

# Install project dependencies for autodoc
print_status "Installing project dependencies for autodoc..."
cd ..
pip install -e .
cd docs

# Build documentation
print_status "Building documentation..."
sphinx-build -b html . _build/html

# Validate build
if [ -f "_build/html/index.html" ]; then
    print_status "Documentation built successfully! 🎉"
    print_status "You can view the documentation by opening _build/html/index.html in your browser"
    
    # Check for common issues
    if [ -f "_build/html/genindex.html" ]; then
        print_status "✓ API index generated"
    else
        print_warning "⚠ API index not generated - check for import errors"
    fi
    
    if [ -f "_build/html/search.html" ]; then
        print_status "✓ Search functionality available"
    else
        print_warning "⚠ Search not available"
    fi
    
    # Count built pages
    PAGE_COUNT=$(find _build/html -name "*.html" | wc -l)
    print_status "Built $PAGE_COUNT HTML pages"
    
    exit 0
else
    print_error "Documentation build failed"
    print_error "Check the build output above for errors"
    exit 1
fi

