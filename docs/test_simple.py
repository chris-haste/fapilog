"""
Simple test file for @docs: markers.
"""


def simple_function():
    """
    A simple function to test @docs: markers.

    @docs:use_cases
    - **Testing** the @docs: system
    - **Demonstration** of the marker functionality

    @docs:examples
    ```python
    result = simple_function()
    print(result)
    ```

    @docs:notes
    - This is a test function
    - Used to verify @docs: processing
    """
    return "Hello, @docs: system!"
