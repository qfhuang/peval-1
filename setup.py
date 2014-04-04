#!/usr/bin/env python

import sys
from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand


class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        import pytest
        errno = pytest.main(self.test_args)
        sys.exit(errno)


setup(
    name="peval",
    version="0.1.0",
    description="Partial evaluation on AST level",
    long_description=open("README.rst").read(),
    url="https://github.com/Manticore/peval",
    author="Konstantin Lopuhin",
    author_email="kostia.lopuhin@gmail.com",
    maintainer="Bogdan Opanchuk",
    maintainer_email="bogdan@opanchuk.net",
    packages=find_packages(),
    install_requires=["six"],
    tests_require=["pytest", "astunparse"],
    cmdclass={'test': PyTest},
    platforms=["any"],
    keywords="AST partial optimization",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Software Development :: Code Generators",
    ],
)
