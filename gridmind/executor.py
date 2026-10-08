"""Dispatch Executor for GridMind.

Applies validated candidate actions to the physical environment / simulator:
- Verifies integrity of first-interval dispatch variables
- Acts as a defensive execution bridge between optimization and physical reality
- Advances the simulation state by one 15-minute interval
"""

from typing import Any, Dict
from gridmind.sim.simulator import Simulator
from gridmind.sim.state import DispatchAction, GridState


class DispatchExecutor:
    """Safely dispatches commanded setpoints to the portfolio simulator."""

    def __init__(self, simulator: Simulator) -> None:
        self.simulator = simulator

    def apply(self, action: DispatchAction) -> GridState:
        """Execute first-interval dispatch action against simulator.

        Args:
            action: Validated first-interval dispatch action.

        Returns:
            Updated GridState resulting from physical execution.
        """
        # Defensive sanitation: ensure no NaN or negative numbers reach simulator
        sanitized = DispatchAction(
            battery_charge={b: max(0.0, float(v)) for b, v in action.battery_charge.items()},
            battery_discharge={b: max(0.0, float(v)) for b, v in action.battery_discharge.items()},
            grid_import=max(0.0, float(action.grid_import)),
            grid_export=max(0.0, float(action.grid_export)),
            solar_curtailment={s: max(0.0, float(v)) for s, v in action.solar_curtailment.items()},
            wind_curtailment={w: max(0.0, float(v)) for w, v in action.wind_curtailment.items()},
            demand_response={c: max(0.0, float(v)) for c, v in action.demand_response.items()},
            contract_shortfall={c: max(0.0, float(v)) for c, v in action.contract_shortfall.items()},
            unserved_critical={c: max(0.0, float(v)) for c, v in action.unserved_critical.items()},
            balance_slack=float(action.balance_slack),
        )

        next_state = self.simulator.step(sanitized)
        return next_state
