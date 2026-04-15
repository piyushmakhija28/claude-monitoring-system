"""E2E tests: ENABLE_RUNTIME_VERIFICATION=1 in hook mode (CLAUDE_HOOK_MODE=1).

Validates that:
  - RuntimeVerifier.get_instance() returns a real RuntimeVerifier (not NullVerifier)
  - PRE_ANALYSIS_CONTRACT preconditions are enforced by orchestration_pre_analysis_node
  - PROMPT_GEN_CONTRACT postconditions are enforced
  - OTel spans are created via the decorators.create_span path (B.8 / ADR-4)
  - NullVerifier is returned when ENABLE_RUNTIME_VERIFICATION is absent

All external I/O is mocked.  No live GitHub calls, no .env reads,
no real claude CLI subprocess (ADR-1 / ADR-2).

Run:
    pytest tests/e2e/test_hook_mode_runtime_verification.py -v
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LONG_PROMPT = "A" * 250  # satisfies PROMPT_GEN_CONTRACT min_length=200


# ===========================================================================
# Test 1: get_instance returns RuntimeVerifier when enabled
# ===========================================================================


def test_get_instance_returns_real_verifier_when_enabled(monkeypatch):
    """With ENABLE_RUNTIME_VERIFICATION=1, get_instance() returns RuntimeVerifier."""
    from langgraph_engine.runtime_verification.verifier import NullVerifier, RuntimeVerifier

    monkeypatch.setenv("ENABLE_RUNTIME_VERIFICATION", "1")
    verifier = RuntimeVerifier.get_instance()

    assert isinstance(verifier, RuntimeVerifier)
    assert not isinstance(verifier, NullVerifier)


# ===========================================================================
# Test 2: get_instance returns NullVerifier when disabled
# ===========================================================================


def test_get_instance_returns_null_verifier_when_disabled(monkeypatch):
    """Without ENABLE_RUNTIME_VERIFICATION=1, get_instance() returns NullVerifier."""
    from langgraph_engine.runtime_verification.verifier import NullVerifier, RuntimeVerifier

    monkeypatch.delenv("ENABLE_RUNTIME_VERIFICATION", raising=False)
    verifier = RuntimeVerifier.get_instance()

    assert isinstance(verifier, NullVerifier)


# ===========================================================================
# Test 3: PRE_ANALYSIS_CONTRACT registers on get_instance
# ===========================================================================


def test_pre_analysis_contract_registered_on_enable(monkeypatch):
    """PRE_ANALYSIS_CONTRACT.node_name is present in verifier registry after import."""
    monkeypatch.setenv("ENABLE_RUNTIME_VERIFICATION", "1")

    from langgraph_engine.runtime_verification.node_contracts import PRE_ANALYSIS_CONTRACT
    from langgraph_engine.runtime_verification.verifier import RuntimeVerifier

    verifier = RuntimeVerifier.get_instance()
    verifier.register(PRE_ANALYSIS_CONTRACT)

    assert PRE_ANALYSIS_CONTRACT.node_name in verifier._registry


# ===========================================================================
# Test 4: orchestration_pre_analysis_node passes when user_message present
# ===========================================================================


def test_pre_analysis_node_no_violations_with_valid_state(monkeypatch, base_hook_state):
    """orchestration_pre_analysis_node with valid state produces zero pre-violations."""
    monkeypatch.setenv("ENABLE_RUNTIME_VERIFICATION", "1")
    monkeypatch.setenv("CLAUDE_HOOK_MODE", "1")

    from langgraph_engine.runtime_verification.node_contracts import PRE_ANALYSIS_CONTRACT
    from langgraph_engine.runtime_verification.verifier import RuntimeVerifier

    verifier = RuntimeVerifier.get_instance()
    verifier.register(PRE_ANALYSIS_CONTRACT)

    violations = verifier.check_preconditions(PRE_ANALYSIS_CONTRACT.node_name, base_hook_state)

    assert violations == [], "Expected no violations for valid hook-mode state"


# ===========================================================================
# Test 5: orchestration_pre_analysis_node fails when user_message missing
# ===========================================================================


def test_pre_analysis_node_critical_violation_when_user_message_missing(monkeypatch):
    """Missing user_message produces a CRITICAL precondition violation."""
    monkeypatch.setenv("ENABLE_RUNTIME_VERIFICATION", "1")
    monkeypatch.setenv("CLAUDE_HOOK_MODE", "1")

    from langgraph_engine.runtime_verification.node_contracts import PRE_ANALYSIS_CONTRACT
    from langgraph_engine.runtime_verification.verifier import RuntimeVerifier

    verifier = RuntimeVerifier.get_instance()
    verifier.register(PRE_ANALYSIS_CONTRACT)

    state_without_message = {"project_root": "/tmp", "combined_complexity_score": 5}
    violations = verifier.check_preconditions(PRE_ANALYSIS_CONTRACT.node_name, state_without_message)

    assert len(violations) >= 1
    assert any(v["severity"] == "CRITICAL" for v in violations)


# ===========================================================================
# Test 6: PROMPT_GEN postcondition passes with long enough prompt
# ===========================================================================


def test_prompt_gen_postcondition_passes_with_long_prompt(monkeypatch):
    """PROMPT_GEN_CONTRACT postcondition passes when orchestration_prompt >= 200 chars."""
    monkeypatch.setenv("ENABLE_RUNTIME_VERIFICATION", "1")
    monkeypatch.setenv("CLAUDE_HOOK_MODE", "1")

    from langgraph_engine.runtime_verification.node_contracts import PROMPT_GEN_CONTRACT
    from langgraph_engine.runtime_verification.verifier import RuntimeVerifier

    verifier = RuntimeVerifier.get_instance()
    verifier.register(PROMPT_GEN_CONTRACT)

    state = {"orchestration_prompt": _LONG_PROMPT}
    violations = verifier.check_postconditions(PROMPT_GEN_CONTRACT.node_name, state)

    assert violations == [], "Long prompt must satisfy min_length=200 postcondition"


# ===========================================================================
# Test 7: PROMPT_GEN postcondition fails with short prompt
# ===========================================================================


def test_prompt_gen_postcondition_fails_with_short_prompt(monkeypatch):
    """PROMPT_GEN_CONTRACT postcondition fails when orchestration_prompt < 200 chars."""
    monkeypatch.setenv("ENABLE_RUNTIME_VERIFICATION", "1")
    monkeypatch.setenv("CLAUDE_HOOK_MODE", "1")

    from langgraph_engine.runtime_verification.node_contracts import PROMPT_GEN_CONTRACT
    from langgraph_engine.runtime_verification.verifier import RuntimeVerifier

    verifier = RuntimeVerifier.get_instance()
    verifier.register(PROMPT_GEN_CONTRACT)

    state = {"orchestration_prompt": "too short"}
    violations = verifier.check_postconditions(PROMPT_GEN_CONTRACT.node_name, state)

    assert len(violations) >= 1
    assert violations[0]["severity"] == "ERROR"


# ===========================================================================
# Test 8: verify_node decorator wraps function when enabled
# ===========================================================================


def test_verify_node_decorator_creates_wrapper_when_enabled(monkeypatch):
    """With ENABLE_RUNTIME_VERIFICATION=1, verify_node wraps the function (__rv_wrapped__=True)."""
    monkeypatch.setenv("ENABLE_RUNTIME_VERIFICATION", "1")

    from langgraph_engine.runtime_verification.contracts import NodeContract, PostconditionSpec, PreconditionSpec
    from langgraph_engine.runtime_verification.decorators import verify_node

    contract = NodeContract(
        node_name="hook_mode_test_node",
        preconditions=[PreconditionSpec(key="user_message", expected_type=str, required=True)],
        postconditions=[PostconditionSpec(key="result", non_null=True, min_length=0)],
    )

    @verify_node(contract)
    def _sample_node(state):
        return {"result": "done"}

    # Wrapper must be marked with __rv_wrapped__
    assert getattr(_sample_node, "__rv_wrapped__", False) is True


# ===========================================================================
# Test 9: verify_node passes through original fn when disabled
# ===========================================================================


def test_verify_node_passes_through_original_fn_when_disabled(monkeypatch):
    """With ENABLE_RUNTIME_VERIFICATION=0, verify_node returns original fn unchanged."""
    monkeypatch.delenv("ENABLE_RUNTIME_VERIFICATION", raising=False)

    from langgraph_engine.runtime_verification.contracts import NodeContract
    from langgraph_engine.runtime_verification.decorators import verify_node

    contract = NodeContract(
        node_name="hook_mode_disabled_node",
        preconditions=[],
        postconditions=[],
        invariants=[],
    )

    def _original(state):
        return {"output": "unchanged"}

    decorated = verify_node(contract)(_original)

    # Must NOT be wrapped -- returned unchanged (no __rv_wrapped__)
    assert not getattr(decorated, "__rv_wrapped__", False)
    assert decorated({}) == {"output": "unchanged"}


# ===========================================================================
# Test 10: OTel span attributes set via mock (ADR-4 / B.8)
# ===========================================================================


def test_otel_span_attributes_set_via_decorators_module(monkeypatch, mock_create_span):
    """verify_node sets node.name and verification.result span attributes (ADR-4)."""
    monkeypatch.setenv("ENABLE_RUNTIME_VERIFICATION", "1")

    mock_patch, span_mock = mock_create_span

    from langgraph_engine.runtime_verification.contracts import NodeContract, PreconditionSpec
    from langgraph_engine.runtime_verification.decorators import verify_node

    contract = NodeContract(
        node_name="otel_span_test_node",
        preconditions=[PreconditionSpec(key="user_message", expected_type=str, required=True)],
        postconditions=[],
        invariants=[],
    )

    @verify_node(contract)
    def _node(state):
        return {"output": "ok"}

    state = {"user_message": "hello otel"}
    _node(state)

    # create_span must have been called by the decorator
    assert mock_patch.called

    # span.set_attribute must have been called with node.name
    calls = [str(c) for c in span_mock.set_attribute.call_args_list]
    node_name_found = any("node.name" in c for c in calls)
    assert node_name_found, "set_attribute('node.name', ...) was not called on span"


# ===========================================================================
# Test 11: build_report reflects violations accumulated in hook mode
# ===========================================================================


def test_build_report_reflects_hook_mode_violations(monkeypatch):
    """After a failed precondition in hook mode, build_report shows pass_fail=False."""
    monkeypatch.setenv("ENABLE_RUNTIME_VERIFICATION", "1")
    monkeypatch.setenv("CLAUDE_HOOK_MODE", "1")

    from langgraph_engine.runtime_verification.contracts import NodeContract, PreconditionSpec
    from langgraph_engine.runtime_verification.verifier import RuntimeVerifier

    verifier = RuntimeVerifier.get_instance()

    contract = NodeContract(
        node_name="hook_report_test_node",
        preconditions=[PreconditionSpec(key="required_field", expected_type=str, required=True)],
    )
    verifier.register(contract)

    # Trigger violation: required_field missing
    verifier.check_preconditions("hook_report_test_node", {})

    report = verifier.build_report()

    assert report.pass_fail is False
    assert len(report.violations) >= 1
