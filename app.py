"""Interactive Mesa dashboard for Institution Design.

Run with:
    solara run app.py
"""

from __future__ import annotations

import solara
from mesa.visualization import SolaraViz, make_plot_component

from institutions import REGIMES
from model import LogisticsCollaborationModel


def round_status(model: LogisticsCollaborationModel):
    return solara.Markdown(
        "\n".join(
            [
                f"**Institution:** `{model.institution_name}`<br>",
                f"**Round:** `{model.current_round}` / `{model.n_rounds}`<br>",
                f"**Collaborations:** `{model.collaboration_count}` (rate `{(model.collaboration_count / model.current_round) if model.current_round else 0.0:.3f}`)",
                f"**Last actions:** `a={model.last_actions['a']}`, `b={model.last_actions['b']}`<br>",
                f"**Last outcome:** `{model.last_outcome}`<br>",
                f"**Last welfare:** `{model.last_welfare:.3f}`<br>",
                f"**Cooperative welfare (counterfactual):** `{model.cooperative_welfare:.3f}`\n",
                "**Per-step utilities:**<br>",
                f"- `u_a(t) = {model.last_utility_a:.3f}`<br>",
                f"- `u_b(t) = {model.last_utility_b:.3f}`",
            ]
        )
    )



model_params = {
    "institution": {
        "type": "Select",
        "label": "Institution",
        "value": "baseline",
        "values": list(REGIMES),
    },
    "n_rounds": {
        "type": "SliderInt",
        "label": "Rounds",
        "value": 200,
        "min": 20,
        "max": 2000,
        "step": 20,
    },
    "initial_trust": {
        "type": "SliderFloat",
        "label": "Initial trust",
        "value": 0.45,
        "min": 0.0,
        "max": 1.0,
        "step": 0.05,
    },
    "risk_a": {
        "type": "SliderFloat",
        "label": "Risk A",
        "value": 0.25,
        "min": 0.0,
        "max": 1.0,
        "step": 0.05,
    },
    "risk_b": {
        "type": "SliderFloat",
        "label": "Risk B",
        "value": 0.25,
        "min": 0.0,
        "max": 1.0,
        "step": 0.05,
    },
    "risk_weight": {
        "type": "SliderFloat",
        "label": "Risk weight",
        "value": 3.0,
        "min": 0.5,
        "max": 8.0,
        "step": 0.25,
    },
    "seed": {
        "type": "SliderInt",
        "label": "Seed",
        "value": 42,
        "min": 0,
        "max": 9999,
        "step": 1,
    },
}

collaboration_plot = make_plot_component({"collaboration_rate": "tab:green"})
welfare_plot = make_plot_component(
    {"last_welfare": "tab:blue", "cooperative_welfare": "tab:gray"}
)
utility_plot = make_plot_component(
    {"last_utility_a": "tab:cyan", "last_utility_b": "tab:pink"}
)
trust_plot = make_plot_component({"trust_a": "tab:orange", "trust_b": "tab:red"})
cash_plot = make_plot_component(
    {
        "cash_a": "tab:purple",
        "cash_b": "tab:brown",
        "cooperative_cash_a": "tab:olive",
        "cooperative_cash_b": "tab:gray",
    }
)

model = LogisticsCollaborationModel()

page = SolaraViz(
    model,
    components=[
        round_status,
        utility_plot,
        collaboration_plot,
        welfare_plot,
        trust_plot,
        cash_plot,
    ],
    model_params=model_params,
    name="WSC26 Institution Design for Logistics Collaboration",
)
page  # noqa
