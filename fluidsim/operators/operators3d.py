"""Operators 3d (:mod:`fluidsim.operators.operators3d`)
=======================================================

Provides

.. autoclass:: OperatorsPseudoSpectral3D
   :members:
   :private-members:

"""

from math import pi
from copy import deepcopy

import numpy as np

from transonic import boost, Array, Transonic
from fluiddyn.util import mpi
from fluiddyn.util.mpi import nb_proc, rank
from fluidfft.fft3d.operators import OperatorsPseudoSpectral3D as _Operators

from fluidsim.base.setofvariables import SetOfVariables
from fluidsim.base.params import Parameters

from .operators2d import OperatorsPseudoSpectral2D as OpPseudoSpectral2D
from .. import _is_testing

ts = Transonic()

Asov = Array[np.complex128, "4d"]
Aui8 = Array[np.uint8, "3d"]
Ac = Array[np.complex128, "3d"]
Af = Array[np.float64, "3d"]


@boost
def dealiasing_setofvar(sov: Asov, where_dealiased: Aui8):
    """Dealiasing 3d setofvar object.

    Parameters
    ----------

    sov : 4d ndarray
        A set of variables array.

    where_dealiased : 3d ndarray
        A 3d array of "booleans" (actually uint8).

    """
    nk, n0, n1, n2 = sov.shape

    for i0 in range(n0):
        for i1 in range(n1):
            for i2 in range(n2):
                if where_dealiased[i0, i1, i2]:
                    for ik in range(nk):
                        sov[ik, i0, i1, i2] = 0.0


@boost
def dealiasing_variable(ff_fft: Ac, where_dealiased: Aui8):
    """Dealiasing 3d array"""
    n0, n1, n2 = ff_fft.shape

    for i0 in range(n0):
        for i1 in range(n1):
            for i2 in range(n2):
                if where_dealiased[i0, i1, i2]:
                    ff_fft[i0, i1, i2] = 0.0


def dealiasing_setofvar_numpy(sov: Asov, where_dealiased: Aui8):
    for i in range(sov.shape[0]):
        sov[i][np.nonzero(where_dealiased)] = 0.0


def dealiasing_variable_numpy(ff_fft: Ac, where_dealiased: Aui8):
    ff_fft[np.nonzero(where_dealiased)] = 0.0


if not ts.is_transpiling and not ts.is_compiled and not _is_testing:
    # for example if Pythran is not available
    dealiasing_variable = dealiasing_variable_numpy
    dealiasing_setofvar = dealiasing_setofvar_numpy
elif ts.is_transpiling:
    _Operators = object


if nb_proc > 1:
    MPI = mpi.MPI
    comm = mpi.comm


