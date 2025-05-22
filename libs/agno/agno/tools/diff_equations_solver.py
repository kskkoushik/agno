import json
import sympy as sp
from typing import Callable, List, Optional

from agno.tools import Toolkit
from agno.utils.log import log_info, logger


class DifferentialEquationTools(Toolkit):
    def __init__(self, solve_ode: bool = True, enable_all: bool = False, **kwargs):
        tools: List[Callable] = []
        if solve_ode or enable_all:
            tools.append(self.solve_ode)
        super().__init__(name="differential_equation_solver", tools=tools, **kwargs)

    def solve_ode(
        self,
        equation: str,
        function: str = "y",
        variable: str = "x",
        initial_condition: Optional[dict] = None
    ) -> str:
        """
        Solve a first-order ODE symbolically.

        Args:
            equation (str): ODE in the form of a string, e.g. "dy/dx = x + y"
            function (str): Dependent variable (default "y")
            variable (str): Independent variable (default "x")
            initial_condition (dict): Optional initial condition as {"x0": float, "y0": float}

        Returns:
            str: JSON-formatted solution
        """
        try:
            x = sp.Symbol(variable)
            y = sp.Function(function)(x)

            # Parse the RHS of dy/dx = <expr>
            lhs, rhs = map(str.strip, equation.split("="))
            if lhs != f"d{function}/d{variable}":
                return json.dumps({"error": f"Expected LHS 'd{function}/d{variable}', got '{lhs}'"})

            ode_rhs = sp.sympify(rhs)
            ode = sp.Eq(y.diff(x), ode_rhs)

            if initial_condition:
                x0 = float(initial_condition.get("x0"))
                y0 = float(initial_condition.get("y0"))
                sol = sp.dsolve(ode, y, ics={y.subs(x, x0): y0})
            else:
                sol = sp.dsolve(ode, y)

            log_info(f"Solved ODE: {equation} with solution: {sol}")
            return json.dumps({"operation": "solve_ode", "solution": str(sol)})
        except Exception as e:
            logger.error(f"Failed to solve ODE: {equation}")
            return json.dumps({"operation": "solve_ode", "error": str(e)})
