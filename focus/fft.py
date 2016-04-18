# Copyright (c) 2016, Frederik Hermans, Liam McNamara
#
# This file is part of FOCUS and is licensed under the 3-clause BSD license.
# The full license can be found in the file COPYING.

import cPickle as pickle
import os
import subprocess
import sys

import numpy as np
import pyfftw

import focus.util


def _wisdom_filename():
    if focus.util.is_android():
        return '/sdcard/wisdom-' + \
            subprocess.check_output(['getprop', 'net.hostname']).strip()
    else:
        return os.path.expanduser('~') + \
            '/.focus-wisdom-' + subprocess.check_output(['hostname']).strip()


class FFT(object):
    def __init__(self, shape):
        have_wisdom = self.load_wisdom()

        self.floatbuf = pyfftw.n_byte_align_empty(shape, pyfftw.simd_alignment,
                                                  dtype=np.float32)
        self._rfft2 = pyfftw.builders.rfft2(self.floatbuf,
                                            planner_effort='FFTW_MEASURE')
        self.complexbuf = pyfftw.n_byte_align_empty(shape,
                                                    pyfftw.simd_alignment,
                                                    dtype=np.complex64)
        self._irfft2 = pyfftw.builders.irfft2(self.complexbuf,
                                              planner_effort='FFTW_MEASURE')
        if not have_wisdom:
            self.save_wisdom()

    def rfft2(self, data):
        self.floatbuf[:] = data
        return self._rfft2(self.floatbuf)

    def irfft2(self, data):
        self.complexbuf[:] = data
        return self._irfft2(self.complexbuf)

    def load_wisdom(self):
        try:
            with open(_wisdom_filename(), 'rb') as fin:
                wisdom = pickle.load(fin)
                pyfftw.import_wisdom(wisdom)
            return True
        except IOError:
            sys.stderr.write('WARNING: No wisdom file {}. This may take a '
                             'while ...\n'.format(_wisdom_filename()))
            return False

    def save_wisdom(self):
        with open(_wisdom_filename(), 'wb') as fout:
            pickle.dump(pyfftw.export_wisdom(), fout,
                        protocol=pickle.HIGHEST_PROTOCOL)


_fft_cache = dict()
_use_numpy = False


def get_cached(shape):
    global _fft_cache
    try:
        return _fft_cache[shape]
    except KeyError:
        _fft_cache[shape] = FFT(shape)
        return _fft_cache[shape]


def rfft2(frame):
    if _use_numpy:
        return np.fft.rfft2(frame)
    return get_cached(frame.shape).rfft2(frame)


def irfft2(spectrum):
    if _use_numpy:
        return np.fft.irfft2(spectrum)
    return get_cached(spectrum.shape).irfft2(spectrum)


def test_rfft2(n=10):
    from focus.util import phase_diff

    data = np.random.randint(0, 256, (n, 512, 512)).astype(np.uint8)
    for d in data:
        spectrum = rfft2(d)
        np_spectrum = np.fft.rfft2(d)
        # Test that the phases are similar. Note that since we're using
        # single-precision floats with pyfftw, and numpy uses double precision,
        # the results will differ. However, the differences in phase are
        # very small (< 0.002).
        max_diff = np.max(np.abs(phase_diff(spectrum, np_spectrum)))
        if max_diff > 0.002:
            raise RuntimeError('test_rfft2: Inconsistent results')


def test_irfft2(n=10):
    def normalize(data):
        data -= data.min()
        data /= data.max()
        data *= 255.
        return data

    spectra = np.random.random((n, 512, 512)) + \
        1j * np.random.random((n, 512, 512))
    for s in spectra:
        data = normalize(irfft2(s))
        np_data = normalize(np.fft.irfft2(s))
        max_diff = np.abs(data-np_data).max()
        if max_diff > 0.0001:
            raise RuntimeError('test_irfft2: Inconsistent results.')


def benchmark(shape=(512, 512), n=10):
    import time

    fft = FFT(shape)
    data = np.random.randint(0, 256, (n, ) + shape).astype(np.uint8)

    # Numpy benchmark
    start_np = time.time()
    for i in xrange(n):
        np.fft.rfft2(data[i])
    stop_np = time.time()
    time_np = stop_np-start_np
    print 'npfft:  {:4} s ({:.0f} ms / fft)'.format(time_np,
                                                    time_np/n*1000)

    # pyFFTW benchmark
    start_pyfftw = time.time()
    for i in xrange(n):
        fft.rfft2(data[i])
    stop_pyfftw = time.time()
    time_pyfftw = stop_pyfftw-start_pyfftw
    print 'pyfftw: {:4} s ({:.0f} ms / fft)'.format(time_pyfftw,
                                                    time_pyfftw/n*1000)
    print 'Speedup: {:.2}'.format(time_np/time_pyfftw)


def wisdom():
    print 'Creating wisdom file ... ignore warnings about missing wisdom file.'
    try:
        os.unlink(_wisdom_filename())
    except OSError:
        pass
    for shape in ((512, 512), (768, 768), (1024, 1024)):
        fft = FFT(shape)
    fft.save_wisdom()
