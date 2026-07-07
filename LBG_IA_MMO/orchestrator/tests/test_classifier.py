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


def test_classifier_detects_opengame_prototype() -> None:
    c = DeterministicIntentClassifier()
    intent, conf = c.classify("prépare un prototype jeu avec OpenGame")
    assert intent == "prototype_game"
    assert 0.0 <= conf <= 1.0


def test_classifier_detects_project_status_questions() -> None:
    c = DeterministicIntentClassifier()
    for text in (
        "que peut tu me dire sur le projet LBG_Project_03, ou en est on ?",
        "je suis l'initiateur du projet, et tu es le projet",
        "comment avance le projet ?",
    ):
        intent, conf = c.classify(text)
        assert intent == "project_pm", text
        assert conf >= 0.7


def test_classifier_greeting_is_dialogue() -> None:
    c = DeterministicIntentClassifier()
    intent, conf = c.classify("Bonjour")
    assert intent == "npc_dialogue"
    assert conf >= 0.6

