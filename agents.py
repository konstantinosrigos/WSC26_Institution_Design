"""Carrier agent definitions for the Mesa + norms-games prototype."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from mesa import Agent

ACTIONS: tuple[str, str, str] = ("take_other", "give_own", "refuse")


@dataclass
class AgentRoundRecord:
    round_index: int
    action: str
    outcome: str
    payoff: float
    trust_after: float
    applied_profile: Tuple[str, str]


class CarrierAgent(Agent):
    """Carrier in the IAD action situation repeated over Mesa rounds."""

    def __init__(
        self,
        unique_id: int,
        model: Any,
        label: str,
        trust: float = 0.45,
        risk: float = 0.25,
        risk_weight: float = 1.0,
    ) -> None:
        try:
            super().__init__(model)
        except TypeError:
            super().__init__(unique_id, model)
        self.label = label
        self.trust = trust
        self.risk = risk
        self.risk_weight = risk_weight
        self.cash = 0.0
        self.success_count = 0
        self.failure_count = 0
        self.history: List[AgentRoundRecord] = []

    def _belief_over_other_actions(self) -> Dict[str, float]:
        # Information rule assumption: agents know payoff structure and use trust
        # as belief about cooperative intent in the next action situation.
        cooperative_mass = max(0.2, min(0.85, 0.25 + 0.55 * self.trust))
        p_take = 0.6 * cooperative_mass
        p_give = 0.4 * cooperative_mass
        p_refuse = max(0.0, 1.0 - cooperative_mass)
        total = p_take + p_give + p_refuse
        return {
            "take_other": p_take / total,
            "give_own": p_give / total,
            "refuse": p_refuse / total,
        }

    def _coordination_upside(self, opportunity: Any) -> float:
        if self.label == "a":
            best_collab = max(
                float(opportunity.payoff_if_a_executes_both),
                float(opportunity.payoff_to_a_if_b_executes),
            )
            status_quo = float(opportunity.status_quo_a)
        else:
            best_collab = max(
                float(opportunity.payoff_if_b_executes_both),
                float(opportunity.payoff_to_b_if_a_executes),
            )
            status_quo = float(opportunity.status_quo_b)
        return max(0.0, best_collab - status_quo)

    def _sample_action(
        self,
        scores: Dict[str, float],
        temperature: float = 0.45,
        epsilon: float = 0.08,
    ) -> str:
        actions = list(scores.keys())
        if not actions:
            return "refuse"

        if self.model.random.random() < epsilon:
            return self.model.random.choice(actions)

        max_score = max(scores.values())
        exps = {
            action: math.exp((score - max_score) / max(temperature, 1e-6))
            for action, score in scores.items()
        }
        total = sum(exps.values())
        draw = self.model.random.random()
        cumulative = 0.0
        for action in actions:
            cumulative += exps[action] / total
            if draw <= cumulative:
                return action
        return actions[-1]

    def choose_action(self, opportunity: Any, adapter: Any) -> str:
        beliefs = self._belief_over_other_actions()
        scores: Dict[str, float] = {}
        feasible_actions = list(ACTIONS)
        if self.label == "a" and not opportunity.a_can_take:
            feasible_actions.remove("take_other")
        if self.label == "b" and not opportunity.b_can_take:
            feasible_actions.remove("take_other")
        upside = self._coordination_upside(opportunity)

        for my_action in feasible_actions:
            expected = 0.0
            for other_action, prob in beliefs.items():
                if self.label == "a":
                    resolution = adapter.resolve_round(opportunity, my_action, other_action)
                    my_payoff = resolution.payoffs["a"]
                else:
                    resolution = adapter.resolve_round(opportunity, other_action, my_action)
                    my_payoff = resolution.payoffs["b"]
                expected += prob * my_payoff

            if my_action == "take_other":
                expected -= 0.35 * self.risk * self.risk_weight
            elif my_action == "give_own":
                expected -= 0.18 * self.risk * self.risk_weight

            if my_action == "refuse":
                # Option value of not walking away from a potentially beneficial match.
                expected -= upside * (0.07 + 0.08 * self.trust)
            else:
                expected += upside * (0.03 + 0.10 * self.trust)
                expected += 0.15 * self.trust
            scores[my_action] = expected

        return self._sample_action(scores)

    def register_round(
        self,
        round_index: int,
        action: str,
        outcome: str,
        payoff: float,
        applied_profile: Tuple[str, str],
    ) -> None:
        self.history.append(
            AgentRoundRecord(
                round_index=round_index,
                action=action,
                outcome=outcome,
                payoff=payoff,
                trust_after=self.trust,
                applied_profile=applied_profile,
            )
        )
