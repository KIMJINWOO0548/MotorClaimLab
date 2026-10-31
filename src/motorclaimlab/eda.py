"""SQL exploration with count/exposure totals in disposable in-memory SQLite."""

import sqlite3

from .data import validate_frame


def summarize_sql(frame) -> dict:
    """Aggregate exposure before dividing; no individual records are returned."""
    validate_frame(frame)
    with sqlite3.connect(":memory:") as connection:
        connection.row_factory = sqlite3.Row
        frame[["ClaimNb", "Exposure", "Area"]].to_sql("policies", connection, index=False)
        overall = dict(
            connection.execute(
                "SELECT COUNT(*) AS rows, SUM(ClaimNb) AS claims, SUM(Exposure) AS exposure, "
                "1.0 * SUM(ClaimNb) / SUM(Exposure) AS frequency FROM policies"
            ).fetchone()
        )
        by_area = [
            dict(row)
            for row in connection.execute(
                "SELECT Area AS area, COUNT(*) AS rows, SUM(ClaimNb) AS claims, "
                "SUM(Exposure) AS exposure, 1.0 * SUM(ClaimNb) / SUM(Exposure) AS frequency "
                "FROM policies GROUP BY Area ORDER BY Area"
            )
        ]
    return {"overall": overall, "by_area": by_area}
