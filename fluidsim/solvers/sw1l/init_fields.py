"""Initialisation of the fields (:mod:`fluiddyn.simul.base.init_fields`)
========================================================================

.. currentmodule:: fluiddyn.simul.sw1l.init_fields

Provides:

.. autoclass:: InitFieldsNoise
   :members:
   :private-members:

.. autoclass:: InitFieldsWave
   :members:
   :private-members:

.. autoclass:: InitFieldsVortexGrid
   :members:
   :private-members:

.. autoclass:: InitFieldsSW1L
   :members:
   :private-members:

"""


import numpy as np

from fluidsim.base.init_fields import InitFieldsBase, SpecificInitFields

from fluidsim.solvers.ns2d.init_fields import (
    InitFieldsNoise as InitFieldsNoiseNS2D)

from fluidsim.solvers.ns2d.init_fields import InitFieldsJet, InitFieldsDipole


class InitFieldsNoise(InitFieldsNoiseNS2D):

    def __call__(self):
        rot_fft, ux_fft, uy_fft = self.compute_rotuxuy_fft()
        self.sim.state.init_from_uxuyfft(ux_fft, uy_fft)


class InitFieldsWave(SpecificInitFields):
    tag = 'wave'

    @classmethod
    def _complete_params_with_default(cls, params):
        super(InitFieldsWave, cls)._complete_params_with_default(params)
        params.init_fields._set_child(cls.tag, attribs={
            'eta_max': 1.,
            'ikx': 2})

    def __call__(self):
        oper = self.sim.oper

        ikx = self.sim.params.init_fields.wave.ikx
        eta_max = self.sim.params.init_fields.wave.eta_max

        kx = oper.deltakx * ikx
        eta_fft = np.zeros_like(self.sim.state('eta_fft'))
        cond = np.logical_and(oper.KX == kx, oper.KY == 0.)
        eta_fft[cond] = eta_max
        oper.project_fft_on_realX(eta_fft)

        self.sim.state.init_from_etafft(eta_fft)


class InitFieldsVortexGrid(SpecificInitFields):
    """
        Initializes the vorticity field with n_vort^2 Gaussian vortices in a square grid.
        Vortices are randomly assigned clockwise / anti-clockwise directions;
        with equal no of vortices for each direction.

        Parameters
        ----------
        omega_max : Max vorticity of a single vortex at its center
        n_vort : No. of vortices along one edge of the square grid, should be       even integer
        sd : Standard Deviation of the gaussian, optional
             If not specified, follows six-sigma rule based on half vortex spacing

    """
    tag = 'vortex_grid'
    
    @classmethod
    def _complete_params_with_default(cls, params):
        super(InitFieldsVortexGrid, cls)._complete_params_with_default(params)
        params.init_fields._set_child(cls.tag, attribs={
            'omega_max': 1.,
            'n_vort': 8,
            'sd': 0.})

    def __call__(self):
        rot = self.vortex_grid_shape()
        rot_fft = self.sim.oper.fft2(rot)
        self.sim.init_from_rotfft(rot_fft)
        
    def vortex_grid_shape(self):
        oper = self.sim.oper

        def wz_gaussian(XX, YY, sign, Amp=1., sigma=10.):
            return (sign * Amp * np.exp(- (XX**2 + YY**2) / (2 * sigma**2)))
        
        Lx = oper.Lx
        Ly = oper.Ly
        XX = oper.XX
        YY = oper.YY
        shape = oper.shapeX
        N_vort = self.params.init_fields.vortex_grid.n_vort
        SD = self.params.init_fields.vortex_grid.sd

        if N_vort % 2 != 0:
            raise ValueError("Cannot initialize a net circulation free field." +
                             "N_vort should be even.")

        dx_vort = Lx / N_vort
        dy_vort = Ly / N_vort
        x_vort = np.linspace(0, Lx, N_vort + 1) + dx_vort / 2.
        y_vort = np.linspace(0, Ly, N_vort + 1) + dy_vort / 2.
        sign_list = self._random_plus_minus_list()

        if SD == 0.:
            SD = min(dx_vort, dy_vort) / 2. / 6.
            self.params.init_fields.vortex_grid.sd = SD

        amp = self.params.init_fields.vortex_grid.omega_max
        if mpi.rank is 0:
            print 'Initializing vortex grid with SD = ', SD, 'amp = ',amp

        omega = np.zeros(shape)
        for i in xrange(0, N_vort):
            x0 = x_vort[i]
            for j in xrange(0, N_vort):
                y0 = y_vort[j]
                sign = sign_list.pop()
                omega = omega + wz_gaussian(XX - x0, YY - y0, sign, amp, SD)

        return omega

    def _random_plus_minus_list(self):
        """
        Returns a list with of length n_vort^2, with equal number of pluses and minuses.
        """
        from random import choice, shuffle
        
        N = self.params.init_fields.n_vort
        plus_or_minus = (+1., -1.)
        pm = list()

        for i in xrange(0, N**2):
            if i < N / 2:
                pm.append(choice(plus_or_minus))
            else:
                pm.append(-pm[i - N / 2])

        shuffle(pm)

        if pm.count(+1.) != pm.count(-1.):
            print "Clockwise: ", pm.count(-1.), ", Anti-clockwise: ", pm.count(+1.)
            raise ValueError(
                "Mismatch between number of clockwise and anticlockwise vortices in initialisation")
        return pm
    
        
class InitFieldsSW1L(InitFieldsBase):
    """Init the fields for the solver SW1L."""

    @staticmethod
    def _complete_info_solver(info_solver):
        """Complete the ParamContainer info_solver."""

        InitFieldsBase._complete_info_solver(
            info_solver,
            classes=[InitFieldsNoise, InitFieldsJet,
                     InitFieldsDipole, InitFieldsWave,
                     InitFieldsVortexGrid])
