#! /usr/bin/env python
# -*- coding: utf-8 -*-

import setuptools

setuptools.setup(
    name="clichain",
    version="0.1.0",
    url="https://github.com/loicpw/clichain",
    download_url = "https://github.com/loicpw/clichain.git",

    author="Loïc Peron",
    author_email="peronloic.us@gmail.com",

    description="Create a CLI to chain tasks as a pipeline",

    long_description='\n\n'.join(
        open(f, 'rb').read().decode('utf-8')
        for f in ['README.rst', 'HISTORY.rst']),

    packages=setuptools.find_packages(),

    install_requires=[
        'click',
    ],

    license='MIT License',
    include_package_data=True,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
)
