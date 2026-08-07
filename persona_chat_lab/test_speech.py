from speech import _spoken_text


def test_spoken_text_removes_stage_direction():
    assert _spoken_text("*[Jaw tightens]* I was at the yard.") == "I was at the yard."
