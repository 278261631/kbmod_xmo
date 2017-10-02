![kbmod](https://gist.githubusercontent.com/PWhiddy/d42e66a9dd8e4af205a706f388a90ed4/raw/ae5bb87ada12538289852b58ba8e54b564a81584/kbmod.svg)

# KBMOD (Kernel-Based Moving Object Detection)

[![Build Status](https://travis-ci.org/DiracInstitute/kbmod.svg?branch=master)](https://travis-ci.org/DiracInstitute/kbmod) [![License](https://img.shields.io/badge/License-BSD%202--Clause-orange.svg)](https://opensource.org/licenses/BSD-2-Clause)

A Maximum Likelihood detection algorithm for moving astronomical objects.

KBMOD is a set of Python tools to search astronomical images for moving
objects based upon method of maximum likelihood detection.

## Requirements

The packages required to run the code are:

* python3-dev
* Scipy (Numpy, Matplotlib)
* Scikit-learn
* Astropy
* Cuda 8.0
* CMake

## Setup

To install:
```source install.sh```
This will build the python library and run the tests.

If you log out, next time run
```source setup.bash```
to reappend the library to the python path


## Example

See the example [ipython notebook](https://github.com/jbkalmbach/kbmod/blob/master/notebooks/kbmod_demo.ipynb).

## License

The software is open source and available under the BSD license.
