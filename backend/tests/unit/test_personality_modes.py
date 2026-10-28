"""Unit tests for personality modes and distress safety overrides."""

from backend.app.personality.manager import PersonalityManager
from backend.app.personality.schema import PersonalityMode


def test_personality_mode_attributes() -> None:
    """Verify that every personality mode has defined tone, verbosity, and initiative."""
    manager = PersonalityManager()

    for mode in PersonalityMode:
        config = manager.get_mode_config(mode)
        assert config.mode == mode
        assert config.tone_description
        assert config.prompt_modifier
        assert config.verbosity in ("minimal", "low", "balanced", "verbose")
        assert 0.0 <= config.initiative <= 1.0


def test_mode_switching() -> None:
    """Verify switching personality modes updates active configuration."""
    manager = PersonalityManager()
    assert manager.active_mode is PersonalityMode.ADAPTIVE

    manager.set_mode(PersonalityMode.FOCUS)
    mode_focus: PersonalityMode = manager.active_mode
    assert mode_focus == PersonalityMode.FOCUS
    assert manager.get_active_config().verbosity == "low"

    manager.set_mode(PersonalityMode.RELAX)
    mode_relax: PersonalityMode = manager.active_mode
    assert mode_relax == PersonalityMode.RELAX
    assert manager.get_active_config().allow_playful_banter is True


def test_distress_detection_suppresses_playful_teasing() -> None:
    """Critical safety test: Relax mode playful teasing is overridden during distress, health concerns, or crises."""
    manager = PersonalityManager()
    manager.set_mode(PersonalityMode.RELAX)

    # 1. Normal casual user utterance in Relax mode -> allowed banter
    casual_text = "Hey Cindercrest, check out my terrible code indentation!"
    prompt_casual = manager.build_system_prompt_for_input(casual_text)
    assert "playful" in prompt_casual.lower() or "banter" in prompt_casual.lower()

    # 2. Distress / health concern utterance -> banter strictly overridden
    distress_utterances = [
        "I'm feeling really severe chest pain right now.",
        "My anxiety is spiraling and I am having a panic attack.",
        "I just found out my mother was admitted to the hospital.",
        "I'm feeling completely overwhelmed, hopeless, and can't cope.",
    ]

    for utterance in distress_utterances:
        prompt_distress = manager.build_system_prompt_for_input(utterance)
        # Relax mode teasing/banter instructions MUST NOT be present
        assert "allow friendly banter" not in prompt_distress.lower()
        assert "playful teasing" not in prompt_distress.lower()
        assert "witty" not in prompt_distress.lower()
        # Supportive, empathetic, serious tone MUST be mandated
        assert "serious" in prompt_distress.lower() or "empathetic" in prompt_distress.lower() or "supportive" in prompt_distress.lower()


def test_safety_rules_invariant_across_all_modes() -> None:
    """Verify that core safety rules (no fake actions, no shell execution) exist across all personality prompts."""
    manager = PersonalityManager()

    for mode in PersonalityMode:
        manager.set_mode(mode)
        prompt = manager.build_system_prompt_for_input("General query")
        # Invariant safety rules
        assert "never claim to have taken physical or digital actions" in prompt.lower()
        assert "admit uncertainty honestly" in prompt.lower()
