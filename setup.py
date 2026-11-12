#!/usr/bin/env python3

import os
import sys

# setup.py imports the package to reuse singularity.__version__.  PEP 517
# build frontends (pip, build) exec this file in a subprocess whose sys.path
# does not include the source tree, so add it explicitly.  Without this,
# "pip install ." fails with "No module named 'singularity'" now that a
# pyproject.toml routes the build through the setuptools backend.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import singularity

from setuptools import setup, find_packages

setup(
    name="Singularity-2030",
    version=singularity.__version__,
    description="A simulation of a true AI",
    author="Evil Mr Henry",
    author_email="evilmrhenry@emhsoft.com",
    maintainer="kostich",
    url="https://github.com/kostich/singularity",
    license="GPL-2.0-or-later",
    python_requires=">=3.9",
    classifiers=[
        'Intended Audience :: End Users/Desktop',
        'Topic :: Games/Entertainment',

        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
    ],
    # Only ship the game itself.  "utils/" holds developer helper scripts, not
    # part of the installed package, so name the packages we do ship instead of
    # letting find_packages() decide.  It used to find a top-level "utils"
    # package there through a stray __init__.py, which upstream deleted in
    # 932d6e2; the explicit list keeps that from coming back.
    packages=find_packages(include=["singularity", "singularity.*"]),
    zip_safe=False,
    include_package_data=True,
    install_requires=[
        'numpy',
        'pygame>=2.5.2',
        # Polib parses the .po/.mo translation catalogs at startup.  It used
        # to be vendored in singularity/code/polib.py; that copy is gone, so
        # this is now a real runtime dependency.
        'polib>=1.2',
    ],
    extras_require={
        'dev': [
            'pytest',
        ],
    },
    entry_points={
        'gui_scripts': [
            'singularity=singularity.__main__:main',
        ],
    },
)
