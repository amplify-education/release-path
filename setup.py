#! /usr/bin/env python

from setuptools import setup

setup(
    name="release_path",
    version="0.1",
    description="Tools to manage a git release path",
    author="Calen Pennington",
    author_email="cpennington@wgen.net",
    scripts=['branches_pending_release',
             'deep_merge',
             'merge_release_branches',
             'mk_release_branch'],
    setup_requires=['nose'],
    install_requires=[
        'simpleversions==0.1.2',
        'argparse',
        'GitPython==0.1.6',
    ],
)
