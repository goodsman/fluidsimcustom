import sys

from fluiddyn.clusters.idris import JeanZay as Cluster

cluster = Cluster()

nb_nodes = 1
nb_cores_per_node = cluster.nb_cores_per_node
nb_procs = nb_mpi_processes = nb_nodes * nb_cores_per_node

walltime = "00:40:00"

cluster.commands_setting_env.append(
    "export TRANSONIC_MPI_TIMEOUT=100"
)

cluster.submit_script(
    "run_simul.py",
    name_run=f"ns3d.strat",
    nb_nodes=nb_nodes,
    nb_cores_per_node=nb_cores_per_node,
    nb_mpi_processes=nb_mpi_processes,
    omp_num_threads=1,
    ask=True,
    walltime=walltime,
)


