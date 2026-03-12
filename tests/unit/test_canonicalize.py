from pcag.core.utils.canonicalize import canonicalize

def test_key_sorting():
    """Keys should be sorted lexicographically."""
    assert canonicalize({"b": 1, "a": 2}) == '{"a":2,"b":1}'

def test_float_rounding():
    """Floats should be rounded to 3 decimal places."""
    assert canonicalize({"v": 1.12345}) == '{"v":1.123}'
    assert canonicalize({"v": 150.09999}) == '{"v":150.100}'

def test_nested_object():
    """Nested objects should be recursively canonicalized."""
    data = {"b": {"z": 1, "y": 2}, "a": [3, 2]}
    # {"a":[3,2],"b":{"y":2,"z":1}}
    assert canonicalize(data) == '{"a":[3,2],"b":{"y":2,"z":1}}'

def test_array_preserves_order():
    """Arrays should preserve element order."""
    assert canonicalize([2, 1, 3]) == '[2,1,3]'
    assert canonicalize({"a": [2, 1]}) == '{"a":[2,1]}'

def test_same_data_different_order_same_result():
    """Different key ordering should produce identical canonical form."""
    d1 = {"a": 1, "b": 2, "c": {"x": 10, "y": 20}}
    d2 = {"c": {"y": 20, "x": 10}, "b": 2, "a": 1}
    assert canonicalize(d1) == canonicalize(d2)

def test_special_values():
    """Test null, bool, empty objects."""
    assert canonicalize(None) == 'null'
    assert canonicalize(True) == 'true'
    assert canonicalize(False) == 'false'
    assert canonicalize({}) == '{}'
    assert canonicalize([]) == '[]'
    assert canonicalize({"val": None}) == '{"val":null}'
