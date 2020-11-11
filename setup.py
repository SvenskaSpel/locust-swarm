#!/usr/bin/env python
# -*- coding: utf-8 -*-
import ast
import re
import os
import sys

from setuptools import find_packages, setup
from setuptools.command.install import install
from setuptools.command.egg_info import egg_info
from setuptools.command.develop import develop

_version_re = re.compile(r"__version__\s+=\s+(.*)")
_init_file = "locust_swarm/__init__.py"
with open(_init_file, "rb") as f:
    version = str(ast.literal_eval(_version_re.search(f.read().decode("utf-8")).group(1)))


class PostDevelopCommand(develop):
    def run(self):
        if os.name == "nt":
            sys.exit("Looks like you are on windows. Only MacOS and Linux are supported :(")
        develop.run(self)


class PostInstallCommand(install):
    def run(self):
        if os.name == "nt":
            sys.exit("Looks like you are on windows. Only MacOS and Linux are supported :(")
        install.run(self)


class PostEggInfoCommand(egg_info):
    def run(self):
        if os.name == "nt":
            sys.exit("Looks like you are on windows. Only MacOS and Linux are supported :(")
        egg_info.run(self)


setup(
    name="locust-swarm",
    version=version,
    description="Load test distribution tool for Locust",
    long_description="""https://github.com/SvenskaSpel/locust-swarm""",
    classifiers=[
        "Topic :: Software Development :: Testing :: Traffic Generation",
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: MacOS",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
    ],
    python_requires=">=3.6, <4",
    keywords="",
    author="Lars Holmberg",
    url="https://github.com/SvenskaSpel/locust-swarm",
    license="Apache-2.0",
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=["keyring==21.4.0", "locust-plugins>=1.0.17", "psutil", "ConfigArgParse>=1.0"],
    scripts=["bin/swarm"],
    cmdclass={"egg_info": PostEggInfoCommand, "install": PostInstallCommand, "develop": PostDevelopCommand},
)
