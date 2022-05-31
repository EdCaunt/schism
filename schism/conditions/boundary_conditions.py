"""Objects for the specification of boundary conditions"""

__all__ = ['BoundaryConditions']

import devito as dv
import networkx as nx

from devito.symbolics import retrieve_functions


class BoundaryCondition:
    """
    A single boundary condition imposed on some immersed surface

    Parameters
    ----------
    equation : Devito Eq
        The equality imposed on the surface
    functions : list of Devito Functions
        List of Functions on which boundary conditions are imposed. If none
        provided, then all time-dependent functions contained within the
        boundary condition will be used.

    Attributes
    ----------
    equation : Devito Eq
        The equality imposed on the surface
    functions : tuple
        The functions within the boundary condition on which boundary
        conditions are imposed
    dimensions : tuple
        Dimensions in which derivatives are taken within the boundary condition
    coeff_placeholders : tuple
        Placeholders used to replace coefficients in the LHS expression
    coeff_map : dict
        Map between coeffcient placeholders and their expressions within the
        LHS expression
    """
    def __init__(self, eq, funcs=None):
        self._eq = eq
        # Parse the rhs
        self._parse_rhs()
        # Get the intersection between funcs in lhs and funcs supplied
        self._get_functions(funcs)
        # Get the dimensions in which derivatives are taken
        self._get_derivative_dimensions()
        # Substitute the coefficients in the expression
        # Note: needs to complain if a function found in the expression
        # TODO: Finish this

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        else:
            return False

    def __str__(self):
        return "BoundaryCondition({})".format(str(self.equation))

    def __repr__(self):
        return "BoundaryCondition({})".format(str(self.equation))

    def _parse_rhs(self):
        """Parse and process the RHS of the equation"""
        if self.rhs != 0:
            raise NotImplementedError("Nonzero RHS currently unsupported")

    def _get_functions(self, funcs):
        """
        Get the intersection between functions in the LHS and functions
        supplied by the user
        """
        if funcs is None:
            # Get all time-dependent functions in LHS
            all_funcs = retrieve_functions(self.lhs)
            # Cull duplicates in here as retrieve_functions works on a term-by-
            # term basis and will return duplicates if a function appears
            # multiple times in an expression.
            self._funcs = tuple(set([func for func in all_funcs
                                     if func.is_TimeDependent]))
        else:
            # Need intersection of functions in LHS and specified functions
            all_funcs = set(retrieve_functions(self.lhs))
            self._funcs = tuple(all_funcs.intersection(set(funcs)))

    def _get_derivative_dimensions(self):
        """Get the dimensions in which derivatives are taken"""
        # Get all the derivatives on the lhs
        derivs = self.lhs.find(dv.Derivative)
        dims = set()  # Dimensions in which derivs are taken
        for deriv in derivs:
            # Check that expression is a function
            if not isinstance(deriv.expr, dv.Function):
                errmsg = """Derivatives of non-Function expressions
                            unsupported. Note that currently f.dx.dy will not
                            be collapsed to f.dxdy, and should be amended as
                            such."""
                raise NotImplementedError(errmsg)

            # Check that derivative is of a function in .funcs
            if deriv.expr in self.funcs:
                dims.update(deriv.dims)
            # Derivatives of other fields currently unsupported
            else:
                errmsg = "Derivatives of coefficent functions unsupported"
                raise NotImplementedError(errmsg)

        if len(dims) == 0:  # If no derivatives present, then set to None
            self._dims = None
        else:  # Otherwise record the derivatives
            self._dims = tuple(dims)

    @property
    def equation(self):
        """The equation imposed by the boundary condition"""
        return self._eq

    @property
    def lhs(self):
        """Alias for self.equation.lhs"""
        return self.equation.lhs

    @property
    def rhs(self):
        """Alias for self.equation.rhs"""
        return self.equation.rhs

    @property
    def funcs(self):
        """Functions on which the BC is imposed"""
        return self._funcs

    @property
    def dims(self):
        """Dimensions in which derivatives are taken"""
        return self._dims


