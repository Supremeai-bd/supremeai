from tools.bangla_nlp import BengaliNLP


def test_bengali_nlp_detection():
    nlp = BengaliNLP()
    assert nlp.is_bengali("আমি বাংলা শিখছি") is True
    assert nlp.is_bengali("Hello world") is False


def test_bengali_nlp_tokenize():
    nlp = BengaliNLP()
    tokens = nlp.tokenize("আমি বাংলা ভালো ভাষা শিখছি")
    assert len(tokens) > 0
    assert "বাংলা" in tokens


def test_bengali_nlp_sentiment():
    nlp = BengaliNLP()
    res = nlp.analyze_sentiment("এটা খুব সুন্দর")
    assert res["label"] == "positive"
    res2 = nlp.analyze_sentiment("এটা খারাপ")
    assert res2["label"] == "negative"


def test_bengali_nlp_language_mix():
    nlp = BengaliNLP()
    res = nlp.detect_language_mix("আমি love বাংলা")
    assert res["primary"] in {"bengali", "mixed"}
