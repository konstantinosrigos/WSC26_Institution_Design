"""Institutional regime configuration and IAD mapping helpers."""

from dataclasses import dataclass, replace
from pathlib import Path
import re
from typing import Dict, Literal

RegimeName = Literal[
    "baseline",
    "compensation",
    "commitment",
    "platform_priority",
]

REGIMES: tuple[RegimeName, ...] = (
    "baseline",
    "compensation",
    "commitment",
    "platform_priority",
)


@dataclass(frozen=True)
class InstitutionSpec:
    """Institution-level parameters used by the Mesa simulation."""

    name: RegimeName
    identifier: str
    folder: Path
    compensation: float
    failed_coordination_penalty: float
    commitment_enabled: bool
    platform_priority_enabled: bool
    one_refusal_failure_penalty: float | None = None
    mismatch_failure_penalty: float | None = None
    executor_share_min: float | None = None
    executor_share_max: float | None = None
    status_quo_min: float = 8.0
    status_quo_max: float = 12.0
    giver_disutility_min: float = 0.7
    giver_disutility_max: float = 1.5
    surplus_if_a_executes_min: float = 3.6
    surplus_if_a_executes_max: float = 5.4
    surplus_if_b_executes_min: float = 2.6
    surplus_if_b_executes_max: float = 4.4
    can_take_probability: float = 0.85
    information_rule: str = "public_payoff_information"


_INSTITUTION_PARAM_PATTERN = re.compile(
    r"^\s*institution_param\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*,\s*([-+]?\d*\.?\d+)\s*\)\s*\.\s*$"
)


def _spec_table(root: Path) -> Dict[RegimeName, InstitutionSpec]:
    return {
        "baseline": InstitutionSpec(
            name="baseline",
            identifier="baseline",
            folder=root / "baseline",
            compensation=0.0,
            failed_coordination_penalty=0.5,
            commitment_enabled=False,
            platform_priority_enabled=False,
            one_refusal_failure_penalty=0.5,
            mismatch_failure_penalty=1.5,
            executor_share_min=0.68,
            executor_share_max=0.78,
            status_quo_min=8.0,
            status_quo_max=12.0,
            giver_disutility_min=0.7,
            giver_disutility_max=1.5,
            surplus_if_a_executes_min=3.6,
            surplus_if_a_executes_max=5.4,
            surplus_if_b_executes_min=2.6,
            surplus_if_b_executes_max=4.4,
            can_take_probability=0.85,
        ),
        "compensation": InstitutionSpec(
            name="compensation",
            identifier="compensation",
            folder=root / "compensation",
            compensation=1.25,
            failed_coordination_penalty=0.5,
            commitment_enabled=False,
            platform_priority_enabled=False,
            one_refusal_failure_penalty=0.5,
            mismatch_failure_penalty=1.5,
            executor_share_min=0.68,
            executor_share_max=0.78,
            status_quo_min=8.0,
            status_quo_max=12.0,
            giver_disutility_min=0.7,
            giver_disutility_max=1.5,
            surplus_if_a_executes_min=3.6,
            surplus_if_a_executes_max=5.4,
            surplus_if_b_executes_min=2.6,
            surplus_if_b_executes_max=4.4,
            can_take_probability=0.85,
        ),
        "commitment": InstitutionSpec(
            name="commitment",
            identifier="commitment",
            folder=root / "commitment",
            compensation=0.0,
            failed_coordination_penalty=0.4,
            commitment_enabled=True,
            platform_priority_enabled=False,
            one_refusal_failure_penalty=0.4,
            mismatch_failure_penalty=1.1,
            executor_share_min=0.68,
            executor_share_max=0.78,
            status_quo_min=8.0,
            status_quo_max=12.0,
            giver_disutility_min=0.7,
            giver_disutility_max=1.5,
            surplus_if_a_executes_min=3.6,
            surplus_if_a_executes_max=5.4,
            surplus_if_b_executes_min=2.6,
            surplus_if_b_executes_max=4.4,
            can_take_probability=0.85,
        ),
        "platform_priority": InstitutionSpec(
            name="platform_priority",
            identifier="platform_priority",
            folder=root / "platform_priority",
            compensation=0.0,
            failed_coordination_penalty=0.45,
            commitment_enabled=False,
            platform_priority_enabled=True,
            one_refusal_failure_penalty=0.45,
            mismatch_failure_penalty=1.2,
            executor_share_min=0.68,
            executor_share_max=0.78,
            status_quo_min=8.0,
            status_quo_max=12.0,
            giver_disutility_min=0.7,
            giver_disutility_max=1.5,
            surplus_if_a_executes_min=3.6,
            surplus_if_a_executes_max=5.4,
            surplus_if_b_executes_min=2.6,
            surplus_if_b_executes_max=4.4,
            can_take_probability=0.85,
        ),
    }


