#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys

from setuptools import find_packages, setup
from setuptools.command.install import install
from setuptools.command.egg_info import egg_info
from setuptools.command.develop import develop


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
    description="Load test + test data distribution & launching tool for Locust",
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
    install_requires=[
        "keyring==21.4.0",
        "locust-plugins>=2.2.2",
        "psutil",
        "ConfigArgParse>=1.0",
    ],
    scripts=["bin/swarm"],
    cmdclass={"egg_info": PostEggInfoCommand, "install": PostInstallCommand, "develop": PostDevelopCommand},
    use_scm_version={
        "write_to": "locust_swarm/_version.py",
        "local_scheme": "no-local-version",
    },
    setup_requires=["setuptools_scm"],
)
