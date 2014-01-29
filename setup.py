#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name="ast_pe",
    version="0.1",
    description="Partial evaluation on AST level",
    long_description=open("README.rst").read(),
    url="https://github.com/Manticore/ast_pe",
    author="Konstantin Lopuhin",
    author_email="kostia.lopuhin@gmail.com",
    maintainer="Bogdan Opanchuk",
    maintainer_email="bogdan@opanchuk.net",
    packages=find_packages(),
    install_requires=["six"],
    tests_require=["nose", "meta"],
    platforms=["any"],
    keywords="AST partial optimization",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python"",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.2",
        "Programming Language :: Python :: 3.3",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
    ],
)
