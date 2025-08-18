# Makefile for fapilog documentation
# This provides convenient commands for building and managing documentation

.PHONY: help clean html linkcheck doctest coverage build verify validate install

# Default target
help:
	@echo "fapilog Documentation Makefile"
	@echo "=============================="
	@echo ""
	@echo "Available targets:"
	@echo "  help       - Show this help message"
	@echo "  install    - Install documentation dependencies"
	@echo "  html       - Build HTML documentation"
	@echo "  clean      - Clean build directory"
	@echo "  linkcheck  - Check for broken external links"
	@echo "  doctest    - Run doctests in documentation"
	@echo "  coverage   - Check documentation coverage"
	@echo "  build      - Full build with verification"
	@echo "  verify     - Verify build output"
	@echo "  validate   - Validate internal links"
	@echo "  serve      - Serve documentation locally"
	@echo "  deploy     - Deploy to GitHub Pages"
	@echo ""

# Install dependencies
install:
	@echo "Installing documentation dependencies..."
	pip install -r requirements.txt
	@echo "Installing project dependencies for autodoc..."
	cd .. && pip install -e . && cd docs

# Build HTML documentation
html:
	@echo "Building HTML documentation..."
	sphinx-build -b html . _build/html

# Clean build directory
clean:
	@echo "Cleaning build directory..."
	rm -rf _build/
	rm -rf _static/custom.css _static/custom.js

# Check external links
linkcheck:
	@echo "Checking external links..."
	sphinx-build -b linkcheck . _build/linkcheck

# Run doctests
doctest:
	@echo "Running doctests..."
	sphinx-build -b doctest . _build/doctest

# Check documentation coverage
coverage:
	@echo "Checking documentation coverage..."
	sphinx-build -b coverage . _build/coverage

# Full build with verification
build: clean html verify validate
	@echo "Build completed successfully!"

# Verify build output
verify:
	@echo "Verifying build output..."
	python verify_build.py

# Validate internal links
validate:
	@echo "Validating internal links..."
	python validate_links.py

# Serve documentation locally
serve: html
	@echo "Starting local server..."
	@echo "Documentation available at: http://localhost:8000"
	@echo "Press Ctrl+C to stop"
	cd _build/html && python -m http.server 8000

# Deploy to GitHub Pages (requires proper setup)
deploy: build
	@echo "Deploying to GitHub Pages..."
	@echo "Note: This requires proper GitHub Pages configuration"
	@echo "Consider using the GitHub Actions workflow instead"

# Quick build for development
dev: html
	@echo "Quick build completed for development"

# Full quality check
quality: validate verify linkcheck
	@echo "Quality checks completed!"

# Install and build
setup: install build
	@echo "Documentation setup completed!"

# Show build status
status:
	@echo "Documentation build status:"
	@if [ -d "_build/html" ]; then \
		echo "  ✓ Build directory exists"; \
		if [ -f "_build/html/index.html" ]; then \
			echo "  ✓ Main page built"; \
		else \
			echo "  ✗ Main page missing"; \
		fi; \
		if [ -f "_build/html/genindex.html" ]; then \
			echo "  ✓ API index built"; \
		else \
			echo "  ✗ API index missing"; \
		fi; \
	else \
		echo "  ✗ Build directory missing"; \
	fi

