"""Frozen Windows/Linux entry point."""
import multiprocessing
multiprocessing.freeze_support()
from fixoflow.desktop import main
if __name__=='__main__':main()
