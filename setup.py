#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys

import importlib.util
from setuptools import find_packages, setup
from setuptools.command.install import install
from setuptools.command.egg_info import egg_info
from setuptools.command.develop import develop


def install_check(self, command):
    if os.name == "nt":
        sys.exit("Looks like you are on windows. Only MacOS and Linux are supported :(")
    command.run(self)


class PostDevelopCommand(develop):
    def run(self):
        install_check(self, develop)


class PostInstallCommand(install):
    def run(self):
        install_check(self, install)


class PostEggInfoCommand(egg_info):
    def run(self):
        install_check(self, egg_info)


requirement_list = [
    "keyring==21.4.0",
    "psutil",
    "ConfigArgParse>=1.0",
]
# if locust-plugins IS installed, then require a version known to work with this version of swarm.
spec = importlib.util.find_spec("locust_plugins")
if spec is not None:
    requirement_list.append("locust-plugins>=2.7.0")

setup(
    name="locust-swarm",
    description="Load test + test data distribution & launching tool for Locust",
    long_description="""https://github.com/SvenskaSpel/locust-swarm""",
    classifiers=[
        "Topic :: Software Development :: Testing :: Traffic Generation",
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: MacOS",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
    ],
    python_requires=">=3.7, <4",
    keywords="",
    author="Lars Holmberg",
    url="https://github.com/SvenskaSpel/locust-swarm",
    license="Apache-2.0",
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=requirement_list,
    entry_points={
        "console_scripts": ["swarm = locust_swarm.swarm:main"],
    },
    cmdclass={"egg_info": PostEggInfoCommand, "install": PostInstallCommand, "develop": PostDevelopCommand},
    use_scm_version={
        "write_to": "locust_swarm/_version.py",
        "local_scheme": "no-local-version",
    },
    setup_requires=["setuptools_scm"],
)
