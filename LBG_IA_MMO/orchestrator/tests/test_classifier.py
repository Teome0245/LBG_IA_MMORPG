from introspection.deterministic_classifier import DeterministicIntentClassifier


def test_classifier_detects_quest_keywords_task_work() -> None:
    c = DeterministicIntentClassifier()
    for text in (
        "J'ai une tache pour toi",
        "J'ai une tâche pour toi",
        "Du travail pour moi ?",
        "Des travaux à faire ?",
    ):
        intent, conf = c.classify(text)
        assert intent == "quest_request"
        assert 0.0 <= conf <= 1.0


def test_classifier_detects_devops_probe() -> None:
    c = DeterministicIntentClassifier()
    intent, conf = c.classify("sonde devops stp")
    assert intent == "devops_probe"
    assert 0.0 <= conf <= 1.0

