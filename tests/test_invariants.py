"""Studio Golden Invariant Evaluations for FastUp.

Evaluates critical business, legal, and operational invariants offline in <1s.
Protects against regressions during prompt, skill, or architectural refactoring:
1. Article 33 (ст. 33 НК РБ) employment substitution stop-words.
2. Belarus IP income tax (20%) and standard 20% deduction computation rules.
3. Pricing model invariance: all prices must strictly begin with 'от N BYN'.
4. Tool Envelope and Escalation contracts.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Tuple

import pytest

# Add scripts directory to path
REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from tool_envelope import (
    EXIT_NON_RETRYABLE,
    EXIT_RETRYABLE,
    EXIT_SUCCESS,
    ToolEnvelope,
    envelope_error,
    envelope_success,
    run_enveloped,
)
from escalate import format_escalation_card

# Prohibited labor relationship terms per Article 33 Tax Code of Belarus
ARTICLE_33_STOP_PATTERNS = [
    r"\bоклад(?:а|у|ом|е)?\b",
    r"\bзарплат(?:а|ы|е|у|ой|е)?\b",
    r"\bзаработная\s+плата\b",
    r"\bтарифн(?:ая|ой|ую)\s+ставк(?:а|и|е|у|ой)?\b",
    r"\bпреми(?:я|и|ю|ей|е)?\b",
    r"\bпремировани(?:е|я|ю|ем|и)?\b",
    r"\bрабоч(?:ий|его|ему|им|ем)\s+день\b",
    r"\bрабоч(?:ее|его|ему|им|ем)\s+врем(?:я|ени|енем)\b",
    r"\bграфик(?:\s+работ(?:ы|а))?\b",
    r"\bотпуск(?:а|у|ом|е)?\b",
    r"\bбольничн(?:ый|ого|ому|ым|ом)?\b",
    r"\bштатн(?:ое|ого|ому|ым|ом)?\s+расписани(?:е|я|ю|ем|и)\b",
    r"\bдолжност(?:ь|и|ью)?\b",
    r"\bиспытательн(?:ый|ого|ому|ым|ом)\s+срок(?:а|у|ом|е)?\b",
]


def audit_article_33_compliance(text: str) -> Tuple[bool, List[str]]:
    """Scan text for Article 33 stop-words. Returns (is_compliant, violations)."""
    violations = []
    lower_text = text.lower()
    for pattern in ARTICLE_33_STOP_PATTERNS:
        match = re.search(pattern, lower_text, re.IGNORECASE)
        if match:
            violations.append(match.group(0))
    return len(violations) == 0, violations


def compute_ip_income_tax(
    revenue: float,
    expenses: float = 0.0,
    use_standard_deduction: bool = False,
) -> dict:
    """Deterministic Belarus IP income tax calculator (подоходный налог 20%).

    Art. 205 Tax Code of Belarus:
    - Standard deduction option: 20% of revenue without documentary confirmation.
    - Statutory threshold: 500,000 BYN cumulative gross revenue triggers 30% rate warning.
    """
    if revenue < 0 or expenses < 0:
        raise ValueError("Revenue and expenses cannot be negative")

    if use_standard_deduction:
        deduction = revenue * 0.20
    else:
        deduction = expenses

    tax_base = max(0.0, revenue - deduction)
    tax_amount = round(tax_base * 0.20, 2)
    threshold_exceeded = revenue >= 500000.0

    return {
        "revenue": revenue,
        "deduction": deduction,
        "tax_base": tax_base,
        "tax_amount": tax_amount,
        "threshold_500k_exceeded": threshold_exceeded,
    }


# ============================================================================
# 1. Article 33 Legal Cleanliness Tests
# ============================================================================
class TestArticle33Compliance:
    def test_forbidden_terms_fail(self):
        prohibited_samples = [
            "Ежемесячный оклад сотрудника составляет 1200 BYN.",
            "Начислена премия за выполнение плана продаж.",
            "Оплата труда производится по тарифной ставке.",
            "Подрядчик обязуется соблюдать график работы с 9:00 до 18:00.",
            "Предоставляется оплачиваемый отпуск на 14 календарных дней.",
            "Исполнитель назначается на должность контент-менеджера.",
            "Испытательный срок составляет 1 месяц.",
        ]
        for sample in prohibited_samples:
            compliant, violations = audit_article_33_compliance(sample)
            assert not compliant, f"Expected violation in: '{sample}', got passed"
            assert len(violations) > 0

    def test_compliant_contractor_terms_pass(self):
        compliant_samples = [
            "Базовое вознаграждение за комплекс услуг по администрированию CRM за период 10.09–25.09 — 600,00 BYN.",
            "Оплата за результат валидации лидов (15 лидов по 5,00 BYN) — 75,00 BYN.",
            "Абонентская плата за информационное взаимодействие и сопровождение клиентской базы — 400,00 BYN.",
            "Дополнительное вознаграждение за успешное сопровождение сделки Клиент ООО «Тест» — 300,00 BYN.",
            "Услуги оказаны в полном объёме, в установленные сроки и с надлежащим качеством.",
        ]
        for sample in compliant_samples:
            compliant, violations = audit_article_33_compliance(sample)
            assert compliant, f"Expected compliant, but found violations: {violations}"


# ============================================================================
# 2. Tax Computation Invariants
# ============================================================================
class TestTaxInvariants:
    def test_standard_deduction_tax_rate(self):
        # With standard 20% deduction: Tax base = 10,000 * 0.80 = 8,000. Tax = 8,000 * 0.20 = 1,600.
        calc = compute_ip_income_tax(revenue=10000.0, use_standard_deduction=True)
        assert calc["deduction"] == 2000.0
        assert calc["tax_base"] == 8000.0
        assert calc["tax_amount"] == 1600.0
        assert not calc["threshold_500k_exceeded"]

    def test_actual_expenses_tax_rate(self):
        # Revenue 10,000, actual documented expenses 3,000. Tax base = 7,000. Tax = 1,400.
        calc = compute_ip_income_tax(revenue=10000.0, expenses=3000.0, use_standard_deduction=False)
        assert calc["tax_base"] == 7000.0
        assert calc["tax_amount"] == 1400.0

    def test_expenses_exceeding_revenue(self):
        # Tax base cannot be negative.
        calc = compute_ip_income_tax(revenue=5000.0, expenses=7000.0)
        assert calc["tax_base"] == 0.0
        assert calc["tax_amount"] == 0.0

    def test_threshold_500k_warning(self):
        calc_under = compute_ip_income_tax(revenue=499999.0)
        assert not calc_under["threshold_500k_exceeded"]

        calc_over = compute_ip_income_tax(revenue=500001.0)
        assert calc_over["threshold_500k_exceeded"]

    def test_negative_values_raise_error(self):
        with pytest.raises(ValueError):
            compute_ip_income_tax(revenue=-100.0)


# ============================================================================
# 3. Positioning & Facts Price Invariants
# ============================================================================
class TestPriceInvariants:
    def test_facts_file_pricing_strictly_prefixed_with_from(self):
        facts_path = REPO_ROOT / "positioning" / "facts.md"
        if not facts_path.exists():
            agents_md = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
            readme_md = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
            assert 'Pricing is strictly formatted as "от N BYN"' in agents_md
            assert '"от N BYN"' in readme_md
            return

        content = facts_path.read_text(encoding="utf-8")

        # Invariant 1: Explicit rule in facts.md
        assert "Цена всегда в форме «от N BYN»" in content

        # Invariant 2: Check standard price definitions in facts.md
        required_price_patterns = [
            r"лендинг\s+от\s+1\s*100",
            r"корпоративный\s+от\s+1\s*800",
            r"магазин\s+от\s+3\s*000",
            r"контекст\s+от\s+700",
            r"SEO\s+(?:первый\s+месяц\s+)?от\s+1\s*000",
            r"дизайн\s+от\s+450",
        ]
        for pat in required_price_patterns:
            assert re.search(pat, content, re.IGNORECASE), f"Missing required price pattern: {pat}"


# ============================================================================
# 4. Tool Envelope & Escalation Contract Tests
# ============================================================================
class TestToolEnvelopeAndEscalation:
    def test_success_envelope(self):
        env = envelope_success("demo_tool", {"count": 42}, duration_ms=15)
        d = env.to_dict()
        assert d["status"] == "success"
        assert d["tool"] == "demo_tool"
        assert d["duration_ms"] == 15
        assert d["data"] == {"count": 42}
        assert "error" not in d

    def test_error_envelope(self):
        env = envelope_error(
            tool="demo_tool",
            code="NETWORK_TIMEOUT",
            message="Connection dropped",
            retryable=True,
            duration_ms=250,
        )
        d = env.to_dict()
        assert d["status"] == "error"
        assert d["tool"] == "demo_tool"
        assert d["error"]["code"] == "NETWORK_TIMEOUT"
        assert d["error"]["retryable"] is True

    def test_run_enveloped_success(self):
        env = run_enveloped("calc", lambda a, b: a + b, 10, 20)
        assert env.status == "success"
        assert env.data == 30
        assert env.duration_ms >= 0

    def test_run_enveloped_exception(self):
        def buggy():
            raise ConnectionResetError("Remote server closed connection")

        env = run_enveloped("buggy_tool", buggy)
        assert env.status == "error"
        assert env.error is not None
        assert env.error.code == "ConnectionResetError"
        assert env.error.retryable is True  # OSError/ConnectionError is marked retryable

    def test_escalation_card_formatting(self):
        card = format_escalation_card(
            task="SEO Audit",
            error="Connection timed out",
            hypothesis="Firewall dropped requests",
            action="Check IP whitelist",
            context={"slug": "client-test"},
            timestamp="2026-09-19 12:00:00",
        )
        assert "FASTUP ESCALATION INCIDENT" in card
        assert "SEO Audit" in card
        assert "Connection timed out" in card
        assert "Firewall dropped requests" in card
        assert "Check IP whitelist" in card
        assert "client-test" in card
