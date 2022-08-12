import pytest
import numpy as np
from firedrake import *
import ufl


@pytest.fixture(scope='module')
def mesh():
    return UnitSquareMesh(5, 5)


@pytest.fixture
def M(fs):
    uhat = TrialFunction(fs)
    v = TestFunction(fs)
    return inner(uhat, v) * dx


def test_assemble_interp(mesh):
    V1 = FunctionSpace(mesh, "CG", 1)
    V2 = FunctionSpace(mesh, "CG", 2)

    x, y = SpatialCoordinate(mesh)
    expr = cos(2*pi*x)*sin(2*pi*y)
    f1 = Function(V1).interpolate(expr)

    # Check type
    If1 = Interp(f1, V2)
    assert isinstance(If1, ufl.Interp)

    # -- I(f1, V2) -- #
    a = assemble(If1)
    b = interpolate(f1, V2)
    assert np.allclose(a.dat.data, b.dat.data)

    assembled_If1 = assemble(If1)
    assert np.allclose(assembled_If1.dat.data, b.dat.data)

    # -- I(v1, V2) -- #
    v1 = TrialFunction(V1)
    Iv1 = Interp(v1, V2)

    # Get the interpolation matrix
    a = assemble(Iv1)
    res = Cofunction(V2.dual())
    # Check that `I * f1 == b` with I the interpolation matrix
    # and b the interpolation of f1 into V2.
    with f1.dat.vec_ro as x, res.dat.vec_ro as y:
        a.petscmat.mult(x, y)
    assert np.allclose(res.dat.data, b.dat.data)

    # -- Action(I(v1, V2), f1) -- #
    assembled_action_Iv1 = assemble(action(Iv1, f1))
    assert np.allclose(assembled_action_Iv1.dat.data, b.dat.data)

    # -- Adjoint(I(v1, V2)) -- #
    v2 = TestFunction(V2)
    c2 = assemble(v2 * dx)
    # Interpolation from V2* to V1*
    c1 = Cofunction(V1.dual()).interpolate(c2)
    # Interpolation matrix (V2* -> V1*)
    a = assemble(adjoint(Iv1))
    res = Cofunction(V1.dual())
    with c2.dat.vec_ro as x, res.dat.vec_ro as y:
        a.petscmat.mult(x, y)
    assert np.allclose(res.dat.data, c1.dat.data)

    # -- Action(Adjoint(I(v1, v2)), fstar) -- #
    fstar = Cofunction(V2.dual())
    v = Argument(V1, 0)
    Ivfstar = assemble(Interp(v, fstar))
    # Action(Adjoint(I(v1, v2)), fstar) <=> I(v, fstar)
    res = assemble(action(adjoint(Iv1), fstar))
    assert np.allclose(res.dat.data, Ivfstar.dat.data)

    # -- Interp(f1, u2) (rank 0) -- #
    # Set the Cofunction u2
    u2 = assemble(v2 * dx)
    # Interp(f1, u2) <=> Action(Interp(f1, V2), u2)
    # a is rank 0 so assembling it produces a scalar.
    a = assemble(Interp(f1, u2))
    # Compute numerically Action(Interp(f1, V2), u2)
    b = assemble(Interp(f1, V2))
    with b.dat.vec_ro as x, u2.dat.vec_ro as y:
        res = x.dot(y)
    assert np.abs(a - res) < 1e-9


def test_assemble_base_form_operator_expressions(mesh):
    V1 = FunctionSpace(mesh, "CG", 1)
    V2 = FunctionSpace(mesh, "CG", 2)

    x, y = SpatialCoordinate(mesh)
    f1 = Function(V1).interpolate(cos(2*pi*x)*sin(2*pi*y))
    f2 = Function(V1).interpolate(sin(2*pi*y))
    f3 = Function(V1).interpolate(cos(2*pi*x))

    If1 = Interp(f1, V2)
    If2 = Interp(f2, V2)
    If3 = Interp(f3, V2)

    # Sum of BaseFormOperators (1-form)
    res = assemble(If1 + If2 + If3)
    res2 = assemble(assemble(If1) + assemble(If2) + assemble(If3))
    assert np.allclose(res.dat.data, res2.dat.data)

    # Sum of BaseFormOperator and Coefficients (1-form)
    u = Function(V2).interpolate(x**2 + y**2)
    res = assemble(u + If1)
    res2 = assemble(assemble(If1) + assemble(u))
    assert np.allclose(res.dat.data, res2.dat.data)

    # Sum of BaseFormOperator (2-form)
    v1 = TrialFunction(V1)
    Iv1 = Interp(v1, V2)
    Iv2 = Interp(v1, V2)
    res = assemble(Iv1 + Iv2)
    mat_Iv1 = assemble(Iv1)
    mat_Iv2 = assemble(Iv2)
    assert np.allclose((mat_Iv1 + mat_Iv2)[:, :], res.petscmat[:, :], rtol=1e-14)

    # Linear combination of BaseFormOperator (1-form)
    alpha = 0.5
    res = assemble(alpha * If1 + alpha**2 * If2 - alpha ** 3 * If3)
    a = assemble(If1)
    b = assemble(If2)
    c = assemble(If3)
    res2 = assemble(alpha * a + alpha**2 * b - alpha**3 * c)
    assert np.allclose(res2.dat.data, res.dat.data)

    # Linear combination of BaseFormOperator (2-form)
    res = assemble(alpha * Iv1 - alpha**2 * Iv2)
    assert np.allclose(alpha * mat_Iv1.petscmat[:, :] - alpha**2 * mat_Iv2.petscmat[:, :], res.petscmat[:, :], rtol=1e-14)

    # Check product of BaseFormOperators
    res = assemble(If1 * If2)
    b = assemble(If2)
    # Check product of BaseFormOperator and Coefficient
    res2 = assemble(If1 * b)
    a = assemble(If1)
    # Exact solution
    res3 = assemble(a * b)
    assert np.allclose(res.dat.data, res2.dat.data)
    assert np.allclose(res2.dat.data, res3.dat.data)

    """
    # Multiplication involving BaseFormOperators
    v2 = TrialFunction(V2)
    Iv3 = Interp(v2, V1)
    mat_Iv3 = assemble(Iv3)
    res = assemble(Iv1 * Iv3)
    assert np.allclose(mat_Iv1.petscmat.matMult(mat_Iv3.petscmat)[:, :], res.petscmat[:, :], rtol=1e-14)

    res = assemble(Iv3 * If1)
    # Problem with random order of ufl.Product
    # res2 = assemble(Iv3 * b)
    res3 = assemble(action(Iv3, If1))
    res4 = assemble(action(Iv3, a))
    # FIXME: Remove below
    assert np.allclose(res.dat.data, res3.dat.data)
    #assert np.allclose(res.dat.data, res2.dat.data)
    #assert np.allclose(res2.dat.data, res3.dat.data)
    assert np.allclose(res3.dat.data, res4.dat.data)

    res = assemble(alpha * Iv1 * If1 + alpha**2 * Iv2 * (If1 - If2))
    res2 = assemble(alpha * action(Iv1, If1) + alpha**2 * action(Iv2, (If1 - If2)))
    a = assemble(action(Iv1, If1))
    b = assemble(action(Iv2, If1))
    c = assemble(action(Iv2, If2))
    res3 = alpha * a.petscmat[:, :] + alpha**2 * (b.petscmat[:, :] - c.petscmat[:, :])
    assert np.allclose(res.petscmat[:, :], res2.petscmat[:, :], rtol=1e-14)
    assert np.allclose(res2.petscmat[:, :], res3, rtol=1e-14)

    # with pytest.raises(ValueError):
    #    pass
    """


