# Working with Legacy Code (ref: tdd-python)

## Characterization Tests

When adding tests to existing code without breaking it:

### 1. Capture Current Behavior

```python
def test_existing_function_behavior():
    """Document what the function currently does, bugs and all."""
    # Run the function and record actual output
    result = legacy_function(input_data)

    # Assert current behavior (even if it's wrong)
    assert result == current_actual_output

    # TODO: This behavior seems wrong, but test documents current state
```

### 2. Add Tests Before Refactoring

Never refactor without tests. First add tests that pass with current code, then refactor.

```python
# Step 1: Add test for current (buggy) behavior
def test_current_date_calculation():
    result = calculate_date_range("2024-01-01", "2024-01-10")
    assert result == 9  # Currently off by one, but document it

# Step 2: Fix the bug
def test_correct_date_calculation():
    result = calculate_date_range("2024-01-01", "2024-01-10")
    assert result == 10  # Now correct

# Step 3: Update implementation to pass new test
```

### 3. Golden Master Pattern

For complex outputs, capture and compare entire results:

```python
def test_report_generation_golden_master(tmp_path):
    """Ensure report output hasn't changed."""
    output_file = tmp_path / "report.txt"

    generate_report(data, output_file)

    actual = output_file.read_text()
    expected = Path("tests/golden_masters/report_expected.txt").read_text()

    assert actual == expected
```

## Dependency Breaking Techniques

### Extract and Override

```python
# Original tightly-coupled code
class ReportGenerator:
    def generate(self):
        data = Database.query("SELECT * FROM users")  # Hard dependency
        return self.format(data)

# Refactor: Extract method for testing
class ReportGenerator:
    def generate(self):
        data = self.get_data()
        return self.format(data)

    def get_data(self):
        return Database.query("SELECT * FROM users")

# Test with override
class TestableReportGenerator(ReportGenerator):
    def get_data(self):
        return [{"id": 1, "name": "Test"}]  # Test data

def test_report_formatting():
    generator = TestableReportGenerator()
    result = generator.generate()
    assert "Test" in result
```

### Parameterize Dependencies

```python
# Original: Hidden dependency
def process_orders():
    db = Database.connect()  # Global/hidden
    orders = db.get_orders()
    return process(orders)

# Refactored: Explicit dependency
def process_orders(db=None):
    if db is None:
        db = Database.connect()
    orders = db.get_orders()
    return process(orders)

# Test with mock
def test_process_orders():
    mock_db = Mock()
    mock_db.get_orders.return_value = [test_order()]

    result = process_orders(db=mock_db)

    assert result is not None
```

## Dealing with Untestable Code

### Wrap and Test New Code

If legacy code is too risky to change, wrap it:

```python
# Legacy: Untestable mess
def legacy_calculation(a, b, c):
    # 500 lines of spaghetti
    pass

# New: Tested wrapper
def safe_calculation(a, b, c):
    """Wrapper with validation and error handling."""
    if not valid_inputs(a, b, c):
        raise ValueError("Invalid inputs")

    try:
        return legacy_calculation(a, b, c)
    except Exception as e:
        logger.error(f"Legacy calculation failed: {e}")
        return default_value()

def test_safe_calculation_validation():
    with pytest.raises(ValueError):
        safe_calculation(None, None, None)

def test_safe_calculation_error_handling(mocker):
    mocker.patch('module.legacy_calculation', side_effect=Exception())
    result = safe_calculation(1, 2, 3)
    assert result == default_value()
```

### Seam Insertion

Find "seams" where you can inject testability:

```python
# Before: Global state
class PaymentProcessor:
    def process(self, amount):
        PaymentGateway.charge(amount)  # Global

# After: Dependency injection seam
class PaymentProcessor:
    def __init__(self, gateway=None):
        self.gateway = gateway or PaymentGateway

    def process(self, amount):
        self.gateway.charge(amount)

def test_payment_processing():
    mock_gateway = Mock()
    processor = PaymentProcessor(gateway=mock_gateway)

    processor.process(100)

    mock_gateway.charge.assert_called_with(100)
```

## Incremental Test Addition Strategy

### 1. Start with High-Value Tests

Focus on:

- Core business logic
- Bug-prone areas
- Frequently changed code
- Critical user paths

### 2. Test New Features First

All new features MUST follow TDD. This gradually improves coverage.

### 3. Add Tests When Fixing Bugs

```python
# Bug report: "Function returns wrong value for negative inputs"

# Step 1: Write failing test that reproduces bug
def test_negative_input_bug():
    result = problematic_function(-5)
    assert result == expected_value  # Currently fails

# Step 2: Fix the bug
# Step 3: Verify test now passes
```

### 4. Refactor with Test Coverage

Don't refactor untested code. Add tests first, then refactor.

## Tools for Legacy Code

### Coverage Analysis

```bash
# Run with coverage to find untested areas
pytest --cov=src --cov-report=html

# Open htmlcov/index.html to see what's missing
```

### Mutation Testing

```bash
# Install mutmut
pip install mutmut

# Run mutation tests to find weak tests
mutmut run

# Review surviving mutants
mutmut show
```

### Static Analysis

```bash
# Find complexity hotspots
radon cc src/ -a -nb

# Find areas needing refactoring
radon mi src/
```

## Approval Testing

For complex outputs that are hard to specify:

```python
from approvaltests import verify

def test_complex_report_output():
    """Verify report matches approved version."""
    report = generate_complex_report(test_data)
    verify(report)  # Creates approved file on first run
```

## Safe Refactoring Steps

1. **Add characterization tests** - Document current behavior
2. **Run tests** - Establish baseline (all green)
3. **Make small change** - One refactoring at a time
4. **Run tests** - Verify behavior unchanged
5. **Commit** - Save safe checkpoint
6. **Repeat** - Continue incrementally

Never make large changes to untested code. Small, verified steps are safer.
