"""Frozen, exposure-weighted claim frequency models with train-only preprocessing."""

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import PoissonRegressor
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler
from threadpoolctl import threadpool_limits

CATEGORICAL = ["VehPower", "VehBrand", "VehGas", "Area", "Region"]
NUMERIC = ["VehAge", "DrivAge", "BonusMalus", "Density"]
COVARIATES = [
    "VehPower",
    "VehAge",
    "DrivAge",
    "BonusMalus",
    "VehBrand",
    "VehGas",
    "Area",
    "Density",
    "Region",
]


def _features(frame: pd.DataFrame) -> pd.DataFrame:
    missing = set(COVARIATES).difference(frame.columns)
    if missing:
        raise ValueError(f"Missing covariates: {sorted(missing)}")
    result = frame.loc[:, COVARIATES].copy(deep=True)
    for name in ["VehPower", *NUMERIC]:
        try:
            values = pd.to_numeric(result[name], errors="raise").to_numpy(dtype=float)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Invalid numeric covariate: {name}") from error
        if not np.all(np.isfinite(values)) or np.any(values < 0):
            raise ValueError(f"Covariate {name} must be finite and nonnegative")
        if name in ["BonusMalus", "Density"] and np.any(values <= 0):
            raise ValueError(f"Covariate {name} must be positive")
        result[name] = values
    for name in CATEGORICAL[1:]:
        if result[name].isna().any() or result[name].astype(str).str.strip().eq("").any():
            raise ValueError(f"Invalid categorical covariate: {name}")
        result[name] = result[name].astype(str)
    return result


def _checked_rates(values: np.ndarray) -> np.ndarray:
    rates = np.asarray(values, dtype=float)
    if not np.all(np.isfinite(rates)) or np.any(rates <= 0):
        raise ValueError("Model produced a nonpositive or nonfinite frequency")
    return rates


@dataclass
class MeanFrequency:
    rate: float

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        return _checked_rates(np.full(len(frame), self.rate))


@dataclass
class FrequencyModel:
    preprocessor: ColumnTransformer
    estimator: object

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        features = self.preprocessor.transform(_features(frame))
        return _checked_rates(self.estimator.predict(features))


def fit_models(train: pd.DataFrame, seed: int = 20261101, max_iter: int = 100) -> dict[str, object]:
    """Fit on frequency targets with exposure weights; reject zero-claim training."""
    features = _features(train)
    if len(train) == 0:
        raise ValueError("Training data must contain rows")
    try:
        claims = train["ClaimNb"].to_numpy(dtype=float, copy=True)
        exposure = train["Exposure"].to_numpy(dtype=float, copy=True)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Training requires numeric ClaimNb and Exposure") from error
    if not np.all(np.isfinite(claims)) or np.any(claims < 0) or np.any(claims != np.floor(claims)):
        raise ValueError("ClaimNb must be finite nonnegative integers")
    if not np.all(np.isfinite(exposure)) or np.any(exposure <= 0):
        raise ValueError("Exposure must be finite and positive")
    total_claims, total_exposure = claims.sum(), exposure.sum()
    if not np.isfinite(total_claims) or total_claims <= 0:
        raise ValueError("Training requires a positive total of claims")
    if not np.isfinite(total_exposure):
        raise ValueError("Total exposure must be finite")
    target = claims / exposure
    if not np.all(np.isfinite(target)):
        raise ValueError("Training frequency must be finite")
    baseline = MeanFrequency(float(total_claims / total_exposure))
    _checked_rates(np.array([baseline.rate]))
    glm_preprocessor = ColumnTransformer(
        [
            ("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
            ("numeric", StandardScaler(), NUMERIC),
        ]
    )
    hgb_preprocessor = ColumnTransformer(
        [
            (
                "categorical",
                OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1),
                CATEGORICAL,
            ),
            ("numeric", "passthrough", NUMERIC),
        ]
    )
    glm = PoissonRegressor(alpha=1e-4, max_iter=300, tol=1e-6)
    hgb = HistGradientBoostingRegressor(
        loss="poisson",
        max_iter=max_iter,
        max_leaf_nodes=15,
        min_samples_leaf=100,
        learning_rate=0.05,
        early_stopping=False,
        random_state=seed,
        categorical_features=[True] * len(CATEGORICAL) + [False] * len(NUMERIC),
    )
    with threadpool_limits(limits=2), warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        glm.fit(glm_preprocessor.fit_transform(features), target, sample_weight=exposure)
        hgb.fit(hgb_preprocessor.fit_transform(features), target, sample_weight=exposure)
    return {
        "mean": baseline,
        "poisson_glm": FrequencyModel(glm_preprocessor, glm),
        "poisson_hgb": FrequencyModel(hgb_preprocessor, hgb),
    }
