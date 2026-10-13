"""Exchange opportunity generation for the logistics domain."""

from __future__ import annotations

import random
from dataclasses import dataclass, asdict
from typing import Dict


@dataclass(frozen=True)
class ExchangeOpportunity:
    """One paired-trip exchange opportunity in one simulation round."""

    # Required by the prompt:
    status_quo_a: float
    status_quo_b: float
    payoff_if_a_executes_both: float
    payoff_if_b_executes_both: float
    a_can_take: bool
    b_can_take: bool
    surplus_if_a_executes: float
    surplus_if_b_executes: float
    executor_share_of_surplus: float

    # Extra detail used by payoff rules:
    payoff_to_b_if_a_executes: float
    payoff_to_a_if_b_executes: float
    giver_disutility: float

    def as_dict(self) -> Dict[str, float]:
        return asdict(self)


class OpportunityGenerator:
    """Simple stochastic generator for repeated exchange opportunities."""

    def __init__(
        self,
        seed: int | None = None,
        status_quo_min: float = 8.0,
        status_quo_max: float = 12.0,
        giver_disutility_min: float = 0.7,
        giver_disutility_max: float = 1.5,
        surplus_if_a_executes_min: float = 3.6,
        surplus_if_a_executes_max: float = 5.4,
        surplus_if_b_executes_min: float = 2.6,
        surplus_if_b_executes_max: float = 4.4,
        can_take_probability: float = 0.85,
        executor_share_min: float = 0.68,
        executor_share_max: float = 0.78,
    ) -> None:
        self._rng = random.Random(seed)
        self.status_quo_min = status_quo_min
        self.status_quo_max = status_quo_max
        self.giver_disutility_min = giver_disutility_min
        self.giver_disutility_max = giver_disutility_max
        self.surplus_if_a_executes_min = surplus_if_a_executes_min
        self.surplus_if_a_executes_max = surplus_if_a_executes_max
        self.surplus_if_b_executes_min = surplus_if_b_executes_min
        self.surplus_if_b_executes_max = surplus_if_b_executes_max
        self.can_take_probability = can_take_probability
        self.executor_share_min = executor_share_min
        self.executor_share_max = executor_share_max
        if self.status_quo_min > self.status_quo_max:
            raise ValueError(
                "status_quo_min ({}) cannot be greater than status_quo_max ({})".format(
                    self.status_quo_min,
                    self.status_quo_max,
                )
            )
        if self.giver_disutility_min > self.giver_disutility_max:
            raise ValueError(
                "giver_disutility_min ({}) cannot be greater than giver_disutility_max ({})".format(
                    self.giver_disutility_min,
                    self.giver_disutility_max,
                )
            )
        if self.surplus_if_a_executes_min > self.surplus_if_a_executes_max:
            raise ValueError(
                "surplus_if_a_executes_min ({}) cannot be greater than surplus_if_a_executes_max ({})".format(
                    self.surplus_if_a_executes_min,
                    self.surplus_if_a_executes_max,
                )
            )
        if self.surplus_if_b_executes_min > self.surplus_if_b_executes_max:
            raise ValueError(
                "surplus_if_b_executes_min ({}) cannot be greater than surplus_if_b_executes_max ({})".format(
                    self.surplus_if_b_executes_min,
                    self.surplus_if_b_executes_max,
                )
            )
        if not (0.0 <= self.can_take_probability <= 1.0):
            raise ValueError(
                "can_take_probability ({}) must be in [0, 1]".format(
                    self.can_take_probability,
                )
            )
        if self.executor_share_min > self.executor_share_max:
            raise ValueError(
                "executor_share_min ({}) cannot be greater than executor_share_max ({})".format(
                    self.executor_share_min,
                    self.executor_share_max,
                )
            )

    def sample(self) -> ExchangeOpportunity:
        sq_a = self._rng.uniform(self.status_quo_min, self.status_quo_max)
        sq_b = self._rng.uniform(self.status_quo_min, self.status_quo_max)
        giver_disutility = self._rng.uniform(
            self.giver_disutility_min,
            self.giver_disutility_max,
        )

        # Explicit directional surplus over status quo for successful collaborations.
        surplus_if_a_executes = self._rng.uniform(
            self.surplus_if_a_executes_min,
            self.surplus_if_a_executes_max,
        )
        surplus_if_b_executes = self._rng.uniform(
            self.surplus_if_b_executes_min,
            self.surplus_if_b_executes_max,
        )
        executor_share_of_surplus = self._rng.uniform(
            self.executor_share_min,
            self.executor_share_max,
        )

        a_gain_if_a_executes = surplus_if_a_executes * executor_share_of_surplus
        b_gain_if_a_executes = surplus_if_a_executes - a_gain_if_a_executes
        b_gain_if_b_executes = surplus_if_b_executes * executor_share_of_surplus
        a_gain_if_b_executes = surplus_if_b_executes - b_gain_if_b_executes

        payoff_if_a_executes_both = sq_a + a_gain_if_a_executes
        payoff_if_b_executes_both = sq_b + b_gain_if_b_executes
        payoff_to_b_if_a_executes = sq_b + b_gain_if_a_executes
        payoff_to_a_if_b_executes = sq_a + a_gain_if_b_executes

        return ExchangeOpportunity(
            status_quo_a=sq_a,
            status_quo_b=sq_b,
            payoff_if_a_executes_both=payoff_if_a_executes_both,
            payoff_if_b_executes_both=payoff_if_b_executes_both,
            a_can_take=self._rng.random() < self.can_take_probability,
            b_can_take=self._rng.random() < self.can_take_probability,
            surplus_if_a_executes=surplus_if_a_executes,
            surplus_if_b_executes=surplus_if_b_executes,
            executor_share_of_surplus=executor_share_of_surplus,
            payoff_to_b_if_a_executes=payoff_to_b_if_a_executes,
            payoff_to_a_if_b_executes=payoff_to_a_if_b_executes,
            giver_disutility=giver_disutility,
        )
