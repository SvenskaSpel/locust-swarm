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
    try:
        import locust_plugins  # noqa

        major, minor, _patch = locust_plugins.__version__.split(".")
        if int(major) < 2 or int(major) == 2 and int(minor) < 7:
            sys.exit(
                "Please update (or uninstall) locust-plugins, your version is not compatible with this version of locust-swarm"
            )
    except ImportError:
        pass  # plugins wasnt installed, no worries
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
    install_requires=[
        "keyring==21.4.0",
        "psutil",
        "ConfigArgParse>=1.0",
    ],
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
