from firedrake import *
from pyadjoint import (ReducedFunctional, get_working_tape, stop_annotating,
                       pause_annotation, Control)
import numpy as np
import os
import pytest


@pytest.fixture(autouse=True, scope="module")
def handle_annotation():
    from firedrake_adjoint import annotate_tape, continue_annotation
    if not annotate_tape():
        continue_annotation()
    yield
    # Since importing firedrake_adjoint modifies a global variable, we need to
    # pause annotations at the end of the module
    annotate = annotate_tape()
    if annotate:
        pause_annotation()


def adjoint_example(mesh):
    # This example is designed to exercise all the block types for which
    # the disk checkpointer does something.
    dg_space = FunctionSpace(mesh, "DG", 1)
    cg_space = FunctionSpace(mesh, "CG", 2)
    W = dg_space * cg_space

    w = Function(W)

    x, y = SpatialCoordinate(mesh)
    # InterpolateBlock
    m = interpolate(sin(4*pi*x)*cos(4*pi*y), cg_space)

    u, v = w.split()
    # FunctionAssignBlock, FunctionMergeBlock
    v.assign(m)
    # FunctionSplitBlock, GenericSolveBlock
    u.project(v)

    # AssembleBlock
    J = assemble((u - v)**2 * dx)

    Jhat = ReducedFunctional(J, Control(m))

    with stop_annotating():
        m_new = interpolate(sin(4*pi*x)*cos(4*pi*y), cg_space)
    checkpointer = get_working_tape()._checkpoint_metadata
    init_file_timestamp = os.stat(checkpointer.init_checkpoint_file).st_mtime
    current_file_timestamp = os.stat(checkpointer.current_checkpoint_file).st_mtime
    Jnew = Jhat(m_new)
    # Check that any new disk checkpoints are written to the correct file.
    assert init_file_timestamp == os.stat(checkpointer.init_checkpoint_file).st_mtime
    assert current_file_timestamp < os.stat(checkpointer.current_checkpoint_file).st_mtime

    assert np.allclose(J, Jnew)

    grad_Jnew = Jhat.derivative()

    return Jnew, grad_Jnew


@pytest.mark.skipcomplex
# Waiting on stable parallel decompositions through disk checkpointing.
@pytest.mark.xfail
# A serial version of this test is included in the pyadjoint tests.
@pytest.mark.parallel(nprocs=3)
def test_disk_checkpointing():
    from firedrake_adjoint import enable_disk_checkpointing, \
        checkpointable_mesh, pause_disk_checkpointing
    tape = get_working_tape()
    tape.clear_tape()
    enable_disk_checkpointing()

    mesh = checkpointable_mesh(UnitSquareMesh(10, 10, name="mesh"))
    J_disk, grad_J_disk = adjoint_example(mesh)
    tape.clear_tape()
    pause_disk_checkpointing()

    J_mem, grad_J_mem = adjoint_example(mesh)

    assert np.allclose(J_disk, J_mem)
    assert np.allclose(assemble((grad_J_disk - grad_J_mem)**2*dx), 0.0)
    tape.clear_tape()


@pytest.mark.skipcomplex
def test_disk_checkpointing_successive_writes():
    from firedrake_adjoint import enable_disk_checkpointing, \
        checkpointable_mesh, pause_disk_checkpointing
    tape = get_working_tape()
    tape.clear_tape()
    enable_disk_checkpointing()

    mesh = checkpointable_mesh(UnitSquareMesh(1, 1))

    cg_space = FunctionSpace(mesh, "CG", 1)
    u = Function(cg_space, name='u')
    v = Function(cg_space, name='v')

    u.assign(1.)
    v.assign(v + 2.*u)
    v.assign(v + 3.*u)

    J = assemble(v*dx)
    Jhat = ReducedFunctional(J, Control(u))
    assert np.allclose(J, Jhat(1))
    pause_disk_checkpointing()
    tape.clear_tape()
