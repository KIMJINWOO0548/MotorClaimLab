"""SQL group ordering with precise count and exposure accumulation."""

import math
import sqlite3
from contextlib import closing
from itertools import groupby
from operator import itemgetter

import pandas as pd

from .data import validate_frame


def summarize_sql(frame) -> dict:
    """Aggregate exposure before dividing; no individual records are returned."""
    audit = validate_frame(frame)
    overall = {key: audit[key] for key in ("rows", "claims", "exposure")}
    overall["frequency"] = overall["claims"] / overall["exposure"]
    records = frame[["Area", "ClaimNb", "Exposure"]].assign(
        Area=frame["Area"].astype(str),
        ClaimNb=pd.to_numeric(frame["ClaimNb"]).astype("int64"),
        Exposure=pd.to_numeric(frame["Exposure"]).astype(float),
    )
    by_area = []
    with closing(sqlite3.connect(":memory:")) as connection:
        records.to_sql("policies", connection, index=False)
        ordered = connection.execute("SELECT Area, ClaimNb, Exposure FROM policies ORDER BY Area")
        for area, group in groupby(ordered, key=itemgetter(0)):
            rows = claims = 0

            def exposures(members):
                nonlocal rows, claims
                for _, count, exposure in members:
                    rows += 1
                    claims += count
                    yield exposure

            # SQLite SUM can overflow int64 and does not share the audit's exposure arithmetic.
            exposure = math.fsum(exposures(group))
            by_area.append(
                {
                    "area": area,
                    "rows": rows,
                    "claims": claims,
                    "exposure": exposure,
                    "frequency": claims / exposure,
                }
            )
    return {"overall": overall, "by_area": by_area}
