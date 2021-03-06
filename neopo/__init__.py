# neopo: A lightweight solution for local Particle development.
# Copyright (c) 2021 Nathan Robinson.
# https://neopo.xyz

import os

# Disable RuntimeWarning for neopo.particle and neopo.script
import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)

# Import module api
from .cli import main, particle
from .cli import iterate, script, script_wait
from .cli import install, upgrade, uninstall, versions, create
from .cli import build, flash, flash_all, clean
from .cli import run, configure, flags, settings, libs
from .cli import update, get
