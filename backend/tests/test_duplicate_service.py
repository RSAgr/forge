from app.services.duplicate_service import text_similarity


def test_similar_issue_descriptions_score_as_duplicates():
    assert text_similarity(
        "Large pothole blocking the north lane with deep road damage",
        "Deep pothole causing road damage in the north lane",
    ) > 0.3


def test_unrelated_or_empty_descriptions_do_not_match():
    assert text_similarity("broken streetlight at the corner", "garbage collection near school") < 0.3
    assert text_similarity("", "pothole on the road") == 0
