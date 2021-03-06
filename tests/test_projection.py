"""Tests for the Projection object"""

import pytest
import devito as dv
import numpy as np
import os

from schism.basic.basis import Basis
from schism.finite_differences.interpolate_project import Projection


class DummyGroup:
    """Dummy object to replace ConditionGroup for testing"""
    def __init__(self, **kwargs):
        self.funcs = kwargs.get('funcs')


class TestProjection:
    """Tests for the Projection object"""

    grid2D = dv.Grid(shape=(11, 11), extent=(10., 10.))
    grid3D = dv.Grid(shape=(11, 11, 11), extent=(10., 10., 10.))

    f = dv.TimeFunction(name='f', grid=grid2D, space_order=2)
    g = dv.TimeFunction(name='g', grid=grid3D, space_order=2)

    @pytest.mark.parametrize('deriv',
                             [f.dx, f.dy, f.dx2, f.dxdy, g.dx, g.dz2, g.dxdy])
    def test_footprint(self, deriv):
        """Check that the correct stencil footprint is generated"""
        group = DummyGroup(funcs=(deriv.expr,))
        basis_map = {deriv.expr: Basis(deriv.expr.name,
                                       deriv.expr.space_dimensions,
                                       deriv.expr.space_order)}
        project = Projection(deriv, group, basis_map)

        path = os.path.dirname(os.path.abspath(__file__))
        fname = path + '/results/projection_test_results/footprint/' \
            + str(deriv) + '.npy'

        check = np.load(fname)
        assert np.all(np.array(project.footprint) == check)

    @pytest.mark.parametrize('deriv',
                             [f.dx, f.dy, f.dx2, f.dxdy, g.dx, g.dz2, g.dxdy])
    def test_matrix(self, deriv):
        """Check that the correct interior matrix is generated"""
        group = DummyGroup(funcs=(deriv.expr,))
        basis_map = {deriv.expr: Basis(deriv.expr.name,
                                       deriv.expr.space_dimensions,
                                       deriv.expr.space_order)}
        project = Projection(deriv, group, basis_map)

        path = os.path.dirname(os.path.abspath(__file__))
        fname = path + '/results/projection_test_results/matrix/' \
            + str(deriv) + '.npy'

        check = np.load(fname)
        assert np.all(np.isclose(project.project_matrix, check))