class ConditionGroup:
    """
    A group of boundary conditions with overlapping functions

    Parameters
    ----------
    conditions : tuple
        BoundaryCondition objects in the group
    funcs : tuple
        Functions that define the group

    Attributes
    ----------
    conditions : tuple
        BoundaryCondition objects in the group
    funcs : tuple
        Functions that define the group
    dimension_map : dict
        Mapping between dimensions and valid BCs for that dimension
    """
    def __init__(self, conditions, funcs):
        self._conds = conditions
        self._funcs = funcs

    def __str__(self):
        return "ConditionGroup{}".format(str(self.funcs))

    def __repr__(self):
        return "ConditionGroup{}".format(str(self.funcs))

    @property
    def conditions(self):
        """BoundaryCondition objects in the group"""
        return self._conds

    @property
    def funcs(self):
        """Functions that define the group"""
        return self._funcs


class BoundaryConditions:
    """
    A set of specified boundary conditions which will be imposed on some
    immersed surface.

    Parameters
    ----------
    equations : list of Devito Eq
        List of equalities to be imposed on the surface
    functions : list of Devito Functions
        List of Functions on which boundary conditions are imposed.

    Attributes
    ----------
    equations : tuple
        Equalities to be imposed on the surface
    conditions : tuple
        BoundaryCondition objects for each boundary condition
    groups : tuple
        Groups of boundary conditions which are connected by the functions
        used within them
    funcs : tuple
        Functions on which the boundary conditions are imposed (as specified)
        by user
    function_map : dict
        Mapping between functions and boundary condition groups
    """
    def __init__(self, eqs, funcs=None):
        # Flatten functions supplied and remove duplicates
        self._flatten_functions(funcs)
        # Create the equations tuple, flattening equations
        self._flatten_equations(eqs)
        # Set up the BoundaryCondition objects for each equation
        self._setup_bcs()
        # Set up the groups using networkx
        self._group_bcs()

        # Set up the remaining attributes and any helpers etc

    def _flatten_functions(self, funcs):
        """Flatten the functions provided where necessary"""
        if funcs is None:
            self._funcs = None
        else:
            flat_funcs = set()
            for func in funcs:
                try:
                    flat_funcs.update(func.flat())
                except AttributeError:
                    flat_funcs.add(func)
            self._funcs = tuple(flat_funcs)

    def _flatten_equations(self, eqs):
        """Flatten the equations provided"""
        eq_list = []
        for eq in eqs:
            try:
                eq_list += eq._flatten
            except KeyError:  # RHS doesn't match LHS size-wise
                errmsg = "Size of {} does not match {}"
                raise TypeError(errmsg.format(eq.lhs, eq.rhs))

        # Cull duplicates
        eq_set = set(eq_list)

        self._eqs = tuple(eq_set)

    def _setup_bcs(self):
        """Set up a BoundaryCondition object for each equation"""
        self._bcs = [BoundaryCondition(eq, funcs=self.funcs)
                     for eq in self.equations]

    def _group_bcs(self):
        """Group the BCs supplied by their overlapping functions"""
        # Use networkx graph to find interconnectivity between functions
        f_graph = nx.Graph()
        for bc in self.bcs:
            f_graph.add_nodes_from(bc.funcs)
            # Set up edges between first function and all others
            # Will all end up linked through the first function
            edges = [(bc.funcs[0], func) for func in bc.funcs[1:]]
            f_graph.add_edges_from(edges)

        # Functions interlinked by boundary conditions
        f_groups = [tuple(group) for group in nx.connected_components(f_graph)]

        bc_groups = []
        f_map = {}
        for group in f_groups:
            conditions = [bc for bc in self.bcs if bc.funcs[0] in group]
            new_group = ConditionGroup(conditions, group)
            bc_groups.append(new_group)
            for func in group:
                f_map[func] = new_group
        print(f_map)

    @property
    def equations(self):
        """Equalities to be imposed on the surface"""
        return self._eqs

    @property
    def bcs(self):
        """BoundaryCondition for each equation"""
        return self._bcs

    @property
    def funcs(self):
        """
        The functions on which Boundary conditions are imposed. Note these are
        what has been specified by the user, not what is actually contained
        within the boundary conditions
        """
        return self._funcs
