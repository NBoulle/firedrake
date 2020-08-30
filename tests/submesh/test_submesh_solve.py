# Simple Poisson equation
# =========================

import numpy as np
import math
import pytest

from firedrake import *
from firedrake.cython import dmcommon
from firedrake.petsc import PETSc
from pyop2.datatypes import IntType
import ufl


@pytest.mark.parallel
@pytest.mark.parametrize("f_lambda", [lambda x: x[0] < 1.0001, lambda x: x[0] > 0.9999])
@pytest.mark.parametrize("b_lambda", [lambda x: x[0] > 0.9999, lambda x: x[0] < 1.0001, lambda x: x[1] < 0.0001, lambda x: x[1] > 0.9999])
def test_submesh_poisson_cell(f_lambda, b_lambda):

    # This test is for checking an edge case
    # where we have few elements.

    msh = RectangleMesh(2, 1, 2., 1., quadrilateral=True)
    msh.init()

    msh.markSubdomain("half_domain", 111, "cell", None, geometric_expr = f_lambda)

    submsh = SubMesh(msh, "half_domain", 111, "cell")

    V = FunctionSpace(submsh, "CG", 1)

    u = Function(V)
    v = TestFunction(V)

    f = Function(V)
    x, y = SpatialCoordinate(submsh)
    f.interpolate(-8.0 * pi * pi * cos(x * pi * 2) * cos(y * pi * 2))

    dx = Measure("cell", submsh)

    a = - inner(grad(u), grad(v)) * dx
    L = inner(f, v) * dx

    g = Function(V)
    g.interpolate(cos(2 * pi * x) * cos(2 * pi * y))

    # New boundary is labeled as max({1, 2, 3, 4}) + 1 = 5.
    bc1 = DirichletBC(V, g, 5)

    parameters = {"mat_type": "aij",
                  "snes_type": "ksponly",
                  "ksp_type": "preonly",
                  "pc_type": "lu"}

    solve(a - L == 0, u, bcs = [bc1], solver_parameters=parameters)


@pytest.mark.parametrize("f_lambda", [lambda x: x[0] < 1.0001, lambda x: x[0] > 0.9999])
@pytest.mark.parametrize("b_lambda", [lambda x: x[0] > 0.9999, lambda x: x[0] < 1.0001, lambda x: x[1] < 0.0001, lambda x: x[1] > 0.9999])
def test_submesh_poisson_cell_error(f_lambda, b_lambda):

    msh = RectangleMesh(200, 100, 2., 1., quadrilateral=True)
    msh.init()

    x, y = SpatialCoordinate(msh)
    DP = FunctionSpace(msh, 'DP', 0)
    fltr = Function(DP)
    fltr = Function(DP).interpolate(ufl.conditional(real(x) < 1, 1, 0))

    msh.markSubdomain("half_domain", 111, "cell", fltr)

    submsh = SubMesh(msh, "half_domain", 111, "cell")

    V = FunctionSpace(submsh, "CG", 1)

    u = Function(V)
    v = TestFunction(V)

    f = Function(V)
    x, y = SpatialCoordinate(submsh)
    f.interpolate(-8.0 * pi * pi * cos(x * pi * 2) * cos(y * pi * 2))

    dx = Measure("cell", submsh)

    a = - inner(grad(u), grad(v)) * dx
    L = inner(f, v) * dx

    g = Function(V).interpolate(cos(2 * pi * x) * cos(2 * pi * y))

    bc1 = DirichletBC(V, g, 5)

    parameters = {"mat_type": "aij",
                  "snes_type": "ksponly",
                  "ksp_type": "preonly",
                  "pc_type": "lu"}

    solve(a - L == 0, u, bcs = [bc1], solver_parameters=parameters)

    assert(sqrt(assemble(inner(u - g, u - g) * dx)) < 0.00018)


@pytest.mark.parallel
def test_submesh_helmholtz():

    msh = RectangleMesh(2**8, 2**7, 2., 1., quadrilateral=True)
    msh.init()

    x0, y0 = SpatialCoordinate(msh)
    DP = FunctionSpace(msh, 'DP', 0)
    fltr = Function(DP)
    fltr = Function(DP).interpolate(ufl.conditional(real(x0) > 1, 1, 0))
    #msh.markSubdomain("half_domain", 222, "cell", None, geometric_expr = lambda x: x[0] > 0.9999)
    msh.markSubdomain("half_domain", 222, "cell", fltr)

    submsh = SubMesh(msh, "half_domain", 222, "cell")
    submsh.init()

    V0 = FunctionSpace(msh, "CG", 1)
    V1 = FunctionSpace(submsh, "CG", 1)

    W = V0 * V1

    w = Function(W)
    u = Function(W)
    #u0, u1 = split(u)
    u0, u1 = TrialFunctions(W)
    v0, v1 = TestFunctions(W)

    g0 = Function(V0).interpolate(cos(2 * pi * x0) * cos(2 * pi * y0))
    f0 = Function(V0).interpolate(-8.0 * pi * pi * cos(x0 * pi * 2) * cos(y0 * pi * 2))

    dx0 = Measure("cell", domain=msh)
    dx1 = Measure("cell", domain=submsh)

    a = - inner(grad(u0), grad(v0)) * dx0 + inner(u0 - u1, v1) * dx1
    L = inner(f0, v0) * dx0
    bcs = [DirichletBC(W.sub(0), g0, (1, 2, 3, 4)), ]
    #a = inner(u0, v0) * dx0 + inner(u1 - u0, v1) * dx1
    #L = inner(g0, v0) * dx0
    #bcs = []

    parameters = {"mat_type": "aij",
                  "snes_type": "ksponly",
                  "ksp_type": "preonly",
                  "pc_type": "lu"}

    """
    mat = assemble(a)
    print("")
    print("00")
    print(mat.M[0][0].values)
    print("01")
    print(mat.M[0][1].values)
    print("10")
    print(mat.M[1][0].values)
    print("11")
    print(mat.M[1][1].values)
    #u = Function(W)
    """
    solve(a == L, u, bcs = bcs, solver_parameters=parameters)
    #solve(a - L == 0, u, bcs = [bc0, ])

    x1, y1 = SpatialCoordinate(submsh)
    g1 = Function(V1).interpolate(cos(2 * pi * x1) * cos(2 * pi * y1))

    u0, u1 = u.split()

    print("L2:", assemble((u1 - g1) ** 2 * dx1))
    #print(np.allclose(u1.dat.data, g1.dat.data))
    #print(u0.dat.data)
    #print(g0.dat.data)
    #print(u1.dat.data)
    #print(g1.dat.data)