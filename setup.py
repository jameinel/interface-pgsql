from setuptools import setup

import os.path

setup(
    name="interface-pgsql",
    version="0.0.1",
    author="John Arbash Meinel",
    author_email="john.meinel@canonical.com",
    url="https://github.com/jameinel/interface-pgsql",
    py_modules=["client"],
    install_requires=["PyYAML"],
    dependency_links=[
        "https://github.com/canonical/operator/archive/master.tar.gz#egg=ops-0.0.1",
    ],
    classifiers=[
        "Development Status :: 4 - Beta",

        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",

        "License :: OSI Approved :: Apache Software License",
    ],
)
