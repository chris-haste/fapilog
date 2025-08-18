# fapilog Documentation

This directory contains the complete documentation for the fapilog project, built using Sphinx and the ReadTheDocs theme.

## Quick Start

### Prerequisites

- Python 3.8 or higher
- pip (Python package installer)

### Building Documentation

1. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

2. **Install project for autodoc:**

   ```bash
   cd .. && pip install -e . && cd docs
   ```

3. **Build documentation:**

   ```bash
   make html
   # or
   ./build.sh
   ```

4. **View documentation:**
   ```bash
   make serve
   # Then open http://localhost:8000 in your browser
   ```

## Available Commands

### Using Make

- `make help` - Show available commands
- `make install` - Install dependencies
- `make html` - Build HTML documentation
- `make clean` - Clean build directory
- `make build` - Full build with verification
- `make serve` - Serve documentation locally
- `make validate` - Validate internal links
- `make verify` - Verify build output
- `make quality` - Run all quality checks

### Using Scripts

- `./build.sh` - Build documentation with dependency installation
- `python validate_links.py` - Validate internal documentation links
- `python verify_build.py` - Verify build output

## Directory Structure

```
docs/
├── conf.py                 # Sphinx configuration
├── index.md                # Main documentation entry point
├── requirements.txt        # Python dependencies
├── build.sh               # Build script
├── Makefile               # Make commands
├── validate_links.py      # Link validation script
├── verify_build.py        # Build verification script
├── _static/               # Static assets (CSS, JS, images)
├── _templates/            # Custom HTML templates
├── api-reference/         # API documentation
├── concepts/              # Core concepts
├── tutorials/             # Step-by-step guides
├── examples/              # Code examples
├── contributing/          # Development guidelines
└── _build/                # Build output (gitignored)
```

## Configuration

### Sphinx Configuration (`conf.py`)

The main Sphinx configuration file includes:

- **Extensions**: autodoc, viewcode, napoleon, intersphinx, todo, myst_parser
- **Theme**: ReadTheDocs theme with custom styling
- **Source files**: Markdown (.md) only
- **Auto-documentation**: Automatic API documentation from Python docstrings
- **Type hints**: Enhanced type hint handling
- **Cross-references**: Links to external documentation

### Theme Customization

Custom styling is applied through:

- `_static/custom.css` - Custom CSS styles
- `_static/custom.js` - Custom JavaScript functionality
- Theme options in `conf.py`

## Continuous Integration

### GitHub Actions

The documentation is automatically built and deployed via GitHub Actions:

- **Build**: Runs on all Python versions (3.9-3.12)
- **Validation**: Checks for broken links and build issues
- **Deployment**: Automatically deploys to GitHub Pages on main branch
- **Quality Checks**: Runs on pull requests

### ReadTheDocs

Documentation is also hosted on ReadTheDocs:

- **URL**: https://fapilog.readthedocs.io/
- **Auto-build**: Triggers on repository updates
- **Version support**: Multiple version branches

## Development

### Adding New Documentation

1. **Create new markdown files** in appropriate directories
2. **Update index files** to include new content
3. **Add to navigation** in relevant index files
4. **Run validation** to ensure links work

### Documentation Standards

- Use **Markdown** (.md) files for all content
- Follow **Google/NumPy docstring** style for Python code
- Include **examples** and **code snippets**
- Maintain **consistent navigation** structure
- Use **descriptive link text**

### Quality Assurance

Before committing documentation changes:

1. **Build locally** to check for errors
2. **Validate links** to ensure internal references work
3. **Check formatting** for consistency
4. **Test navigation** to ensure good user experience

## Troubleshooting

### Common Issues

#### Build Failures

- **Import errors**: Ensure project is installed (`pip install -e .`)
- **Missing dependencies**: Install requirements (`pip install -r requirements.txt`)
- **Configuration errors**: Check `conf.py` syntax

#### Link Validation Failures

- **Broken internal links**: Update file paths or create missing files
- **External link failures**: Check if external sites are accessible
- **Anchor link issues**: Verify heading IDs exist

#### Performance Issues

- **Slow builds**: Use `make dev` for quick development builds
- **Large build output**: Clean build directory with `make clean`
- **Memory issues**: Build on systems with sufficient RAM

### Getting Help

- **Build issues**: Check the build output for error messages
- **Configuration**: Review `conf.py` and Sphinx documentation
- **Content issues**: Validate markdown syntax and links
- **CI/CD problems**: Check GitHub Actions workflow logs

## Contributing

### Documentation Contributions

1. **Fork the repository**
2. **Create a feature branch**
3. **Make your changes**
4. **Test locally** with `make build`
5. **Submit a pull request**

### Reporting Issues

- **Documentation bugs**: Use GitHub Issues
- **Build problems**: Include error messages and environment details
- **Content suggestions**: Open discussions or issues

## Resources

### Sphinx Documentation

- [Sphinx User Guide](https://www.sphinx-doc.org/en/master/usage/)
- [MyST Parser](https://myst-parser.readthedocs.io/)
- [ReadTheDocs Theme](https://sphinx-rtd-theme.readthedocs.io/)

### Markdown Resources

- [Markdown Guide](https://www.markdownguide.org/)
- [GitHub Markdown](https://docs.github.com/en/github/writing-on-github)

### Project Resources

- [fapilog Repository](https://github.com/your-username/fapilog)
- [Issue Tracker](https://github.com/your-username/fapilog/issues)
- [Discussions](https://github.com/your-username/fapilog/discussions)

---

_This documentation system is designed to be developer-friendly and maintainable. For questions or issues, please open a GitHub issue or discussion._

