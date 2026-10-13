"""Mesa model for repeated logistics exchange opportunities."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, List

from mesa import Model
from mesa.datacollection import DataCollector

from adapter import NormsGamesAdapter
from agents import CarrierAgent
from institutions import RegimeName, get_institution_spec
from opportunities import ExchangeOpportunity, OpportunityGenerator


@dataclass
class RoundRecord:
    round_index: int
    actions: Dict[str, str]
    applied_profile: tuple[str, str]
    outcome: str
    welfare: float
    status_quo_welfare: float
    net_gain_over_status_quo: float
    realized_collaboration_surplus: float
    failure_type: str
    cumulative_joint_welfare: float
    cumulative_status_quo_welfare: float
    cumulative_net_gain_over_status_quo: float
    cumulative_realized_collaboration_surplus: float
    payoffs: Dict[str, float]
    opportunity: Dict[str, float]


class LogisticsCollaborationModel(Model):
    """Mesa layer for repeated play over one-round IAD action situations."""

    def __init__(
        self,
        institution: RegimeName = "baseline",
        n_rounds: int = 100,
        seed: int | None = None,
        initial_trust: float = 0.45,
        risk_a: float = 0.25,
        risk_b: float = 0.25,
        risk_weight: float = 3.0,
    ) -> None:
        try:
            super().__init__(rng=seed)
        except TypeError:
            try:
                super().__init__(seed=seed)
            except TypeError:
                super().__init__()
                self.random = random.Random(seed)
        if not hasattr(self, "random"):
            self.random = random.Random(seed)

        self.institution_name = institution
        self.spec = get_institution_spec(institution)
        self.n_rounds = n_rounds
        self.current_round = 0

        # IAD scope-tracking state over repeated interactions.
        self.collaboration_count = 0
        self.total_welfare = 0.0
        self.last_outcome = "none"
        self.last_welfare = 0.0
        self.cooperative_welfare = 0.0
        self.last_utility_a = 0.0
        self.last_utility_b = 0.0
        self.last_status_quo_welfare = 0.0
        self.last_net_gain_over_status_quo = 0.0
        self.last_realized_collaboration_surplus = 0.0
        self.last_failure_type = "none"
        self.cooperative_cash_a = 0.0
        self.cooperative_cash_b = 0.0
        self.cumulative_joint_welfare = 0.0
        self.cumulative_status_quo_welfare = 0.0
        self.cumulative_net_gain_over_status_quo = 0.0
        self.cumulative_realized_collaboration_surplus = 0.0
        self.mutual_refusal_count = 0
        self.one_refusal_failure_count = 0
        self.mismatch_failure_count = 0
        self.other_failure_count = 0
        self.last_actions = {"a": "none", "b": "none"}
        self.history: List[RoundRecord] = []

        self.adapter = NormsGamesAdapter(self.spec, seed=seed)
        self.opportunity_generator = OpportunityGenerator(
            seed=seed,
            status_quo_min=self.spec.status_quo_min,
            status_quo_max=self.spec.status_quo_max,
            giver_disutility_min=self.spec.giver_disutility_min,
            giver_disutility_max=self.spec.giver_disutility_max,
            surplus_if_a_executes_min=self.spec.surplus_if_a_executes_min,
            surplus_if_a_executes_max=self.spec.surplus_if_a_executes_max,
            surplus_if_b_executes_min=self.spec.surplus_if_b_executes_min,
            surplus_if_b_executes_max=self.spec.surplus_if_b_executes_max,
            can_take_probability=self.spec.can_take_probability,
            executor_share_min=(
                self.spec.executor_share_min
                if self.spec.executor_share_min is not None
                else 0.68
            ),
            executor_share_max=(
                self.spec.executor_share_max
                if self.spec.executor_share_max is not None
                else 0.78
            ),
        )

        self.carrier_a = CarrierAgent(
            unique_id=0,
            model=self,
            label="a",
            trust=initial_trust,
            risk=risk_a,
            risk_weight=risk_weight,
        )
        self.carrier_b = CarrierAgent(
            unique_id=1,
            model=self,
            label="b",
            trust=initial_trust,
            risk=risk_b,
            risk_weight=risk_weight,
        )

        self.datacollector = DataCollector(
            model_reporters={
                "institution": lambda m: m.institution_name,
                "round": lambda m: m.current_round,
                "collaboration_count": lambda m: m.collaboration_count,
                "collaboration_rate": lambda m: (
                    m.collaboration_count / m.current_round if m.current_round else 0.0
                ),
                "trust_a": lambda m: m.carrier_a.trust,
                "trust_b": lambda m: m.carrier_b.trust,
                "cash_a": lambda m: m.carrier_a.cash,
                "cash_b": lambda m: m.carrier_b.cash,
                "last_outcome": lambda m: m.last_outcome,
                "last_welfare": lambda m: m.last_welfare,
                "cooperative_welfare": lambda m: m.cooperative_welfare,
                "last_utility_a": lambda m: m.last_utility_a,
                "last_utility_b": lambda m: m.last_utility_b,
                "cooperative_cash_a": lambda m: m.cooperative_cash_a,
                "cooperative_cash_b": lambda m: m.cooperative_cash_b,
                "last_status_quo_welfare": lambda m: m.last_status_quo_welfare,
                "last_net_gain_over_status_quo": lambda m: m.last_net_gain_over_status_quo,
                "last_realized_collaboration_surplus": lambda m: m.last_realized_collaboration_surplus,
                "last_failure_type": lambda m: m.last_failure_type,
                "cumulative_joint_welfare": lambda m: m.cumulative_joint_welfare,
                "cumulative_status_quo_welfare": lambda m: m.cumulative_status_quo_welfare,
                "cumulative_net_gain_over_status_quo": lambda m: m.cumulative_net_gain_over_status_quo,
                "cumulative_realized_collaboration_surplus": lambda m: m.cumulative_realized_collaboration_surplus,
                "mutual_refusal_count": lambda m: m.mutual_refusal_count,
                "one_refusal_failure_count": lambda m: m.one_refusal_failure_count,
                "mismatch_failure_count": lambda m: m.mismatch_failure_count,
                "other_failure_count": lambda m: m.other_failure_count,
            }
        )
        self.running = True

    def _counterfactual_cooperative_welfare(self, opportunity: ExchangeOpportunity) -> float:
        return self.adapter.cooperative_welfare_upper_bound(opportunity)

    def _counterfactual_cooperative_payoffs(
        self,
        opportunity: ExchangeOpportunity,
    ) -> Dict[str, float]:
        return self.adapter.cooperative_payoffs_upper_bound(opportunity)

    @staticmethod
    def _clamp_trust(value: float) -> float:
        return min(1.0, max(0.0, value))

    def _update_agent_trust(
        self,
        agent: CarrierAgent,
        own_action: str,
        other_action: str,
        collaboration: bool,
        failure_type: str | None = None,
    ) -> None:
        # Kept for forward compatibility: trust behavior is unchanged by default.
        _ = failure_type
        own_attempted = own_action != "refuse"
        other_attempted = other_action != "refuse"

        if collaboration:
            if own_attempted:
                agent.success_count += 1
            # Trust represents belief in the counterpart's willingness to coordinate.
            delta = 0.045 if other_attempted else 0.015
            agent.trust = self._clamp_trust(agent.trust + delta)
            return

        if own_attempted:
            agent.failure_count += 1

        if failure_type == "mismatch_failure" and own_attempted and other_attempted:
            # Mismatch failures are stronger negative evidence than refusal failures.
            delta = -0.045
        elif failure_type == "one_refusal_failure":
            if own_attempted and not other_attempted:
                # Counterpart refused while this agent attempted to coordinate.
                delta = -0.03
            elif not own_attempted and other_attempted:
                # Counterpart attempted despite this agent refusing.
                delta = 0.004
            else:
                delta = -0.015
        elif own_attempted and other_attempted:
            delta = -0.02
        elif own_attempted and not other_attempted:
            delta = -0.045
        elif not own_attempted and other_attempted:
            delta = 0.006
        else:
            # Very slow recovery when both keep status quo.
            delta = 0.005

        agent.trust = self._clamp_trust(agent.trust + delta)

    def _update_trust_and_counts(
        self,
        action_a: str,
        action_b: str,
        collaboration: bool,
        failure_type: str | None = None,
    ) -> None:
        self._update_agent_trust(
            agent=self.carrier_a,
            own_action=action_a,
            other_action=action_b,
            collaboration=collaboration,
            failure_type=failure_type,
        )
        self._update_agent_trust(
            agent=self.carrier_b,
            own_action=action_b,
            other_action=action_a,
            collaboration=collaboration,
            failure_type=failure_type,
        )

    def _update_failure_type_counts(self, failure_type: str) -> None:
        if failure_type == "mutual_refusal":
            self.mutual_refusal_count += 1
            return
        if failure_type == "one_refusal_failure":
            self.one_refusal_failure_count += 1
            return
        if failure_type == "mismatch_failure":
            self.mismatch_failure_count += 1
            return
        if failure_type == "other_failure":
            self.other_failure_count += 1

    def _record_round(
        self,
        opportunity: ExchangeOpportunity,
        action_a: str,
        action_b: str,
        resolution: Any,
    ) -> None:
        self.history.append(
            RoundRecord(
                round_index=self.current_round,
                actions={"a": action_a, "b": action_b},
                applied_profile=resolution.applied_profile,
                outcome=resolution.outcome,
                welfare=resolution.welfare,
                status_quo_welfare=resolution.status_quo_welfare,
                net_gain_over_status_quo=resolution.net_gain_over_status_quo,
                realized_collaboration_surplus=resolution.realized_collaboration_surplus,
                failure_type=resolution.failure_type,
                cumulative_joint_welfare=self.cumulative_joint_welfare,
                cumulative_status_quo_welfare=self.cumulative_status_quo_welfare,
                cumulative_net_gain_over_status_quo=self.cumulative_net_gain_over_status_quo,
                cumulative_realized_collaboration_surplus=self.cumulative_realized_collaboration_surplus,
                payoffs=resolution.payoffs.copy(),
                opportunity=opportunity.as_dict(),
            )
        )
        self.carrier_a.register_round(
            round_index=self.current_round,
            action=action_a,
            outcome=resolution.outcome,
            payoff=resolution.payoffs["a"],
            applied_profile=resolution.applied_profile,
        )
        self.carrier_b.register_round(
            round_index=self.current_round,
            action=action_b,
            outcome=resolution.outcome,
            payoff=resolution.payoffs["b"],
            applied_profile=resolution.applied_profile,
        )

    def step(self) -> None:
        if not self.running:
            return
        if self.current_round >= self.n_rounds:
            self.running = False
            return

        opportunity = self.opportunity_generator.sample()
        action_a = self.carrier_a.choose_action(opportunity, self.adapter)
        action_b = self.carrier_b.choose_action(opportunity, self.adapter)
        resolution = self.adapter.resolve_round(opportunity, action_a, action_b)
        cooperative_welfare = self._counterfactual_cooperative_welfare(opportunity)
        cooperative_payoffs = self._counterfactual_cooperative_payoffs(opportunity)

        self.carrier_a.cash += resolution.payoffs["a"]
        self.carrier_b.cash += resolution.payoffs["b"]
        self.last_actions = {"a": action_a, "b": action_b}
        self.last_outcome = resolution.outcome
        self.last_welfare = resolution.welfare
        self.cooperative_welfare = cooperative_welfare
        self.last_utility_a = resolution.payoffs["a"]
        self.last_utility_b = resolution.payoffs["b"]
        self.last_status_quo_welfare = resolution.status_quo_welfare
        self.last_net_gain_over_status_quo = resolution.net_gain_over_status_quo
        self.last_realized_collaboration_surplus = resolution.realized_collaboration_surplus
        self.last_failure_type = resolution.failure_type
        self.cooperative_cash_a += cooperative_payoffs["a"]
        self.cooperative_cash_b += cooperative_payoffs["b"]
        self.total_welfare += resolution.welfare
        self.cumulative_joint_welfare += resolution.realized_welfare
        self.cumulative_status_quo_welfare += resolution.status_quo_welfare
        self.cumulative_net_gain_over_status_quo += resolution.net_gain_over_status_quo
        self.cumulative_realized_collaboration_surplus += (
            resolution.realized_collaboration_surplus
        )

        if resolution.collaboration:
            self.collaboration_count += 1
        else:
            self._update_failure_type_counts(resolution.failure_type)
        self._update_trust_and_counts(
            action_a,
            action_b,
            resolution.collaboration,
            failure_type=resolution.failure_type,
        )
        self._record_round(opportunity, action_a, action_b, resolution)

        self.current_round += 1
        self.datacollector.collect(self)
        if self.current_round >= self.n_rounds:
            self.running = False

    def run_model(self) -> None:
        while self.running:
            self.step()

    def get_summary_metrics(self) -> Dict[str, float]:
        return {
            "institution": self.institution_name,
            "rounds": float(self.current_round),
            "collaboration_rate": (
                self.collaboration_count / self.current_round if self.current_round else 0.0
            ),
            "cash_a": self.carrier_a.cash,
            "cash_b": self.carrier_b.cash,
            "trust_a": self.carrier_a.trust,
            "trust_b": self.carrier_b.trust,
            "mean_welfare": (
                self.total_welfare / self.current_round if self.current_round else 0.0
            ),
            "cumulative_joint_welfare": self.cumulative_joint_welfare,
            "cumulative_status_quo_welfare": self.cumulative_status_quo_welfare,
            "cumulative_net_gain_over_status_quo": self.cumulative_net_gain_over_status_quo,
            "cumulative_realized_collaboration_surplus": self.cumulative_realized_collaboration_surplus,
            "mutual_refusal_count": float(self.mutual_refusal_count),
            "one_refusal_failure_count": float(self.one_refusal_failure_count),
            "mismatch_failure_count": float(self.mismatch_failure_count),
            "other_failure_count": float(self.other_failure_count),
        }
