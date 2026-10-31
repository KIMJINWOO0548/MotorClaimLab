"""Independent synthetic checks of frequency and preprocessing boundaries."""

import numpy as np
import pandas as pd
import pytest
from threadpoolctl import threadpool_limits

from motorclaimlab.models import fit_models


@pytest.fixture(autouse=True)
def bounded_prediction_threads():
    with threadpool_limits(limits=2):
        yield


def test_mean_uses_total_claims_over_total_exposure(frame):
    original = frame.copy(deep=True)
    models = fit_models(frame)
    assert list(models) == ["mean", "poisson_glm", "poisson_hgb"]
    # Four claims observed over four policy-years, unlike the rowwise mean rate.
    np.testing.assert_allclose(models["mean"].predict(frame), np.ones(6))
    pd.testing.assert_frame_equal(frame, original)


def test_actual_models_predict_finite_positive_rates_for_unknown_categories(frame):
    models = fit_models(frame, max_iter=3)
    unseen = frame.copy(deep=True)
    unseen["VehPower"] = 99
    for name in ["VehBrand", "VehGas", "Area", "Region"]:
        unseen[name] = "unseen"
    for model in models.values():
        rates = model.predict(unseen)
        assert isinstance(rates, np.ndarray)
        assert rates.shape == (len(frame),)
        assert np.all(np.isfinite(rates))
        assert np.all(rates > 0)


def test_predict_never_learns_from_held_out_data(frame):
    models = fit_models(frame, max_iter=3)
    for name in ["poisson_glm", "poisson_hgb"]:
        model = models[name]
        transformed = model.preprocessor.transform(frame).copy()
        held_out = frame.copy(deep=True)
        held_out["Density"] = 100.0
        held_out["VehBrand"] = "held-out-only"
        model.predict(held_out)
        after = model.preprocessor.transform(frame)
        if hasattr(transformed, "toarray"):
            transformed, after = transformed.toarray(), after.toarray()
        np.testing.assert_array_equal(transformed, after)
        encoder = model.preprocessor.named_transformers_["categorical"]
        assert all("held-out-only" not in values for values in encoder.categories_)


def test_id_target_exposure_and_other_columns_are_not_covariates(frame):
    models = fit_models(frame, max_iter=3)
    changed = frame.copy(deep=True)
    changed["IDpol"] = np.arange(len(frame)) + 9000
    changed["ClaimNb"] = 10000
    changed["Exposure"] = 50.0
    changed["derived_target"] = 200.0
    covariates = frame.drop(columns=["IDpol", "ClaimNb", "Exposure"])
    for model in models.values():
        np.testing.assert_array_equal(model.predict(frame), model.predict(changed))
        np.testing.assert_array_equal(model.predict(frame), model.predict(covariates))


@pytest.mark.parametrize(
    "column,value",
    [
        ("Exposure", 0),
        ("Exposure", np.inf),
        ("ClaimNb", np.nan),
        ("ClaimNb", -1),
        ("ClaimNb", 0.5),
        ("Density", np.inf),
    ],
)
def test_rejects_invalid_training_values(frame, column, value):
    invalid = frame.copy(deep=True)
    invalid[column] = invalid[column].astype(float)
    invalid.loc[0, column] = value
    with pytest.raises(ValueError):
        fit_models(invalid)


def test_zero_claim_training_is_explicitly_unsupported(frame):
    frame["ClaimNb"] = 0
    with pytest.raises(ValueError, match="(?i)(positive|zero|claims)"):
        fit_models(frame)
