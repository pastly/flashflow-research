#!/usr/bin/env python3
from setuptools import setup, find_packages
import os


def find_version():
    with open(os.path.join("ph", "__init__.py")) as fp:
        for line in fp:
            if "__version__" in line.strip():
                version = line.split("=", 1)[1].strip().strip("'")
                return version


def find_name():
    with open(os.path.join("ph", "__init__.py")) as fp:
        for line in fp:
            if "__software_name__" in line.strip():
                name = line.split("=", 1)[1].strip().strip("'")
                return name


def long_description():
    return ''


def get_package_data():
    return [
        'config.default.ini',
        'config.log.default.ini',
    ]


setup(
    name=find_name(),
    version=find_version(),
    description="Measure bandwidth",
    long_description=long_description(),
    author='Matt Traudt',
    author_email='sirmatt@ksu.edu',
    license='CC0',
    packages=find_packages(),
    package_data={
        'ph': get_package_data(),
    },
    entry_points={
        'console_scripts': [
            'ph = ph.main:main',
        ],
    },
    install_requires=[
        'pynacl',
        'aioconsole',
        'cryptography',
    ],
)
