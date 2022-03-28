import os
from pathlib import Path
import re
from math import pi
import subprocess

from fluidoccigen import cluster

t_end = 40.0
nh = 896
nb_nodes = 4
path_scratch = Path(os.environ["SCRATCHDIR"])
path_init = path_scratch / "2022/aniso/init_occigen"

paths_in = sorted(path_init.glob("ns3d.strat_toro*_640x640*"))
path_simuls = sorted(
    (path_scratch / "aniso").glob(f"ns3d.strat_toro*_{nh}x{nh}*")
)

print(f"{path_simuls=}")

def run(command):
    return subprocess.run(
        command.split(), check=True, capture_output=True, text=True
    )


user = os.environ["USER"]
process = run(f"squeue -u {user}")
lines = process.stdout.split("\n")[1:]
jobs_id = [line.split()[0] for line in lines if line]

jobs_name = []
for job_id in jobs_id:
    process = run(f"scontrol show job {job_id}")
    line = process.stdout.split("\n")[0]
    job_name = line.split(" JobName=")[1]
    jobs_name.append(job_name)

print(f"{jobs_name=}")

for path_init_dir in paths_in:

    name_old_sim = path_init_dir.name

    N_str = re.search(r"_N(.*?)_", name_old_sim).group(1)
    N = float(N_str)
    Rb_str = re.search(r"_Rb(.*?)_", name_old_sim).group(1)
    Rb = float(Rb_str)

    N_str = "_N" + N_str
    Rb_str = "_Rb" + Rb_str

    if [p for p in path_simuls if N_str in p.name and Rb_str in p.name]:
        print(f"Simulation directory for {N=} and {Rb=} already created")
        continue

    name_run = f"N{N}_Rb{Rb}_{nh}"
    if name_run in jobs_name:
        print(f"Job {name_run} already launched")
        continue

    path_init_file = next(
        path_init_dir.glob(f"State_phys_{nh}x{nh}*/state_phys*")
    )

    assert path_init_file.exists()
    print(path_init_file)

    period_spatiotemp = min(2 * pi / (N * 8), 0.03)

    command = (
        f"fluidsim-restart {path_init_file} --t_end {t_end} --new-dir-results "
        "--max-elapsed 23:50:00 "
        "--modify-params 'params.nu_4 /= 3.07; params.output.periods_save.phys_fields = 0.5; "
        'params.oper.type_fft = "fft3d.mpi_with_fftw1d"; '
        f"params.output.periods_save.spatiotemporal_spectra = {period_spatiotemp}'"
    )

    nb_cores_per_node = cluster.nb_cores_per_node
    nb_mpi_processes = nb_cores_per_node * nb_nodes

    print(f"Submitting command\n{command}")

    cluster.submit_command(
        command,
        name_run=f"N{N}_Rb{Rb}_{nh}",
        nb_nodes=nb_nodes,
        nb_cores_per_node=nb_cores_per_node,
        nb_mpi_processes=nb_mpi_processes,
        omp_num_threads=1,
        ask=False,
        walltime="23:59:58",
    )
