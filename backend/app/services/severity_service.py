def calculate_severity(analysis: dict) -> tuple[int, str, list[str]]:
    score = 0
    factors: list[str] = []
    risks = analysis.get("public_safety_risks", [])
    if isinstance(risks, list) and risks:
        points = min(35, 15 + 5 * (len(risks) - 1))
        score += points
        factors.append(f"Public safety risks identified (+{points})")
    obstruction = analysis.get("road_obstruction_level", "none")
    points = {"none": 0, "minor": 8, "partial": 18, "severe": 28}.get(str(obstruction).lower(), 0)
    if points:
        score += points
        factors.append(f"{str(obstruction).title()} road obstruction (+{points})")
    damage = analysis.get("visible_damage_indicators", [])
    if isinstance(damage, list) and damage:
        points = min(20, len(damage) * 5)
        score += points
        factors.append(f"{len(damage)} visible damage indicator(s) (+{points})")
    try:
        confidence = max(0.0, min(1.0, float(analysis.get("confidence_score", 0))))
    except (TypeError, ValueError):
        confidence = 0.0
    points = round(confidence * 15)
    score += points
    if points:
        factors.append(f"AI confidence {confidence:.0%} (+{points})")
    weather = analysis.get("weather_context", {})
    if analysis.get("category") in {"Water leakage and flooding", "Drainage and sewage problems"} and isinstance(weather, dict):
        try:
            rainfall = max(0.0, float(weather.get("rainfall_mm", 0)))
        except (TypeError, ValueError):
            rainfall = 0.0
        points = min(10, round(rainfall * 2))
        if points:
            score += points
            factors.append(f"Recent local rainfall {rainfall:g} mm (+{points})")
    score = min(100, score)
    level = "Critical" if score >= 75 else "High" if score >= 50 else "Medium" if score >= 25 else "Low"
    if not factors:
        factors.append("No additional risk indicators were identified")
    return score, level, factors
