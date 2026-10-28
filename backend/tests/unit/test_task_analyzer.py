"""Unit tests for the TaskAnalyzer intent classification engine."""

import pytest

from backend.app.agent.analyzer import TaskAnalyzer
from backend.app.agent.schema import IntentClassificationResult, TaskIntent
from backend.app.core.exceptions import ValidationError


def test_analyzer_rejects_empty_input() -> None:
    analyzer = TaskAnalyzer()
    with pytest.raises(ValidationError):
        analyzer.classify_intent("   ")


def test_analyzer_classifies_conversation() -> None:
    analyzer = TaskAnalyzer()
    cases = [
        "Hello Cindercrest",
        "Hi, how are you doing today?",
        "Good morning!",
        "Thanks for your help, see you later.",
        "Tell me a joke.",
        "Who are you?",
    ]
    for prompt in cases:
        result = analyzer.classify_intent(prompt)
        assert isinstance(result, IntentClassificationResult)
        assert result.intent == TaskIntent.CONVERSATION
        assert result.confidence >= 0.7


def test_analyzer_classifies_information() -> None:
    analyzer = TaskAnalyzer()
    cases = [
        "What time is it right now?",
        "What is the current date?",
        "Calculate 45 * 12",
        "What is 100 / 4?",
        "Show me system specs",
        "Count the words in 'The quick brown fox jumps over the lazy dog'",
    ]
    for prompt in cases:
        result = analyzer.classify_intent(prompt)
        assert isinstance(result, IntentClassificationResult)
        assert result.intent == TaskIntent.INFORMATION
        assert result.confidence >= 0.7


def test_analyzer_classifies_task_execution() -> None:
    analyzer = TaskAnalyzer()
    cases = [
        "Run system diagnostics and analyze the output",
        "Execute the diagnostics workflow",
        "Calculate 50 * 2, then check the current time",
        "Run diagnostics and inspect text metrics",
    ]
    for prompt in cases:
        result = analyzer.classify_intent(prompt)
        assert isinstance(result, IntentClassificationResult)
        assert result.intent == TaskIntent.TASK_EXECUTION
        assert result.confidence >= 0.7
