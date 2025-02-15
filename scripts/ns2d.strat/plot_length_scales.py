"""
plot_length_scales.py
=======================

"""
import os
import numpy as np
import h5py
import matplotlib.pyplot as plt

from glob import glob
from mpl_toolkits.axes_grid1 import make_axes_locatable

# from compute_anisotropy import compute_anisotropy
# from compute_ratio_dissipation import compute_ratio_dissipation
# from compute_reynolds_froude import compute_buoyancy_reynolds

from compute_length_scales import compute_length_scales
from fluiddyn.output.rcparams import set_rcparams
from fluidsim import load_params_simul
from flow_features import get_features_from_sim, _get_resolution_from_dir


def _get_resolution_from_dir(path_simulation):
    return path_simulation.split("NS2D.strat_")[1].split("x")[0]


def _get_gamma_str_from_path(path_simulation):
    return path_simulation.split("_gamma")[1].split("_")[0]


SAVE = False

# Create path simulations
path_root = "/fsnet/project/meige/2015/15DELDUCA/DataSim"
directories = [
    "sim960_no_shear_modes",
    "sim960_no_shear_modes_transitory",
    "sim1920_no_shear_modes",
    "sim1920_modif_res_no_shear_modes",
    "sim3840_modif_res_no_shear_modes",
]

# directories = ["sim960_no_shear_modes",
#                "sim1920_no_shear_modes",
#                "sim1920_modif_res_no_shear_modes"]

# directories = ["sim960_no_shear_modes"]
paths_simulations = []
for directory in directories:
    paths_simulations += sorted(glob(os.path.join(path_root, directory, "NS2D*")))

froudes = []
reynoldsb = []
reynolds8 = []
anisotropies = []
dissipations = []
markers = []
lzs_billant = []

set_rcparams(fontsize=14, for_article=True)

fig, ax = plt.subplots()
ax.set_ylabel(r"$l_zN/U$", fontsize=18)
ax.set_xlabel(r"$\mathcal{R}_8$", fontsize=18)
ax.set_xscale("log")
ax.set_yscale("log")
# ax.text(0.6, 2e-12, r"$\log_{10} \left(\frac{k_{x, 1/2}}{k_{x, f}}\right)$", fontsize=16)
ax.tick_params(axis="x", labelsize=18)
ax.tick_params(axis="y", labelsize=18)
# ax.set_xlim([0.003, 1])
# ax.set_ylim([1e-9, 10])


for path in paths_simulations:
    gamma_str = _get_gamma_str_from_path(path)
    if gamma_str.startswith("2"):
        continue
    else:
        # F_h, Re_8, R_b = compute_buoyancy_reynolds(path)
        # anisotropy = compute_anisotropy(path)
        # dissipation = compute_ratio_dissipation(path)

        anisotropy, dissipation, F_h, Re_8, R_b = get_features_from_sim(path)
        res = _get_resolution_from_dir(path)
        lx, lz = compute_length_scales(path)

        # Compute
        ux_rms = []
        path_phys_files = glob(path + "/state_phys_t*")
        for path_file in path_phys_files[-10:]:
            with h5py.File(path_file, "r") as f:
                ux = f["state_phys"]["ux"][...]
            ux_rms.append(np.sqrt(np.mean(ux**2)))

        # Load parameters
        params = load_params_simul(path)

        lzs_billant.append(lz * params.N / np.mean(ux_rms))

        froudes.append(F_h)
        reynoldsb.append(R_b)
        reynolds8.append(Re_8)
        anisotropies.append(np.log10(2 * anisotropy))
        dissipations.append(np.log10(dissipation))

        if res == "960":
            markers.append("o")
        elif res == "1920":
            markers.append("s")
        elif res == "3840":
            markers.append("^")

        print("F_h", F_h)
        print("Re_8", Re_8)
        print("R_b", R_b)

        for _f, _r, _a, _d, _m, _l in zip(
            froudes, reynoldsb, anisotropies, dissipations, markers, lzs_billant
        ):
            scatter = ax.scatter(
                _r,
                _l,
                s=100 * (1**1),
                c="k",
                vmin=0,
                vmax=1,
                marker=_m,
                alpha=0.7,
            )

        # for _f, _r, _a, _d, _m, _l in zip(froudes, reynoldsb, anisotropies, dissipations, markers, lzs_billant):
        #     scatter = ax.scatter(_r, _l, s=2000 * (_a**1) + 20, c=_d, vmin=0, vmax=1, marker=_m, alpha=0.7)


# ax.scatter(0.1, 1e-5, marker="o", s=2000 * (np.log10(2*0.5)**1) + 20, color="red")
# ax.scatter(0.1, 1e-6, marker="o", s=2000 * (np.log10(2*0.75)**1) + 20, color="red")
# ax.scatter(0.1, 2e-8, marker="o", s=2000 * (np.log10(2)**1) + 20, color="red")

# ax.text(0.16, 8e-6, r"$anisotropy = 0$", color="red", fontsize=14)
# ax.text(0.16, 5e-7, r"$anisotropy = 0.5$", color="red", fontsize=14)
# ax.text(0.16, 2e-8, r"$anisotropy = 1$", color="red", fontsize=14)

# divider = make_axes_locatable(ax)
# cax = divider.append_axes("right", size="5%", pad=0.05)
# cax.tick_params(labelsize=14)
# fig.colorbar(scatter, cax=cax)

# Legend
import matplotlib.lines as mlines
import matplotlib.pyplot as plt

blue_star = mlines.Line2D(
    [],
    [],
    color="k",
    marker="o",
    linestyle="None",
    markersize=8,
    label=r"$n_x = 960$",
)
red_square = mlines.Line2D(
    [],
    [],
    color="k",
    marker="s",
    linestyle="None",
    markersize=8,
    label=r"$n_x = 1920$",
)
purple_triangle = mlines.Line2D(
    [],
    [],
    color="k",
    marker="^",
    linestyle="None",
    markersize=8,
    label=r"$n_x = 3840$",
)

ax.legend(
    handles=[blue_star, red_square, purple_triangle],
    loc="upper center",
    bbox_to_anchor=(0.5, 1.1),
    borderaxespad=0.0,
    ncol=len(markers),
    handletextpad=0.1,
    fontsize=14,
)

fig.tight_layout(pad=0.4)

if SAVE:
    path_save = "/home/users/calpelin7m/Phd/docs/EFMC18/figures"
    fig.savefig(
        path_save + "/vertical_length_billant.eps",
        format="eps",
        bbox_inches="tight",
    )
plt.show()
