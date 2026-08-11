import pytest
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

@pytest.fixture
def mock_targets():
    return [
        {"name": "TLDR AI", "url": "https://tldr.tech/api/latest/ai"},
        {"name": "The Neuron", "url": "https://theneuron.ai/newsletter"}
    ]
