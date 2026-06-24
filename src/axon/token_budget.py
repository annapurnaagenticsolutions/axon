"""Token budget estimator for AXON Phase 1.

This module provides static token budget estimation for AXON prompt templates.
It estimates token counts from prompt templates and validates @budget annotations
against estimated costs. This is static analysis and does not require runtime
execution or provider calls.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional

from axon.ast_nodes import Annotation, PromptDecl
from axon.validator import Diagnostic, Severity


@dataclass(frozen=True)
class TokenBudget:
    """Token budget information for a prompt."""
    estimated: int
    budget: Optional[int] = None
    within_budget: bool = True
    
    def format(self) -> str:
        """Return a human-readable representation."""
        if self.budget is None:
            return f"estimated: {self.estimated} tokens"
        status = "within budget" if self.within_budget else "exceeds budget"
        return f"estimated: {self.estimated} tokens, budget: {self.budget} tokens ({status})"


# Approximate token counts for common patterns
# These are conservative estimates based on typical tokenization patterns
_TOKEN_ESTIMATION_RULES = {
    # Characters per token approximation (conservative)
    "chars_per_token": 4,
    # Template variable placeholders
    "variable_placeholder": 2,  # {var} ~ 2 tokens
    # Newlines
    "newline": 1,
    # Whitespace
    "whitespace": 1,
}


def estimate_tokens(text: str) -> int:
    """Estimate token count for a text string.
    
    This uses a conservative character-based approximation. For Phase 1,
    this is sufficient for budget validation without requiring actual
    tokenizer integration or provider calls.
    
    Args:
        text: The text to estimate tokens for
        
    Returns:
        Estimated token count
    """
    if not text:
        return 0
    
    # Remove template variable placeholders first (they'll be replaced at runtime)
    # Count them separately
    variable_count = len(re.findall(r"\{[^}]+\}", text))
    text_without_vars = re.sub(r"\{[^}]+\}", "X", text)
    
    # Count characters (conservative estimate: ~4 chars per token)
    char_count = len(text_without_vars)
    text_tokens = char_count // _TOKEN_ESTIMATION_RULES["chars_per_token"]
    
    # Add tokens for variable placeholders
    variable_tokens = variable_count * _TOKEN_ESTIMATION_RULES["variable_placeholder"]
    
    # Add tokens for newlines
    newline_count = text.count("\n")
    newline_tokens = newline_count * _TOKEN_ESTIMATION_RULES["newline"]
    
    total = text_tokens + variable_tokens + newline_tokens
    
    # Ensure at least 1 token for non-empty text
    return max(1, total) if text.strip() else 0


def estimate_prompt_budget(prompt: PromptDecl) -> TokenBudget:
    """Estimate token budget for a prompt declaration.
    
    Args:
        prompt: The prompt declaration to estimate
        
    Returns:
        TokenBudget with estimated count and budget validation
    """
    estimated = estimate_tokens(prompt.template)
    
    # Extract budget from annotations
    budget = None
    for annotation in prompt.annotations:
        if annotation.name == "budget":
            tokens_str = annotation.args.get("tokens")
            if tokens_str:
                try:
                    budget = int(tokens_str)
                except ValueError:
                    pass
    
    within_budget = True
    if budget is not None:
        within_budget = estimated <= budget
    
    return TokenBudget(
        estimated=estimated,
        budget=budget,
        within_budget=within_budget,
    )


def validate_prompt_budgets(prompts: list[PromptDecl]) -> list[Diagnostic]:
    """Validate prompt budgets and return diagnostics.
    
    Args:
        prompts: List of prompt declarations to validate
        
    Returns:
        List of diagnostics for budget violations
    """
    diagnostics: list[Diagnostic] = []
    
    for prompt in prompts:
        budget_info = estimate_prompt_budget(prompt)
        
        if budget_info.budget is not None and not budget_info.within_budget:
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    message=(
                        f"prompt '{prompt.name}' estimated {budget_info.estimated} tokens "
                        f"exceeds @budget(tokens: {budget_info.budget})"
                    ),
                    line=prompt.line,
                    code="exceeds-budget",
                )
            )
    
    return diagnostics


class TokenBudgetEstimator:
    """Token budget estimator for AXON declarations."""
    
    def __init__(self):
        self.diagnostics: list[Diagnostic] = []
    
    def check(self, declarations: list) -> list[Diagnostic]:
        """Run token budget estimation on all declarations and return diagnostics."""
        self.diagnostics = []
        
        prompts = [decl for decl in declarations if isinstance(decl, PromptDecl)]
        self.diagnostics.extend(validate_prompt_budgets(prompts))
        
        return self.diagnostics


def check_token_budgets(declarations: list) -> list[Diagnostic]:
    """Convenience function to check token budgets."""
    estimator = TokenBudgetEstimator()
    return estimator.check(declarations)
