"""Convergence tests for the stencils generated"""

import devito as dv
import numpy as np
import sympy as sp
import pytest

from test_geometry import read_sdf
from schism import BoundaryGeometry, BoundaryConditions, Boundary


def sinusoid(func, x, ppw, deriv=0):
    """
    Return a sinusoidal function to test against.

    Parameters
    ----------
    func : str
        'sin' or 'cos'
    x : ndarray
        Values to take the function of
    ppw : int
        Points per wavelength
    deriv : int
        Derivative to take
    """
    xind = sp.Symbol('x')
    if func == 'sin':
        expr = sp.sin(2*sp.pi*(xind-50.5)/ppw)
    elif func == 'cos':
        expr = sp.cos(2*sp.pi*(xind-50.5)/ppw)
    if deriv != 0:
        diff_expr = sp.diff(expr, *[xind for i in range(deriv)])
    else:  # Need to sidestep default behaviour to take single deriv
        diff_expr = expr

    lam = sp.lambdify(xind, diff_expr)
    return lam(x)


class TestHorizontalSetup:
    """Simple tests based on a horizontal boundary"""

    @pytest.mark.parametrize('s_o', [2, 4, 6])
    def test_horizontal_convergence(self, s_o):
        """
        Convergence test for immersed boundary stencils at a horizontal surface
        0.5 dy above the last interior point.
        """
        # Load the flat 2D sdf
        sdf = read_sdf('horizontal', 2)
        # Create a geometry from it
        bg = BoundaryGeometry(sdf)
        grid = bg.grid

        f = dv.TimeFunction(name='f', grid=grid, space_order=s_o)
        # Deriv will be dy2
        deriv = (f.dy2,)  # Wants to be tuple

        # Pressure free-surface bcs
        if s_o == 2:
            bcs = BoundaryConditions([dv.Eq(f, 0),
                                      dv.Eq(f.dx2+f.dy2, 0)])
        elif s_o == 4:
            bcs = BoundaryConditions([dv.Eq(f, 0),
                                      dv.Eq(f.dx2+f.dy2, 0),
                                      dv.Eq(f.dx4 + 2*f.dx2dy2 + f.dy4, 0)])
        elif s_o == 6:
            bcs = BoundaryConditions([dv.Eq(f, 0),
                                      dv.Eq(f.dx2+f.dy2, 0),
                                      dv.Eq(f.dx4 + 2*f.dx2dy2 + f.dy4, 0),
                                      dv.Eq(f.dx6 + 3*f.dx4dy2
                                            + 3*f.dx2dy4 + f.dy6, 0)])

        boundary = Boundary(bcs, bg)
        subs = boundary.substitutions(deriv)

        # Fill f with sinusoid
        yinds = np.arange(grid.shape[-1])

        eq = dv.Eq(f.forward, subs[f.dy2])
        op = dv.Operator(eq)

        errs = []

        if s_o == 2 or s_o == 4:
            refinements = [1, 2, 4, 8, 16]
        elif s_o == 6:
            # Tighter range as you hit the noise floor otherwise
            refinements = [1, 2, 3, 4]
        for refinement in refinements:
            f.data[:] = 0  # Reset the data
            f.data[0] = sinusoid('sin', yinds, refinement*10, deriv=0)
            op.apply(time_M=1)

            # Scaling factor
            # (as I'm expanding the function, not shrinking the grid)
            err = f.data[-1]*10**2
            err -= sinusoid('sin', yinds, refinement*10, deriv=2)

            # Trim down to interior and exclude edges
            err_trimmed = err[s_o//2:-s_o//2, s_o//2:50]
            errs.append(float(np.amax(np.abs(err_trimmed))))

        grad = np.polyfit(np.log10(refinements), np.log10(errs), 1)[0]

        assert grad <= -s_o