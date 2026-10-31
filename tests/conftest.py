"""Hand-authored synthetic records; never copied from the public dataset."""

import pandas as pd
import pytest


@pytest.fixture
def frame():
    return pd.DataFrame(
        {
            "IDpol": [1, 2, 3, 4, 5, 6],
            "ClaimNb": [0, 1, 0, 2, 0, 1],
            "Exposure": [0.5, 1.0, 0.25, 1.0, 0.5, 0.75],
            "Area": ["A", "B", "A", "C", "B", "C"],
            "VehPower": [4, 5, 4, 6, 5, 6],
            "VehAge": [1, 5, 2, 8, 3, 12],
            "DrivAge": [25, 40, 32, 60, 45, 70],
            "BonusMalus": [50, 60, 50, 80, 55, 90],
            "VehBrand": ["B1", "B2", "B1", "B3", "B2", "B3"],
            "VehGas": ["Regular", "Diesel", "Regular", "Diesel", "Regular", "Diesel"],
            "Density": [10, 20, 30, 40, 50, 60],
            "Region": ["R1", "R2", "R1", "R3", "R2", "R3"],
        }
    )
