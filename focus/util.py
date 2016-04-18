# Copyright (c) 2016, Frederik Hermans, Liam McNamara
#
# This file is part of FOCUS and is licensed under the 3-clause BSD license.
# The full license can be found in the file COPYING.

import cPickle as pickle
import os

import numpy as np

_is_android = None


def phase_diff(a, b):
    """Returns the phase difference of elements in `psk_a` and `psk_b`."""
    arg_a = np.angle(a)
    arg_b = np.angle(b)
    return np.arctan2(np.sin(arg_a-arg_b),
                      np.cos(arg_a-arg_b))


def is_android():
    global _is_android
    if _is_android is None:
        _is_android = os.path.exists('/data/data/se.sics.vizpy')
    return _is_android


def load_frames(fname):
    if fname.endswith('.pickle'):
        with open(fname, 'rb') as fin:
            return pickle.load(fin)
    else:
        raise ValueError('Don\'t know how to load frames from {}'.format(fname))


def parse_resolution(resolution_str):
    return tuple([int(v) for v in resolution_str.split('x')][::-1])


def sizeof_fmt(num, suffix='B'):
    # http://stackoverflow.com/a/1094933
    for unit in ('', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi'):
        if abs(num) < 1024.0:
            return "%3.1f %s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f %s%s" % (num, 'Yi', suffix)