def test_check_identity(mesh):
    V2 = FunctionSpace(mesh, "CG", 2)
    V1 = FunctionSpace(mesh, "CG", 1)
    v2 = TestFunction(V2)
    v1 = TestFunction(V1)
    a = assemble(Interp(v1, v2*dx))
    b = assemble(v1*dx)
    assert np.allclose(a.dat.data, b.dat.data)


def test_solve_interp_f(mesh):
    V1 = FunctionSpace(mesh, "CG", 1)
    V2 = FunctionSpace(mesh, "DG", 0)
    x, y = SpatialCoordinate(mesh)

    # The space of interpolation (V2) is voluntarily chosen to be of poorer quality than V1.
    # The reasons is that the form is defined on V1 so if we interpolate
    # in a higher-order space we won't see the impact of the interpolation.
    w = TestFunction(V1)
    u = Function(V1)
    f1 = Function(V1).interpolate(cos(x)*sin(y))

    # -- Exact solution with a source term interpolated into DG0
    f2 = interpolate(f1, V2)
    F = inner(grad(w), grad(u))*dx + inner(u, w)*dx - inner(f2, w)*dx
    solve(F == 0, u)

    # -- Solution where the source term is interpolated via `ufl.Interp`
    u2 = Function(V1)
    If = Interp(f1, V2)
    # This requires assembling If
    F2 = inner(grad(w), grad(u2))*dx + inner(u2, w)*dx - inner(If, w)*dx
    solve(F2 == 0, u2)
    assert np.allclose(u.dat.data, u2.dat.data)


def test_solve_interp_u(mesh):
    V1 = FunctionSpace(mesh, "CG", 1)
    x, y = SpatialCoordinate(mesh)

    w = TestFunction(V1)
    u = Function(V1)
    f = Function(V1).interpolate(cos(x)*sin(y))

    # -- Exact solution
    F = inner(grad(w), grad(u))*dx + inner(u, w)*dx - inner(f, w)*dx
    solve(F == 0, u)

    # -- Non mat-free case not supported yet => Need to be able to get the Interpolation matrix -- #
    """
    # -- Solution where the source term is interpolated via `ufl.Interp`
    u2 = Function(V1)
    # Iu is the identity
    Iu = Interp(u2, V1)
    # This requires assembling the Jacobian of Iu
    F2 = inner(grad(w), grad(u))*dx + inner(Iu, w)*dx - inner(f, w)*dx
    solve(F2 == 0, u2)
    """

    # -- Solution where u2 is interpolated via `ufl.Interp` (mat-free)
    u2 = Function(V1)
    # Iu is the identity
    Iu = Interp(u2, V1)
    # This requires assembling the action the Jacobian of Iu
    F2 = inner(grad(w), grad(u))*dx + inner(Iu, w)*dx - inner(f, w)*dx
    solve(F2 == 0, u2, solver_parameters={"mat_type": "matfree",
                                          "ksp_type": "cg",
                                          "pc_type": "none"})
    assert np.allclose(u.dat.data, u2.dat.data)

    # Same problem with grad(Iu) instead of grad(Iu)
    u2 = Function(V1)
    # Iu is the identity
    Iu = Interp(u2, V1)
    # This requires assembling the action the Jacobian of Iu
    F2 = inner(grad(w), grad(Iu))*dx + inner(Iu, w)*dx - inner(f, w)*dx
    solve(F2 == 0, u2, solver_parameters={"mat_type": "matfree",
                                          "ksp_type": "cg",
                                          "pc_type": "none"})
    assert np.allclose(u.dat.data, u2.dat.data)
