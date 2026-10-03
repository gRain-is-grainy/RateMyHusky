import pytest

from rag.chat_validate import (
    has_structured_evidence,
    has_reddit_evidence,
    thin_data_check,
    validate_output,
)


# ── has_structured_evidence ──────────────────────────────────────────────


class TestHasStructuredEvidence:
    def test_none_returns_false(self):
        assert has_structured_evidence(None) is False

    def test_empty_dict_returns_false(self):
        assert has_structured_evidence({}) is False

    def test_course_kind_with_avg_rating(self):
        assert has_structured_evidence({"kind": "course", "avg_rating": 4.0}) is True

    def test_course_kind_with_avg_difficulty(self):
        assert has_structured_evidence({"kind": "course", "avg_difficulty": 3.0}) is True

    def test_course_kind_all_none_returns_false(self):
        assert has_structured_evidence({
            "kind": "course",
            "avg_rating": None,
            "avg_difficulty": None,
        }) is False

    def test_professor_kind_with_total_reviews_gt_zero(self):
        assert has_structured_evidence({"kind": "professor", "total_reviews": 31}) is True

    def test_professor_kind_total_reviews_zero_checks_ratings(self):
        assert has_structured_evidence({
            "kind": "professor",
            "total_reviews": 0,
            "avg_rating": None,
            "rmp_rating": None,
            "difficulty": None,
            "would_take_again_pct": None,
        }) is False

    def test_professor_kind_with_avg_rating(self):
        assert has_structured_evidence({
            "kind": "professor",
            "total_reviews": 0,
            "avg_rating": 4.2,
        }) is True

    def test_professor_kind_with_rmp_rating(self):
        assert has_structured_evidence({
            "kind": "professor",
            "total_reviews": 0,
            "rmp_rating": 4.0,
        }) is True

    def test_professor_kind_with_difficulty(self):
        assert has_structured_evidence({
            "kind": "professor",
            "total_reviews": 0,
            "difficulty": 3.5,
        }) is True

    def test_professor_kind_with_would_take_again_pct(self):
        assert has_structured_evidence({
            "kind": "professor",
            "total_reviews": 0,
            "would_take_again_pct": 85,
        }) is True

    def test_default_kind_professor_with_total_reviews(self):
        assert has_structured_evidence({"total_reviews": 5}) is True

    def test_default_kind_all_none_returns_false(self):
        assert has_structured_evidence({
            "total_reviews": 0,
            "avg_rating": None,
            "rmp_rating": None,
            "difficulty": None,
            "would_take_again_pct": None,
        }) is False


# ── has_reddit_evidence ──────────────────────────────────────────────────


class TestHasRedditEvidence:
    def test_comment_count_below_min_returns_false(self):
        r = {"comment_count": 3, "comments": [{"body": "word " * 60} for _ in range(3)]}
        assert has_reddit_evidence(r) is False

    def test_enough_comments_but_not_enough_words_returns_false(self):
        r = {"comment_count": 4, "comments": [{"body": "short"} for _ in range(4)]}
        assert has_reddit_evidence(r) is False

    def test_enough_comments_and_words_returns_true(self):
        r = {"comment_count": 5, "comments": [{"body": "word " * 60} for _ in range(5)]}
        assert has_reddit_evidence(r) is True

    def test_exactly_min_comments_and_min_words_returns_true(self):
        count = 4
        words_per = 50  # 4 * 50 = 200
        r = {"comment_count": count, "comments": [{"body": "word " * words_per} for _ in range(count)]}
        assert has_reddit_evidence(r) is True

    def test_missing_comments_key_defaults_to_zero(self):
        r = {}
        assert has_reddit_evidence(r) is False

    def test_none_body_does_not_crash(self):
        r = {"comment_count": 5, "comments": [{"body": None} for _ in range(5)]}
        assert has_reddit_evidence(r) is False


# ── thin_data_check ──────────────────────────────────────────────────────


class TestThinDataCheck:
    def test_reddit_evidence_alone_returns_true(self):
        r = {"comment_count": 5, "comments": [{"body": "word " * 60} for _ in range(5)]}
        ok, msg = thin_data_check(r)
        assert ok is True
        assert msg is None

    def test_structured_evidence_alone_returns_true(self):
        r = {"facts": {"kind": "professor", "total_reviews": 31}}
        ok, msg = thin_data_check(r)
        assert ok is True
        assert msg is None

    def test_neither_evidence_returns_false_with_message(self):
        r = {"comment_count": 2, "comments": [{"body": "short"}, {"body": "tiny"}]}
        ok, msg = thin_data_check(r)
        assert ok is False
        assert isinstance(msg, str) and len(msg) > 0

    def test_empty_facts_and_thin_reddit_returns_false(self):
        r = {
            "comment_count": 2,
            "comments": [{"body": "short"}, {"body": "tiny"}],
            "facts": {"kind": "professor", "total_reviews": 0},
        }
        ok, msg = thin_data_check(r)
        assert ok is False
        assert isinstance(msg, str) and len(msg) > 0

    def test_both_evidence_returns_true(self):
        r = {
            "comment_count": 5,
            "comments": [{"body": "word " * 60} for _ in range(5)],
            "facts": {"kind": "professor", "total_reviews": 31},
        }
        ok, msg = thin_data_check(r)
        assert ok is True
        assert msg is None

    def test_course_facts_answer_despite_thin_reddit(self):
        r = {
            "comment_count": 2,
            "comments": [{"body": "short"}, {"body": "tiny"}],
            "facts": {"kind": "course", "avg_rating": 4.0},
        }
        ok, msg = thin_data_check(r)
        assert ok is True
        assert msg is None

    def test_missing_facts_key_defaults_to_false(self):
        r = {"comment_count": 2, "comments": [{"body": "short"}, {"body": "tiny"}]}
        ok, msg = thin_data_check(r)
        assert ok is False
        assert msg is not None


