"""
Simple test file in the same directory as settings.py.
"""

from typing import Optional, Union


def test_function(param: Optional[str] = None) -> Union[str, None]:
    return param


print("Test")
