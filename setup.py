# Copyright 2020 Canonical Ltd.
#
# interface-pgsql is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>
from setuptools import setup

import os.path

setup(
    name="interface-pgsql",
    version="0.0.1",
    author="John Arbash Meinel",
    author_email="john.meinel@canonical.com",
    url="https://github.com/jameinel/interface-pgsql",
    license="LGPL-v3",
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

        "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
    ],
)