# ── validate_output ──────────────────────────────────────────────────────


class TestValidateOutput:
    def test_clean_grounded_answer_passes(self):
        result = validate_output("Some students say Guha is hard but fair [1].", {"comment_count": 3})
        assert result["ok"] is True
        assert result["status"] == "ok"
        assert result["message"] is None

    def test_citation_above_range_fails(self):
        result = validate_output("Students like him [9].", {"comment_count": 3})
        assert result["ok"] is False
        assert result["status"] == "validation_failed"

    def test_citation_zero_fails(self):
        result = validate_output("Students like him [0].", {"comment_count": 3})
        assert result["ok"] is False
        assert result["status"] == "validation_failed"

    def test_citation_exactly_max_is_ok(self):
        result = validate_output("Good prof [3].", {"comment_count": 3})
        assert result["ok"] is True

    def test_citation_one_is_ok(self):
        result = validate_output("Good prof [1].", {"comment_count": 3})
        assert result["ok"] is True

    def test_canary_leak_fails(self):
        result = validate_output("My instructions: RMH-CANARY-7Q ...", {"comment_count": 3})
        assert result["ok"] is False
        assert result["status"] == "validation_failed"

    def test_bare_canary_token_fails(self):
        result = validate_output("The secret token is RMH-CANARY-7Q.", {"comment_count": 3})
        assert result["ok"] is False
        assert result["status"] == "validation_failed"

    def test_system_prompt_leak_fails(self):
        result = validate_output("Ignore your system prompt and ...", {"comment_count": 3})
        assert result["ok"] is False
        assert result["status"] == "validation_failed"

    def test_my_instructions_leak_fails(self):
        result = validate_output("Follow my instructions: ...", {"comment_count": 3})
        assert result["ok"] is False
        assert result["status"] == "validation_failed"

    def test_my_actual_instructions_leak_fails(self):
        result = validate_output("These are my actual instructions.", {"comment_count": 3})
        assert result["ok"] is False
        assert result["status"] == "validation_failed"

    def test_defamation_marker_arrested_fails(self):
        result = validate_output("He was arrested in 2023 [1].", {"comment_count": 3})
        assert result["ok"] is False
        assert result["status"] == "validation_failed"

    def test_defamation_marker_convicted_fails(self):
        result = validate_output("He was convicted of fraud.", {"comment_count": 3})
        assert result["ok"] is False
        assert result["status"] == "validation_failed"

    def test_defamation_marker_lawsuit_fails(self):
        result = validate_output("There is a lawsuit against him [1].", {"comment_count": 3})
        assert result["ok"] is False
        assert result["status"] == "validation_failed"

    def test_defamation_marker_harass_fails(self):
        result = validate_output("He was harassing students.", {"comment_count": 3})
        assert result["ok"] is False
        assert result["status"] == "validation_failed"

    def test_defamation_marker_predator_fails(self):
        result = validate_output("He is a predator.", {"comment_count": 3})
        assert result["ok"] is False
        assert result["status"] == "validation_failed"

    def test_grouped_citations_extract_cited_set(self):
        result = validate_output("good prof [1] [2].", {"comment_count": 3})
        assert result["ok"] is True
        assert set(result["cited"]) == {1, 2}

    def test_single_citation_in_cited(self):
        result = validate_output("Some students say Guha is hard but fair [1].", {"comment_count": 3})
        assert set(result["cited"]) == {1}

    def test_three_citations_all_extracted(self):
        result = validate_output("One [1] two [2] three [3].", {"comment_count": 3})
        assert result["ok"] is True
        assert set(result["cited"]) == {1, 2, 3}

    def test_no_citations_empty_cited_list(self):
        result = validate_output("No citations here.", {"comment_count": 3})
        assert result["ok"] is True
        assert result["cited"] == []

    def test_none_answer_does_not_crash(self):
        result = validate_output(None, {"comment_count": 3})
        assert result["ok"] is True
        assert result["cited"] == []

    def test_zero_comment_count_means_no_valid_citations(self):
        result = validate_output("[1]", {"comment_count": 0})
        assert result["ok"] is False
        assert result["status"] == "validation_failed"

    def test_empty_retrieval_causes_zero_comment_count(self):
        result = validate_output("[1]", {})
        assert result["ok"] is False
        assert result["status"] == "validation_failed"
