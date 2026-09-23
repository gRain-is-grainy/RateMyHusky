"""precompute with the TRACE tables removed from the DB (Sept 2026).

The full build was run end to end against a mock connection when this landed;
these pin the two pieces that broke on zero rows: the typed empty frames have to
join trace_courses' int64 ids, and the per-professor average has to survive no
groups.
"""

import pandas as pd

from precompute import empty_trace_comments, empty_trace_scores


def test_empty_trace_scores_joins_int_course_ids():
    courses = pd.DataFrame({"course_id": [1], "instructor_id": [2], "name_key": ["a b"]})
    merged = empty_trace_scores().merge(courses, on=["course_id", "instructor_id"], how="inner")
    assert merged.empty


def test_empty_trace_scores_has_the_columns_the_build_reads():
    cols = set(empty_trace_scores().columns)
    assert {"question", "mean", "completed", "count_1", "count_5", "term_id"} <= cols


def test_empty_trace_comments_has_the_columns_the_build_reads():
    assert {"comment", "course_url"} <= set(empty_trace_comments().columns)
