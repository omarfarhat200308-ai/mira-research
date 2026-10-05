"""
Unit tests for the hardcoded red-flag rule engine, in complete isolation
from any LLM or mock — proving the safety net works standalone, since this
is the piece that must never depend on model behavior at all.
"""
from mira.safety.red_flags import evaluate_red_flags


def _ir(tags: list[str], age=None, sex=None, is_pregnant=None) -> dict:
    return {
        "symptom_tags": tags,
        "patient": {"age": age, "sex": sex, "is_pregnant": is_pregnant},
    }


def test_no_symptoms_no_red_flags():
    assert evaluate_red_flags(_ir([])) == []


def test_chest_pain_alone_does_not_fire():
    assert evaluate_red_flags(_ir(["chest_pain"])) == []


def test_chest_pain_with_shortness_of_breath_fires():
    flags = evaluate_red_flags(_ir(["chest_pain", "shortness_of_breath"]))
    assert "cardio_chest_pain_with_dyspnea" in flags


def test_preeclampsia_pattern_fires_with_pregnant_tag():
    flags = evaluate_red_flags(
        _ir(["pregnant", "severe_headache", "swelling_edema"])
    )
    assert "obstetric_preeclampsia_pattern" in flags


def test_preeclampsia_pattern_fires_with_is_pregnant_flag_instead_of_tag():
    flags = evaluate_red_flags(
        _ir(["severe_headache", "visual_disturbance", "swelling_edema"], is_pregnant=True)
    )
    assert "obstetric_preeclampsia_pattern" in flags


def test_preeclampsia_pattern_does_not_fire_without_hypertension_or_edema():
    # Pregnant + severe headache alone, no edema/hypertension signal.
    flags = evaluate_red_flags(_ir(["pregnant", "severe_headache"]))
    assert "obstetric_preeclampsia_pattern" not in flags


def test_preeclampsia_pattern_does_not_fire_if_not_pregnant():
    flags = evaluate_red_flags(
        _ir(["severe_headache", "visual_disturbance", "swelling_edema"], is_pregnant=False)
    )
    assert "obstetric_preeclampsia_pattern" not in flags


def test_postpartum_hemorrhage_fires():
    flags = evaluate_red_flags(_ir(["postpartum_bleeding_heavy"]))
    assert "obstetric_heavy_bleeding" in flags


def test_infant_meningitis_pattern_fires_under_age_2():
    flags = evaluate_red_flags(_ir(["high_fever", "stiff_neck"], age=0))
    assert "infant_fever_meningitis_pattern" in flags


def test_infant_meningitis_pattern_does_not_fire_for_older_child():
    flags = evaluate_red_flags(_ir(["high_fever", "stiff_neck"], age=10))
    assert "infant_fever_meningitis_pattern" not in flags


def test_seizure_fires():
    assert "neuro_seizure_or_loc" in evaluate_red_flags(_ir(["seizure"]))


def test_loss_of_consciousness_fires():
    assert "neuro_seizure_or_loc" in evaluate_red_flags(_ir(["loss_of_consciousness"]))


def test_stroke_pattern_fires():
    assert "neuro_stroke_pattern" in evaluate_red_flags(_ir(["one_sided_weakness"]))


def test_mild_symptoms_do_not_fire_anything():
    flags = evaluate_red_flags(_ir(["runny_nose", "cough", "mild_pain"]))
    assert flags == []


def test_gi_bleeding_fires():
    assert "gi_bleeding" in evaluate_red_flags(_ir(["vomiting_blood"]))
    assert "gi_bleeding" in evaluate_red_flags(_ir(["black_or_bloody_stool"]))
