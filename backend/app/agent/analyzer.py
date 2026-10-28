"""Intent analyzer for categorizing user prompts into structured intents."""

import re

from backend.app.agent.schema import IntentClassificationResult, TaskIntent
from backend.app.core.exceptions import ValidationError

# Regex patterns for conversation cues
CONVERSATION_PATTERNS = [
    r"^(hello|hi|hey|greetings|good morning|good afternoon|good evening)\b",
    r"\b(how are you|how's it going|what's up|nice to meet you)\b",
    r"\b(thank you|thanks|bye|goodbye|see you|have a good day)\b",
    r"\b(who are you|tell me a joke|what is your name)\b",
]

# Regex patterns for informational queries
INFORMATION_PATTERNS = [
    r"\b(what time|current time|what is the time|what date|current date|what day)\b",
    r"\b(calculat\w*|comput\w*|solve|math|\d+\s*[\+\-\*\/\^]\s*\d+)\b",
    r"\b(system specs|system diagnostics|specs of|diagnostics info|os info)\b",
    r"\b(count words|analyze text|word count|character count)\b",
    r"\b(what is|explain|define)\b",
    r"\b(search files|find files|find documents?|search documents?|read file|read document)\b",
]

# Patterns indicating multi-step workflows or explicit task execution
TASK_PATTERNS = [
    r"\b(and then|after that|followed by|then check|then calculate|, then)\b",
    r"\b(execute|orchestrate|pipeline|workflow|multi-step)\b",
    r"\b(run|perform|execute|calculate)\b.*\b(and|then|followed by)\b",
    r"\b(find|search|look for)\b.*\b(and|then)?\b.*\b(summariz\w*|analyze|read)\b",
    r"\b(summariz\w*|read)\b.*\b(document|file|assessment|spec)\b",
]


class TaskAnalyzer:
    """Classifies user requests into CONVERSATION, INFORMATION, or TASK_EXECUTION."""

    def classify_intent(self, user_input: str) -> IntentClassificationResult:
        """Classify the intent of the input string."""
        cleaned = user_input.strip()
        if not cleaned:
            raise ValidationError("User input cannot be empty for intent classification")

        lowered = cleaned.lower()

        # Check for multi-step task execution patterns first
        for pat in TASK_PATTERNS:
            if re.search(pat, lowered):
                return IntentClassificationResult(
                    intent=TaskIntent.TASK_EXECUTION,
                    confidence=0.90,
                    reasoning=f"Matched multi-step or execution pattern: '{pat}'",
                )

        # Check for information patterns
        for pat in INFORMATION_PATTERNS:
            if re.search(pat, lowered):
                return IntentClassificationResult(
                    intent=TaskIntent.INFORMATION,
                    confidence=0.85,
                    reasoning=f"Matched information query pattern: '{pat}'",
                )

        # Check for conversational patterns
        for pat in CONVERSATION_PATTERNS:
            if re.search(pat, lowered):
                return IntentClassificationResult(
                    intent=TaskIntent.CONVERSATION,
                    confidence=0.90,
                    reasoning=f"Matched conversational greeting/closing pattern: '{pat}'",
                )

        # Default fallback: if short statement or general inquiry, consider conversation
        if len(cleaned.split()) <= 4:
            return IntentClassificationResult(
                intent=TaskIntent.CONVERSATION,
                confidence=0.70,
                reasoning="Short general statement classified as conversational dialogue",
            )

        # Longer query without task trigger defaults to information
        return IntentClassificationResult(
            intent=TaskIntent.INFORMATION,
            confidence=0.75,
            reasoning="Default classification for descriptive question or prompt",
        )
