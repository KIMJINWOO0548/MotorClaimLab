"""Independent regression: booleans must never become numeric insurance values."""

import numpy as np
import pytest

from motorclaimlab.data import validate_frame


@pytest.mark.parametrize("column", ["IDpol", "ClaimNb", "Exposure"])
@pytest.mark.parametrize("boolean", [True, np.bool_(True)])
def test_boolean_numeric_source_is_rejected_before_conversion(frame, column, boolean):
    malformed = frame.copy()
    malformed[column] = malformed[column].astype(object)
    malformed.loc[0, column] = boolean
    with pytest.raises(ValueError, match=column):
        validate_frame(malformed)


@pytest.mark.parametrize("column", ["VehPower", "VehAge", "DrivAge", "Density", "BonusMalus"])
def test_boolean_covariate_is_rejected(frame, column):
    malformed = frame.copy()
    malformed[column] = malformed[column].astype(object)
    malformed.loc[0, column] = np.bool_(True)
    with pytest.raises(ValueError, match=column):
        validate_frame(malformed)
