"""Tests for AXON token budget estimator."""

from axon.parser import parse
from axon.token_budget import (
    TokenBudget,
    estimate_tokens,
    estimate_prompt_budget,
    validate_prompt_budgets,
    check_token_budgets,
)


def test_estimate_tokens_empty():
    assert estimate_tokens("") == 0
    assert estimate_tokens("   ") == 0


def test_estimate_tokens_simple():
    # Simple text, ~4 chars per token
    text = "Hello world"
    # 11 chars / 4 = 2.75 -> 2 tokens (conservative)
    assert estimate_tokens(text) >= 2
    assert estimate_tokens(text) <= 4


def test_estimate_tokens_with_variables():
    # Template variables are counted separately
    text = "Hello {name}, your order {order_id} is ready"
    estimated = estimate_tokens(text)
    # Should account for variables
    assert estimated > 0


def test_estimate_tokens_multiline():
    text = """Line one
Line two
Line three"""
    estimated = estimate_tokens(text)
    # Should account for newlines
    assert estimated > 0


def test_estimate_prompt_budget_no_annotation():
    source = '''
prompt Greet(name: Str) -> Str {
    """
    Hello, {name}!
    """
}
'''
    decls = parse(source)
    prompt = decls[0]
    budget = estimate_prompt_budget(prompt)
    assert budget.budget is None
    assert budget.estimated > 0
    assert budget.within_budget is True


def test_estimate_prompt_budget_with_annotation():
    source = '''
prompt Greet(name: Str, @budget(tokens: 100)) -> Str {
    """
    Hello, {name}!
    """
}
'''
    decls = parse(source)
    prompt = decls[0]
    budget = estimate_prompt_budget(prompt)
    assert budget.budget == 100
    assert budget.estimated > 0
    assert budget.within_budget is True


def test_estimate_prompt_budget_exceeds():
    source = '''
prompt LongPrompt(name: Str, @budget(tokens: 5)) -> Str {
    """
    This is a very long prompt that definitely exceeds the tiny budget of 5 tokens.
    It has multiple sentences and lots of content.
    """
}
'''
    decls = parse(source)
    prompt = decls[0]
    budget = estimate_prompt_budget(prompt)
    assert budget.budget == 5
    assert budget.estimated > 5
    assert budget.within_budget is False


def test_validate_prompt_budgets_no_violations():
    source = '''
prompt Greet(name: Str, @budget(tokens: 100)) -> Str {
    """
    Hello, {name}!
    """
}
'''
    decls = parse(source)
    prompts = [d for d in decls if hasattr(d, 'template')]
    diagnostics = validate_prompt_budgets(prompts)
    assert len(diagnostics) == 0


def test_validate_prompt_budgets_with_violations():
    source = '''
prompt LongPrompt(name: Str, @budget(tokens: 5)) -> Str {
    """
    This is a very long prompt that definitely exceeds the tiny budget of 5 tokens.
    """
}
'''
    decls = parse(source)
    prompts = [d for d in decls if hasattr(d, 'template')]
    diagnostics = validate_prompt_budgets(prompts)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "exceeds-budget"
    assert diagnostics[0].severity == "warning"


def test_check_token_budgets():
    source = '''
prompt Greet(name: Str, @budget(tokens: 100)) -> Str {
    """
    Hello, {name}!
    """
}

prompt LongPrompt(name: Str, @budget(tokens: 5)) -> Str {
    """
    This is a very long prompt that definitely exceeds the tiny budget of 5 tokens.
    """
}
'''
    decls = parse(source)
    diagnostics = check_token_budgets(decls)
    # Should have one warning for the budget violation
    warnings = [d for d in diagnostics if d.severity == "warning"]
    assert len(warnings) == 1
    assert warnings[0].code == "exceeds-budget"


def test_token_budget_format():
    budget = TokenBudget(estimated=50, budget=100, within_budget=True)
    formatted = budget.format()
    assert "50" in formatted
    assert "100" in formatted
    assert "within budget" in formatted
    
    budget_exceeds = TokenBudget(estimated=150, budget=100, within_budget=False)
    formatted_exceeds = budget_exceeds.format()
    assert "150" in formatted_exceeds
    assert "100" in formatted_exceeds
    assert "exceeds budget" in formatted_exceeds


def test_estimate_tokens_conservative():
    # Test that estimation is conservative (not too low)
    long_text = "A" * 100
    estimated = estimate_tokens(long_text)
    # 100 chars / 4 = 25 tokens minimum
    assert estimated >= 20


def test_estimate_prompt_budget_multiple_prompts():
    source = '''
prompt P1(name: Str, @budget(tokens: 50)) -> Str {
    """
    Hello, {name}!
    """
}

prompt P2(text: Str, @budget(tokens: 200)) -> Str {
    """
    Process this text: {text}
    """
}
'''
    decls = parse(source)
    prompts = [d for d in decls if hasattr(d, 'template')]
    assert len(prompts) == 2
    
    for prompt in prompts:
        budget = estimate_prompt_budget(prompt)
        assert budget.estimated > 0
        assert budget.budget is not None
