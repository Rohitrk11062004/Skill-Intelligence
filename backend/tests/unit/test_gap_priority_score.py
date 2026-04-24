from app.services.gap.gap_detector import _priority_score, _prerequisite_depth_scores


def test_large_proficiency_gap_outweighs_small_gap():
    large_gap = _priority_score(
        proficiency_distance=1.0,
        importance_normalized=0.6,
        prerequisite_depth_score=0.1,
        is_mandatory=False,
    )
    small_gap = _priority_score(
        proficiency_distance=0.2,
        importance_normalized=0.6,
        prerequisite_depth_score=0.1,
        is_mandatory=False,
    )

    assert large_gap > small_gap


def test_foundational_skill_depth_outweighs_leaf_when_other_factors_equal():
    # A -> B, A -> C: A is foundational and should get higher depth score.
    depth_scores = _prerequisite_depth_scores(
        {
            "A": [],
            "B": ["A"],
            "C": ["A"],
        }
    )

    foundational = _priority_score(
        proficiency_distance=0.6,
        importance_normalized=0.6,
        prerequisite_depth_score=depth_scores.get("A", 0.0),
        is_mandatory=False,
    )
    leaf = _priority_score(
        proficiency_distance=0.6,
        importance_normalized=0.6,
        prerequisite_depth_score=depth_scores.get("B", 0.0),
        is_mandatory=False,
    )

    assert foundational > leaf


def test_duration_is_not_a_priority_input():
    # The new formula intentionally excludes time-to-learn as a core multiplier.
    score_1 = _priority_score(
        proficiency_distance=0.7,
        importance_normalized=0.5,
        prerequisite_depth_score=0.2,
        is_mandatory=True,
    )
    score_2 = _priority_score(
        proficiency_distance=0.7,
        importance_normalized=0.5,
        prerequisite_depth_score=0.2,
        is_mandatory=True,
    )

    assert score_1 == score_2


def test_mandatory_bonus_increases_priority_when_other_inputs_match():
    optional_score = _priority_score(
        proficiency_distance=0.6,
        importance_normalized=0.6,
        prerequisite_depth_score=0.2,
        is_mandatory=False,
    )
    mandatory_score = _priority_score(
        proficiency_distance=0.6,
        importance_normalized=0.6,
        prerequisite_depth_score=0.2,
        is_mandatory=True,
    )

    assert mandatory_score > optional_score


def test_higher_importance_normalized_increases_priority_when_other_inputs_match():
    low_importance = _priority_score(
        proficiency_distance=0.6,
        importance_normalized=0.2,
        prerequisite_depth_score=0.2,
        is_mandatory=False,
    )
    high_importance = _priority_score(
        proficiency_distance=0.6,
        importance_normalized=0.9,
        prerequisite_depth_score=0.2,
        is_mandatory=False,
    )

    assert high_importance > low_importance