def _load_numeric_rule_params(rules_path: Path) -> Dict[str, float]:
    if not rules_path.exists():
        return {}

    params: Dict[str, float] = {}
    for line in rules_path.read_text(encoding="utf-8").splitlines():
        source = line.split("%", 1)[0].strip()
        if not source:
            continue
        match = _INSTITUTION_PARAM_PATTERN.match(source)
        if not match:
            continue
        params[match.group(1)] = float(match.group(2))
    return params


def get_institution_spec(
    regime: RegimeName,
    institutions_root: Path | None = None,
) -> InstitutionSpec:
    """Return the configured institution spec for one regime."""
    root = (
        institutions_root
        if institutions_root is not None
        else Path(__file__).resolve().parent / "institutions"
    )
    table = _spec_table(root)
    if regime not in table:
        supported = ", ".join(REGIMES)
        raise ValueError(
            "Unsupported institution '{}'. Supported: {}".format(regime, supported)
        )
    spec = table[regime]
    if not spec.folder.exists():
        raise FileNotFoundError(
            "Institution folder not found for '{}': {}".format(regime, spec.folder)
        )
    numeric_params = _load_numeric_rule_params(spec.folder / "rules.pl")
    field_overrides = {
        "compensation": numeric_params.get("compensation", spec.compensation),
        "failed_coordination_penalty": numeric_params.get(
            "failed_coordination_penalty", spec.failed_coordination_penalty
        ),
        "one_refusal_failure_penalty": numeric_params.get(
            "one_refusal_failure_penalty", spec.one_refusal_failure_penalty
        ),
        "mismatch_failure_penalty": numeric_params.get(
            "mismatch_failure_penalty", spec.mismatch_failure_penalty
        ),
        "executor_share_min": numeric_params.get("executor_share_min", spec.executor_share_min),
        "executor_share_max": numeric_params.get("executor_share_max", spec.executor_share_max),
        "status_quo_min": numeric_params.get("status_quo_min", spec.status_quo_min),
        "status_quo_max": numeric_params.get("status_quo_max", spec.status_quo_max),
        "giver_disutility_min": numeric_params.get(
            "giver_disutility_min", spec.giver_disutility_min
        ),
        "giver_disutility_max": numeric_params.get(
            "giver_disutility_max", spec.giver_disutility_max
        ),
        "surplus_if_a_executes_min": numeric_params.get(
            "surplus_if_a_executes_min", spec.surplus_if_a_executes_min
        ),
        "surplus_if_a_executes_max": numeric_params.get(
            "surplus_if_a_executes_max", spec.surplus_if_a_executes_max
        ),
        "surplus_if_b_executes_min": numeric_params.get(
            "surplus_if_b_executes_min", spec.surplus_if_b_executes_min
        ),
        "surplus_if_b_executes_max": numeric_params.get(
            "surplus_if_b_executes_max", spec.surplus_if_b_executes_max
        ),
        "can_take_probability": numeric_params.get(
            "can_take_probability", spec.can_take_probability
        ),
    }

    if field_overrides["executor_share_min"] is not None and field_overrides["executor_share_max"] is not None:
        if field_overrides["executor_share_min"] > field_overrides["executor_share_max"]:
            raise ValueError(
                "Invalid executor share range in rules for '{}': min {} > max {}".format(
                    regime,
                    field_overrides["executor_share_min"],
                    field_overrides["executor_share_max"],
                )
            )
    if field_overrides["status_quo_min"] > field_overrides["status_quo_max"]:
        raise ValueError(
            "Invalid status quo range in rules for '{}': min {} > max {}".format(
                regime, field_overrides["status_quo_min"], field_overrides["status_quo_max"]
            )
        )
    if field_overrides["giver_disutility_min"] > field_overrides["giver_disutility_max"]:
        raise ValueError(
            "Invalid giver disutility range in rules for '{}': min {} > max {}".format(
                regime,
                field_overrides["giver_disutility_min"],
                field_overrides["giver_disutility_max"],
            )
        )
    if field_overrides["surplus_if_a_executes_min"] > field_overrides["surplus_if_a_executes_max"]:
        raise ValueError(
            "Invalid A-surplus range in rules for '{}': min {} > max {}".format(
                regime,
                field_overrides["surplus_if_a_executes_min"],
                field_overrides["surplus_if_a_executes_max"],
            )
        )
    if field_overrides["surplus_if_b_executes_min"] > field_overrides["surplus_if_b_executes_max"]:
        raise ValueError(
            "Invalid B-surplus range in rules for '{}': min {} > max {}".format(
                regime,
                field_overrides["surplus_if_b_executes_min"],
                field_overrides["surplus_if_b_executes_max"],
            )
        )
    if not (0.0 <= float(field_overrides["can_take_probability"]) <= 1.0):
        raise ValueError(
            "Invalid can_take_probability for '{}': {} (expected [0,1])".format(
                regime, field_overrides["can_take_probability"]
            )
        )

    spec = replace(
        spec,
        **field_overrides,
    )
    return spec