@boost
class OperatorsPseudoSpectral3D(_Operators):
    """Provides fast Fourier transform functions and 3D operators.

    Uses fft operators that implement the methods:

    - ifft
    - fft
    - get_shapeX_loc
    - get_shapeX_seq
    - get_shapeK_loc
    - get_shapeK_seq
    - get_dimX_K
    - get_seq_indices_first_K

    - get_k_adim_loc
    - sum_wavenumbers
    - build_invariant_arrayK_from_2d_indices12X

    """

    Kx: Af
    Ky: Af
    inv_K_square_nozero: Af
    inv_Kh_square_nozero: Af

    @classmethod
    def _create_default_params(cls):
        params = Parameters(tag="params", attribs={"ONLY_COARSE_OPER": False})
        cls._complete_params_with_default(params)
        return params

    @staticmethod
    def _complete_params_with_default(params):
        """This static method is used to complete the *params* container.
        """
        attribs = {
            "type_fft": "default",
            "type_fft2d": "sequential",
            "coef_dealiasing": 2.0 / 3,
            "nx": 48,
            "ny": 48,
            "nz": 48,
            "Lx": 2 * pi,
            "Ly": 2 * pi,
            "Lz": 2 * pi,
            "NO_SHEAR_MODES": False,
        }
        params._set_child("oper", attribs=attribs)
        params.oper._set_doc(
            """

See the `documentation of fluidfft <http://fluidfft.readthedocs.io>`_ (in
particular of the `3d operator class
<http://fluidfft.readthedocs.io/en/latest/generated/fluidfft.fft3d.operators.html>`_).

type_fft: str

    Method for the FFT (as defined by fluidfft).

type_fft2d: str

    Method for the 2d FFT.

coef_dealiasing: float

    dealiasing coefficient.

nx: int

    Number of points over the x-axis (last dimension in the physical space).

ny: int

    Number of points over the y-axis (second dimension in the physical space).

nz: int

    Number of points over the z-axis (first dimension in the physical space).

Lx, Ly and Lz: float

    Length of the edges of the numerical domain.

"""
        )

    def __init__(self, params=None):

        self.params = params
        self.axes = ("z", "y", "x")

        params.oper.nx = int(params.oper.nx)
        params.oper.ny = int(params.oper.ny)
        params.oper.nz = int(params.oper.nz)

        if params.ONLY_COARSE_OPER:
            nx = ny = nz = 4
        else:
            nx = params.oper.nx
            ny = params.oper.ny
            nz = params.oper.nz

        super().__init__(
            nx,
            ny,
            nz,
            params.oper.Lx,
            params.oper.Ly,
            params.oper.Lz,
            fft=params.oper.type_fft,
            coef_dealiasing=params.oper.coef_dealiasing,
        )

        # problem here type_fft
        params2d = deepcopy(params)
        params2d.oper.type_fft = params2d.oper.type_fft2d
        fft = params2d.oper.type_fft

        if (
            any([fft.startswith(s) for s in ["fluidfft.fft2d.", "fft2d."]])
            or fft in ("default", "sequential")
            or fft is None
        ):
            self.oper2d = OpPseudoSpectral2D(params2d)
        else:
            raise ValueError

        self.ifft2 = self.ifft2d = self.oper2d.ifft2
        self.fft2 = self.fft2d = self.oper2d.fft2
        if nb_proc > 1:
            self.iK0loc_start = self.seq_indices_first_K[0]
            self.nk0_loc, self.nk1_loc, self.nk2_loc = self.shapeK_loc

        try:
            NO_SHEAR_MODES = self.params.oper.NO_SHEAR_MODES
        except AttributeError:
            pass
        else:
            if NO_SHEAR_MODES:
                COND_NOSHEAR = self.Kx ** 2 + self.Ky ** 2 == 0.0
                where_dealiased = np.logical_or(
                    COND_NOSHEAR, self.where_dealiased
                )
                self.where_dealiased = np.array(where_dealiased, dtype=np.uint8)

    def build_invariant_arrayX_from_2d_indices12X(self, arr2d):
        """Build a 3D array from a 2D array"""
        return self._op_fft.build_invariant_arrayX_from_2d_indices12X(
            self.oper2d, arr2d
        )

    def build_invariant_arrayK_from_2d_indices12X(self, arr2d):
        """Build a 3D array from a 2D array"""
        return self._op_fft.build_invariant_arrayK_from_2d_indices12X(
            self.oper2d, arr2d
        )

    def dealiasing(self, *args):
        """Dealiasing of SetOfVariables or np.ndarray"""
        for thing in args:
            if isinstance(thing, SetOfVariables):
                dealiasing_setofvar(thing, self.where_dealiased)
            elif isinstance(thing, np.ndarray):
                dealiasing_variable(thing, self.where_dealiased)

    def put_coarse_array_in_array_fft(
        self, arr_coarse, arr, oper_coarse, shapeK_loc_coarse
    ):
        """Put the values contained in a coarse array in an array.

        Both arrays are in Fourier space.

        """
        if arr.ndim == 4:
            if rank == 0:
                if arr_coarse.ndim != 4:
                    raise ValueError

            for ikey in range(arr.shape[0]):
                if rank == 0:
                    arr3d_coarse = arr_coarse[ikey]
                else:
                    arr3d_coarse = None
                self.put_coarse_array_in_array_fft(
                    arr3d_coarse, arr[ikey], oper_coarse, shapeK_loc_coarse
                )
            return

        nkzc, nkyc, nkxc = shapeK_loc_coarse

        if nb_proc > 1:
            nK2 = self.shapeK_seq[2]
            if mpi.rank == 0:
                fck_fft = arr_coarse
            nK0c, nK1c, nK2c = shapeK_loc_coarse

            for ik0c in range(nK0c):
                ik1c = 0
                ik2c = 0
                rank_ik, ik0loc, ik1loc, ik2loc = self.where_is_wavenumber(
                    ik0c, ik1c, ik2c
                )

                if mpi.rank == 0:
                    fc1D = fck_fft[ik0c, :, :]

                if rank_ik != 0:
                    # message fc1D
                    if mpi.rank == rank_ik:
                        fc1D = np.empty([nK1c, nK2c], dtype=np.complex128)
                    if mpi.rank == 0 or mpi.rank == rank_ik:
                        fc1D = np.ascontiguousarray(fc1D)
                    if mpi.rank == 0:
                        mpi.comm.Send(
                            [fc1D, mpi.MPI.COMPLEX], dest=rank_ik, tag=ik0c
                        )
                    elif mpi.rank == rank_ik:
                        mpi.comm.Recv([fc1D, mpi.MPI.COMPLEX], source=0, tag=ik0c)
                if mpi.rank == rank_ik:
                    # copy
                    for ik2c in range(nK2c):
                        if ik2c <= nK2c / 2.0:
                            ik2 = ik2c
                        else:
                            k2nodim = ik2c - nK2c
                            ik2 = k2nodim + nK2
                        arr[ik0loc, 0:nK1c, ik2] = fc1D[:, ik2c]

        else:
            nkz, nky, nkx = self.shapeK_seq
            for ikzc in range(nkzc):
                ikz = _ik_from_ikc(ikzc, nkzc, nkz)
                for ikyc in range(nkyc):
                    iky = _ik_from_ikc(ikyc, nkyc, nky)
                    for ikxc in range(nkxc):
                        arr[ikz, iky, ikxc] = arr_coarse[ikzc, ikyc, ikxc]

    def coarse_seq_from_fft_loc(self, f_fft, shapeK_loc_coarse):
        """Return a coarse field in K space."""
        nkzc, nkyc, nkxc = shapeK_loc_coarse
        if nb_proc > 1:
            if self.shapeK_seq[1:2] != self.shapeK_loc[1:2]:
                raise NotImplementedError()

            nk0c, nk1c, nk2c = shapeK_loc_coarse
            self.iK0loc_start_rank = np.array(comm.allgather(self.iK0loc_start))
            nk2_loc = self.shapeK_loc[2]
            nk2_loc_rank = np.array(comm.allgather(nk2_loc))
            a = nk2_loc_rank
            self.SAME_SIZE_IN_ALL_PROC = (a >= a.max()).all()
            fc_fft = np.empty([nk0c, nk1c, nk2c], np.complex128)
            nk0, nk1, nk2 = self.shapeK_loc
            f1d_temp = np.empty([nk1c, nk2c], np.complex128)

            for ik0c in range(nk0c):
                ik1c = 0
                ik2c = 0
                rank_ik, ik0loc, ik1loc, ik1loc = self.where_is_wavenumber(
                    ik0c, ik1c, ik2c
                )
                if rank == rank_ik:
                    # create f1d_temp
                    for ik2c in range(nk2c):
                        if ik2c <= nk2c / 2:
                            ik2 = ik2c
                        else:
                            k2nodim = ik2c - nk2c
                            ik2 = k2nodim + nk2
                        f1d_temp[:, ik2c] = f_fft[ik0loc, 0:nk1c, ik2]

                if rank_ik != 0:
                    # message f1d_temp
                    if rank == 0:
                        comm.Recv(
                            [f1d_temp, MPI.DOUBLE_COMPLEX],
                            source=rank_ik,
                            tag=ik0c,
                        )
                    elif rank == rank_ik:
                        comm.Send(
                            [f1d_temp, MPI.DOUBLE_COMPLEX], dest=0, tag=ik0c
                        )
                if rank == 0:
                    # copy into fc_fft
                    fc_fft[ik0c] = f1d_temp.copy()

        else:
            fc_fft = np.empty(shapeK_loc_coarse, np.complex128)
            nkz, nky, nkx = self.shapeK_seq
            for ikzc in range(nkzc):
                ikz = _ik_from_ikc(ikzc, nkzc, nkz)
                for ikyc in range(nkyc):
                    iky = _ik_from_ikc(ikyc, nkyc, nky)
                    for ikxc in range(nkxc):
                        fc_fft[ikzc, ikyc, ikxc] = f_fft[ikz, iky, ikxc]
        return fc_fft

    def where_is_wavenumber(self, ik0, ik1, ik2):
        nk0_seq, nk1_seq, nk2_seq = self.shapeK_seq

        if ik0 >= nk0_seq:
            raise ValueError("not good :-) ik0_seq >= nk0_seq")

        if nb_proc == 1:
            rank_k = 0
            ik0_loc = ik0
        else:
            if self.SAME_SIZE_IN_ALL_PROC:
                rank_k = int(np.floor(float(ik0) / self.nk0_loc))
                if ik0 >= self.nk0_loc * nb_proc:
                    raise ValueError(
                        "not good :-) ik0_seq >= self.nk0_loc * mpi.nb_proc\n"
                        "ik0_seq, self.nk0_loc, mpi.nb_proc = "
                        f"{ik0}, {self.nk0_loc}, {nb_proc}"
                    )

            else:
                rank_k = 0
                while rank_k < self.nb_proc - 1 and (
                    not (
                        self.iK0loc_start_rank[rank_k] <= ik0
                        and ik0 < self.iK0loc_start_rank[rank_k + 1]
                    )
                ):
                    rank_k += 1

            ik0_loc = ik0 - self.iK0loc_start_rank[rank_k]

        ik1_loc = ik1
        if ik1_loc < 0:
            ik1_loc = self.nk1_loc + ik1_loc

        ik2_loc = ik2
        if ik2_loc < 0:
            ik2_loc = self.nk2_loc + ik2_loc

        return rank_k, ik0_loc, ik1_loc, ik2_loc

    @boost
    def urudfft_from_vxvyfft(self, vx_fft: Ac, vy_fft: Ac):
        """Compute toroidal and poloidal horizontal velocities.

        urx_fft, ury_fft contain shear modes!

        """
        inv_Kh_square_nozero = self.Kx ** 2 + self.Ky ** 2
        inv_Kh_square_nozero[inv_Kh_square_nozero == 0] = 1e-14
        inv_Kh_square_nozero = 1 / inv_Kh_square_nozero

        kdotu_fft = self.Kx * vx_fft + self.Ky * vy_fft
        udx_fft = kdotu_fft * self.Kx * inv_Kh_square_nozero
        udy_fft = kdotu_fft * self.Ky * inv_Kh_square_nozero

        urx_fft = vx_fft - udx_fft
        ury_fft = vy_fft - udy_fft

        return urx_fft, ury_fft, udx_fft, udy_fft

    @boost
    def divhfft_from_vxvyfft(self, vx_fft: Ac, vy_fft: Ac):
        """Compute the horizontal divergence in spectral space."""
        return 1j * (self.Kx * vx_fft + self.Ky * vy_fft)

    @boost
    def vxvyfft_from_rotzfft(self, rotz_fft: Ac):

        inv_Kh_square_nozero = self.Kx ** 2 + self.Ky ** 2
        inv_Kh_square_nozero[inv_Kh_square_nozero == 0] = 1e-14
        inv_Kh_square_nozero = 1 / inv_Kh_square_nozero

        vx_fft = 1j * self.Ky * inv_Kh_square_nozero * rotz_fft
        vy_fft = -1j * self.Kx * inv_Kh_square_nozero * rotz_fft
        return vx_fft, vy_fft

    def get_grid1d_seq(self, axe="x"):

        if axe not in ("x", "y", "z"):
            raise ValueError

        if self.params.ONLY_COARSE_OPER:
            number_points = getattr(self.params.oper, "n" + axe)
            length = getattr(self, "L" + axe)
            return np.linspace(0, length, number_points)
        else:
            return getattr(self, axe + "_seq")

    def project_fft_on_realX(self, f_fft):
        return self.fft(self.ifft(f_fft))

    def _ikxyzseq_from_ik012rank(self, ik0, ik1, ik2, rank=0):
        if self._is_mpi_lib:
            # much more complicated in this case
            raise NotImplementedError
        dimX_K = self._op_fft.get_dimX_K()
        if dimX_K == (0, 1, 2):
            ikz, iky, ikx = ik0, ik1, ik2
        else:
            raise NotImplementedError
        return ikx, iky, ikz

    def _ik012rank_from_ikxyzseq(self, ikx, iky, ikz):
        if self._is_mpi_lib:
            # much more complicated in this case
            raise NotImplementedError
        rank_k = 0
        dimX_K = self._op_fft.get_dimX_K()
        if dimX_K == (0, 1, 2):
            ik0, ik1, ik2 = ikz, iky, ikx
        else:
            raise NotImplementedError
        return ik0, ik1, ik2, rank_k

    def _kadim_from_ikxyzseq(self, ikx, iky, ikz):
        kx_adim = ikx
        ky_adim = _kadim_from_ik(iky, self.ny)
        kz_adim = _kadim_from_ik(ikz, self.nz)
        return kx_adim, ky_adim, kz_adim

    def _ikxyzseq_from_kadim(self, kx_adim, ky_adim, kz_adim):
        ikx = kx_adim
        iky = _ik_from_kadim(ky_adim, self.ny)
        ikz = _ik_from_kadim(kz_adim, self.nz)
        return ikx, iky, ikz

    def kadim_from_ik012rank(self, ik0, ik1, ik2, rank=0):
        ikx, iky, ikz = self._ikxyzseq_from_ik012rank(ik0, ik1, ik2, rank)
        return self._kadim_from_ikxyzseq(ikx, iky, ikz)

    def ik012rank_from_kadim(self, kx_adim, ky_adim, kz_adim):
        ikx, iky, ikz = self._ikxyzseq_from_kadim(kx_adim, ky_adim, kz_adim)
        return self._ik012rank_from_ikxyzseq(ikx, iky, ikz)

    def set_value_spect(
        self, arr_fft, value, kx_adim, ky_adim, kz_adim, from_rank=0
    ):
        ik0, ik1, ik2, rank_k = self.ik012rank_from_kadim(
            kx_adim, ky_adim, kz_adim
        )
        if mpi.rank != rank_k or from_rank != 0:
            raise NotImplementedError
        # print("-" * 20)
        # print(f"ik0, ik1, ik2             = ({ik0:4d}, {ik1:4d}, {ik2:4d})")
        arr_fft[ik0, ik1, ik2] = value

    def get_value_spect(self, arr_fft, kx_adim, ky_adim, kz_adim, to_rank=0):
        ik0, ik1, ik2, rank_k = self.ik012rank_from_kadim(
            kx_adim, ky_adim, kz_adim
        )
        if mpi.rank != rank_k or to_rank != 0:
            raise NotImplementedError
        return arr_fft[ik0, ik1, ik2]


