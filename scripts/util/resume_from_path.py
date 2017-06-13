import argparse
import fluidsim as fls

parser = argparse.ArgumentParser(description='Resume a Fluidsim simulation from a path')
parser.add_argument('PATH',
    help='path to an incomplete simulation directory')

args = parser.parse_args()
sim = fls.load_state_phys_file(args.path)
sim.time_stepping.start()
