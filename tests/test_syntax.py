from pdfparser.syntax import analyze


def roles(text):
    return {(text[s.start:s.end], s.role) for s in analyze([("b1", text)])}


def test_simple_svo():
    r = roles("The auditor should evaluate the controls.")
    assert ("The auditor", "SUBJECT") in r
    assert ("should evaluate", "VERB") in r
    assert ("the controls", "OBJECT") in r


def test_relative_clause_and_phrase():
    r = roles("The auditor reviews the controls that the organization implemented during the audit.")
    assert ("that the organization implemented during the audit", "CLAUSE") in r
    assert ("the organization", "SUBJECT") in r


def test_root_prep_phrase():
    assert ("During the audit", "PHRASE") in roles("During the audit, the auditor reviews the logs.")


def test_short_block_skipped():
    assert analyze([("b1", "Table 1.1")]) == []


def test_offsets_are_block_relative_across_blocks():
    spans = analyze([("b1", "Short one here."), ("b2", "The team tests the plan.")])
    text = "The team tests the plan."
    assert ("The team", "SUBJECT") in {(text[s.start:s.end], s.role) for s in spans if s.block_key == "b2"}


def test_same_role_overlap_keeps_outer():
    spans = analyze([("b1", "The manager of the team that owns the system approved it.")])
    for a in spans:
        for b in spans:
            if a is not b and a.block_key == b.block_key and a.role == b.role:
                assert not (a.start <= b.start and b.end <= a.end and (a.start, a.end) != (b.start, b.end))


def test_non_contiguous_verb_group_splits():
    text = "The auditor has, in the meantime, reviewed the controls."
    r = roles(text)
    assert ("has", "VERB") in r and ("reviewed", "VERB") in r


def test_subtree_excludes_trailing_punctuation():
    text = "The auditor, who reviewed the logs, approved the plan."
    clauses = [t for t, role in roles(text) if role == "CLAUSE"]
    assert clauses and all(not t.endswith(",") for t in clauses)


def test_offsets_are_utf16_after_non_bmp_char():
    text = "𝑥 The auditor reviews the logs."
    u16 = text.encode("utf-16-le")
    got = {u16[2 * s.start:2 * s.end].decode("utf-16-le") for s in analyze([("b1", text)]) if s.role == "SUBJECT"}
    assert "The auditor" in got
