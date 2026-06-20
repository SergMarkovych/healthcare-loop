"""
Few-shot prompting — backend.llm._messages.

Verifies the single worked example is injected as a user/assistant turn before
the real note, that it carries the example content, and that it validates
against the schema (so the example can never drift from the contract).
"""

from backend import llm
from backend.schema import EncounterExtraction


def test_messages_has_four_turns_with_fewshot_roles():
    messages = llm._messages("some real note")

    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]


def test_assistant_turn_carries_the_example():
    messages = llm._messages("some real note")

    assert "Levothyroxine" in messages[2]["content"]


def test_final_user_turn_carries_the_real_note():
    messages = llm._messages("some real note")

    assert "some real note" in messages[3]["content"]


def test_example_json_validates_against_schema():
    messages = llm._messages("some real note")

    extraction = EncounterExtraction.model_validate_json(messages[2]["content"])
    assert extraction.medications[0].drug == "Levothyroxine"
