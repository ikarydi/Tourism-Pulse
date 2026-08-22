"""Tests for pulse.narrative.generate_narrative - the LLM half of the
insight engine. No real network calls: the Groq client is stubbed."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from groq import GroqError
from tourism_pulse_api.pulse.calculator import PulseResult
from tourism_pulse_api.pulse.insights import DimensionEvidence, EvidenceSignal
from tourism_pulse_api.pulse.narrative import generate_narrative


def make_pulse_result(**overrides) -> PulseResult:
    defaults = dict(
        pulse=60.0, demand=60.0, capacity=60.0, events=60.0,
        environment=60.0, risk=60.0, economic=60.0,
    )
    return PulseResult(**{**defaults, **overrides})


def make_evidence() -> dict[str, DimensionEvidence]:
    demand = DimensionEvidence(
        dimension="demand",
        value=60.0,
        contributing_signals=[
            EvidenceSignal(
                signal_type="tourism_nights",
                source="ksh",
                value=1000.0,
                unit="nights",
                observed_at=datetime(2026, 8, 20, tzinfo=UTC),
            )
        ],
        related_articles=[],
        related_videos=[],
        related_events=[],
    )
    other = DimensionEvidence(
        dimension="risk",
        value=60.0,
        contributing_signals=[],
        related_articles=[],
        related_videos=[],
        related_events=[],
    )
    return {"demand": demand, "risk": other}


def _stub_response(text: str) -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = text
    return response


def test_returns_none_when_no_api_key_configured() -> None:
    with patch("tourism_pulse_api.pulse.narrative.settings") as mock_settings:
        mock_settings.groq_api_key = None

        result = generate_narrative(
            place_name="Budapest",
            pulse=make_pulse_result(),
            evidence=make_evidence(),
            headline="Moderate tourism activity",
        )

    assert result is None


def test_returns_the_generated_text_when_configured() -> None:
    with (
        patch("tourism_pulse_api.pulse.narrative.settings") as mock_settings,
        patch("tourism_pulse_api.pulse.narrative.Groq") as mock_groq_cls,
    ):
        mock_settings.groq_api_key = "fake-key"
        mock_settings.narrative_model = "llama-3.3-70b-versatile"
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _stub_response(
            "  Budapest is showing steady demand.  "
        )
        mock_groq_cls.return_value = mock_client

        result = generate_narrative(
            place_name="Budapest",
            pulse=make_pulse_result(),
            evidence=make_evidence(),
            headline="Moderate tourism activity",
        )

    assert result == "Budapest is showing steady demand."


def test_prompt_includes_the_actual_evidence() -> None:
    with (
        patch("tourism_pulse_api.pulse.narrative.settings") as mock_settings,
        patch("tourism_pulse_api.pulse.narrative.Groq") as mock_groq_cls,
    ):
        mock_settings.groq_api_key = "fake-key"
        mock_settings.narrative_model = "llama-3.3-70b-versatile"
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _stub_response("ok")
        mock_groq_cls.return_value = mock_client

        generate_narrative(
            place_name="Budapest",
            pulse=make_pulse_result(),
            evidence=make_evidence(),
            headline="Moderate tourism activity",
        )

    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    user_message = call_kwargs["messages"][1]["content"]
    assert "Budapest" in user_message
    assert "tourism_nights" in user_message
    assert "ksh" in user_message


def test_returns_none_on_groq_error() -> None:
    with (
        patch("tourism_pulse_api.pulse.narrative.settings") as mock_settings,
        patch("tourism_pulse_api.pulse.narrative.Groq") as mock_groq_cls,
    ):
        mock_settings.groq_api_key = "fake-key"
        mock_settings.narrative_model = "llama-3.3-70b-versatile"
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = GroqError("boom")
        mock_groq_cls.return_value = mock_client

        result = generate_narrative(
            place_name="Budapest",
            pulse=make_pulse_result(),
            evidence=make_evidence(),
            headline="Moderate tourism activity",
        )

    assert result is None


def test_returns_none_on_unexpected_error() -> None:
    with (
        patch("tourism_pulse_api.pulse.narrative.settings") as mock_settings,
        patch("tourism_pulse_api.pulse.narrative.Groq") as mock_groq_cls,
    ):
        mock_settings.groq_api_key = "fake-key"
        mock_settings.narrative_model = "llama-3.3-70b-versatile"
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("boom")
        mock_groq_cls.return_value = mock_client

        # Must not raise - never breaks the pulse response.
        result = generate_narrative(
            place_name="Budapest",
            pulse=make_pulse_result(),
            evidence=make_evidence(),
            headline="Moderate tourism activity",
        )

    assert result is None


def test_returns_none_when_response_has_no_content() -> None:
    with (
        patch("tourism_pulse_api.pulse.narrative.settings") as mock_settings,
        patch("tourism_pulse_api.pulse.narrative.Groq") as mock_groq_cls,
    ):
        mock_settings.groq_api_key = "fake-key"
        mock_settings.narrative_model = "llama-3.3-70b-versatile"
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _stub_response(None)
        mock_groq_cls.return_value = mock_client

        result = generate_narrative(
            place_name="Budapest",
            pulse=make_pulse_result(),
            evidence=make_evidence(),
            headline="Moderate tourism activity",
        )

    assert result is None
