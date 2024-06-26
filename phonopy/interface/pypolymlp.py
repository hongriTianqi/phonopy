"""Polynomial machine learning potential interface."""

# Copyright (C) 2024 Atsushi Togo
# All rights reserved.
#
# This file is part of phonopy.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# * Redistributions of source code must retain the above copyright
#   notice, this list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in
#   the documentation and/or other materials provided with the
#   distribution.
#
# * Neither the name of the phonopy project nor the names of its
#   contributors may be used to endorse or promote products derived
#   from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

from phonopy.structure.atoms import PhonopyAtoms

try:
    from pypolymlp.mlp_dev.pypolymlp import Pypolymlp
except ImportError:
    Pypolymlp = Any


@dataclass
class PypolymlpParams:
    """Parameters for pypolymlp.

    cutoff : flaot, optional
        Cutoff radius. Default is 8.0.
    model_type : int, optional
        Polynomial function type. Default is 3. model_type = 1: Linear
        polynomial of polynomial invariants model_type = 2: Polynomial of
        polynomial invariants model_type = 3: Polynomial of pair invariants
                        + linear polynomial of polynomial invariants
        model_type = 4: Polynomial of pair and second-order invariants
                        + linear polynomial of polynomial invariants
    max_p : int, optional
        Order of polynomial function. Default is 2.
    gtinv_order : int, optional
        Maximum order of polynomial invariants. Default is 3.
    gtinv_maxl: Sequence[int], optional
        Maximum angular numbers of polynomial invariants. [maxl for order=2,
        maxl for order=3, ...] Default is (8, 8).
    gaussian_params1, gaussian_params2 : Sequence[float, float, int], optional
        Parameters for exp[- param1 * (r - param2)**2]. Parameters are given as
        np.linspace(p[0], p[1], p[2]), where p[0], p[1], and p[2] are given by
        gaussian_params1 and gaussian_params2. Normally it is recommended to
        modify only gaussian_params2. Default is (1.0, 1.0, 1) and (0.0, 7.0,
        10), respectively.
    atom_energies: dict[str, float], optional
        Atomic energies specified by dictionary, e.g., {'Si': -0.35864636, 'O':
        -0.95743902}, where the order is irrelevant. Default is None, which
        gives zero energies for all atoms.

    """

    cutoff: float = 8.0
    model_type: int = 3
    max_p: int = 2
    gtinv_order: int = 3
    gtinv_maxl: Sequence[int] = (8, 8)
    gaussian_params1: Sequence[float, float, int] = (1.0, 1.0, 1)
    gaussian_params2: Sequence[float, float, int] = (0.0, 7.0, 10)
    atom_energies: Optional[dict[str, float]] = None


@dataclass
class PypolymlpData:
    """Dataset for pypolymlp input.

    displacements : np.ndarray
        Displacements of atoms. shape=(n, natoms, 3)
    forces : np.ndarray
        Displacements of atoms. shape=(n, natoms, 3)
    supercell_energies : np.ndarray, optional
        Energies of supercells. shape=(n,)

    """

    displacements: np.ndarray
    forces: np.ndarray
    supercell_energies: np.ndarray


def develop_polymlp(
    supercell: PhonopyAtoms,
    train_data: PypolymlpData,
    test_data: PypolymlpData,
    params: Optional[PypolymlpParams] = None,
    verbose: bool = False,
):
    """Develop polynomial MLPs of pypolymlp.

    Parameters
    ----------
    supercell : PhonopyAtoms
        Supercell structure.
    train_data : PyPolymlpData
        Training dataset.
    test_data : PyPolymlpData
        Test dataset.
    params : PypolymlpParams, optional
        Parameters for pypolymlp. Default is None.
    verbose : bool, optional
        Verbosity. Default is False.

    Returns
    -------
    polymlp : Pypolymlp
        Pypolymlp object.

    """
    try:
        from pypolymlp.mlp_dev.pypolymlp import Pypolymlp
        from pypolymlp.utils.phonopy_utils import phonopy_cell_to_st_dict
    except ImportError as exc:
        raise ModuleNotFoundError("Pypolymlp python module was not found.") from exc

    if params is None:
        _params = PypolymlpParams()
    else:
        _params = params

    if _params.atom_energies is None:
        elements_energies = {s: 0.0 for s in supercell.symbols}
    else:
        elements_energies = {s: _params.atom_energies[s] for s in supercell.symbols}
    polymlp = Pypolymlp()
    polymlp.set_params(
        elements=list(elements_energies.keys()),
        cutoff=_params.cutoff,
        model_type=_params.model_type,
        max_p=_params.max_p,
        gtinv_order=_params.gtinv_order,
        gtinv_maxl=_params.gtinv_maxl,
        gaussian_params2=_params.gaussian_params2,
        atomic_energy=list(elements_energies.values()),
    )
    polymlp.set_datasets_displacements(
        train_data.displacements.transpose(0, 2, 1),
        train_data.forces.transpose(0, 2, 1),
        train_data.supercell_energies,
        test_data.displacements.transpose(0, 2, 1),
        test_data.forces.transpose(0, 2, 1),
        test_data.supercell_energies,
        phonopy_cell_to_st_dict(supercell),
    )
    polymlp.run(verbose=verbose)
    return polymlp


def evalulate_polymlp(
    polymlp: Pypolymlp,  # type: ignore
    supercells_with_displacements: list[PhonopyAtoms],
):
    """Run force calculation using pypolymlp.

    Parameters
    ----------
    polymlp : Pypolymlp
        Pypolymlp object.
    supercells_with_displacements : Sequence[PhonopyAtoms]
        Sequence of supercells with displacements.

    Returns
    -------
    energies : np.ndarray
        Energies of supercells. shape=(n,)
    forces : np.ndarray
        Forces of supercells. shape=(n, natoms, 3)
    stresses : np.ndarray
        Stresses of supercells (xx, yy, zz, xy, yz, zx). shape=(n, 6)

    """
    try:
        from pypolymlp.calculator.properties import Properties
        from pypolymlp.utils.phonopy_utils import phonopy_cell_to_st_dict
    except ImportError as exc:
        raise ModuleNotFoundError("Pypolymlp python module was not found.") from exc

    prop = Properties(params_dict=polymlp.parameters, coeffs=polymlp.coeffs)
    energies, forces, stresses = prop.eval_multiple(
        [phonopy_cell_to_st_dict(scell) for scell in supercells_with_displacements]
    )
    energies = np.array(energies, dtype="double")
    forces = np.array(np.transpose(forces, (0, 2, 1)), dtype="double", order="C")
    stresses = np.array(stresses, dtype="double", order="C")
    return energies, forces, stresses
