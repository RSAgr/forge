from app.services.severity_service import calculate_severity


def test_severity_score_and_factors_are_explainable():
    score, level, factors = calculate_severity({
        "category": "Potholes and road damage",
        "public_safety_risks": ["traffic collision risk"],
        "road_obstruction_level": "severe",
        "visible_damage_indicators": ["cracks", "pavement loss", "standing water", "edge failure"],
        "confidence_score": 1,
    })
    assert score == 78
    assert level == "Critical"
    assert len(factors) == 4
    assert any("safety risks" in factor for factor in factors)
    assert any("road obstruction" in factor for factor in factors)


def test_rainfall_only_affects_water_and_drainage_severity():
    water = {"category": "Water leakage and flooding", "confidence_score": 0.5,
             "weather_context": {"rainfall_mm": 4}}
    unrelated = {"category": "Broken streetlights", "confidence_score": 0.5,
                 "weather_context": {"rainfall_mm": 4}}
    water_score, _, water_factors = calculate_severity(water)
    other_score, _, other_factors = calculate_severity(unrelated)
    assert water_score == other_score + 8
    assert any("rainfall" in factor for factor in water_factors)
    assert not any("rainfall" in factor for factor in other_factors)


def test_severity_caps_at_100_and_empty_analysis_is_low():
    score, level, factors = calculate_severity({
        "category": "Drainage and sewage problems",
        "public_safety_risks": ["a", "b", "c", "d", "e"],
        "road_obstruction_level": "severe",
        "visible_damage_indicators": ["a", "b", "c", "d", "e"],
        "confidence_score": 1,
        "weather_context": {"rainfall_mm": 20},
    })
    assert (score, level) == (100, "Critical")
    assert any("rainfall" in factor for factor in factors)
    assert calculate_severity({}) == (0, "Low", ["No additional risk indicators were identified"])
