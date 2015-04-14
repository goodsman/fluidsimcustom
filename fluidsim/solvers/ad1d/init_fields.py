
"""InitFieldsNS2D"""

import numpy as np

from fluidsim.base.init_fields import InitFieldsBase


class InitFieldsAD1D(InitFieldsBase):
    """Init the fields for the solver AD1D."""

    implemented_flows = ['GAUSSIAN', 'COS']

    def __call__(self):
        """Init the state (in physical and Fourier space) and time"""

        type = self.get_and_check_type()

        if type == 'GAUSSIAN':
            self.init_fields_gaussian()
        elif type == 'COS':
            self.init_fields_cos()
        else:
            raise ValueError('bad value of params.type')

    def init_fields_gaussian(self):
        s = np.exp(-(10*(self.oper.xs-self.oper.Lx/2))**2)
        self.sim.state.state_phys[0] = s

    def init_fields_cos(self):
        s = np.cos(2*np.pi*self.oper.xs/self.oper.Lx)
        self.sim.state.state_phys[0] = s
