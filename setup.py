#! /usr/bin/env python

from setuptools import setup

setup(
    name="release_path",
    version="0.1.4",
    description="Tools to manage a git release path",
    scripts=['branches_pending_release',
             'deep_merge',
             'merge_release_branches',
             'mk_release_branch',
             'merge_branch_upstream',
             'merge_products_upstream',
             'merge_upstream_star',
             'single_merge',
             'verify_guards'
            ],
    py_modules=['release_path', 'release_branch_manager'],
    setup_requires=['nose'],
    install_requires=[
        'simpleversions==0.1.2',
        'argparse',
        'GitPython',
    ],
)