def _ik_from_ikc(ikc, nkc, nk):
    if ikc <= nkc / 2.0:
        ik = ikc
    else:
        knodim = ikc - nkc
        ik = knodim + nk
    return ik


def _kadim_from_ik(ik, nk, first=False):
    if first or ik <= nk // 2:
        return ik
    return ik - nk


def _ik_from_kadim(k_adim, nk, first=False):
    if first or k_adim >= 0:
        return k_adim
    return nk + k_adim


if __name__ == "__main__":
    n = 4

    p = OperatorsPseudoSpectral3D._create_default_params()

    p.oper.nx = n
    p.oper.ny = 2 * n
    p.oper.nz = 4 * n

    # p.oper.type_fft = 'fftwpy'
    p.oper.type_fft2d = "fft2d.with_pyfftw"

    oper = OperatorsPseudoSpectral3D(params=p)

    field = np.ones(oper.shapeX_loc)

    print(oper.shapeX_loc)
    print(oper.oper2d.shapeX_loc)

    field_fft = oper.fft3d(field)

    assert field_fft.shape == oper.shapeK_loc

    oper.project_perpk3d(field_fft, field_fft, field_fft)

    a2d = np.arange(oper.nx * oper.ny).reshape(oper.oper2d.shapeX_loc)
    a3d = oper.build_invariant_arrayX_from_2d_indices12X(a2d)
