# Copyright (c) 2016, Frederik Hermans, Liam McNamara
#
# This file is part of FOCUS and is licensed under the 3-clause BSD license.
# The full license can be found in the file COPYING.

import numpy as np

import focus.fft

MIN_SNR = 45


def snr(signal, distorted):
    """Returns signal to noise ratio between a signal and a distorted copy.

    The return value is in dB."""
    # http://dsp.stackexchange.com/questions/4889/how-do-i-calculate-snr-of-noisy-signal
    noise = signal - distorted
    snr = np.mean(signal ** 2) / np.mean(noise ** 2)
    snr_db = 10. * np.log10(snr)
    return snr_db


def clip_and_quantize(frame):
    """Clips and quantizes a frame.

    The clipping threshold is chosen such that the SNR is at least MIN_SR dB.
    See pg. 22-23 of the Master thesis."""
    peak = frame.max()

    # Binary search for threshold that gives MIN_SNR
    lower_thresh = 0.5
    upper_thresh = 1.0
    thresh = (upper_thresh + lower_thresh) / 2.
    # Clip
    clipped = frame.copy()
    clipped[clipped > thresh*peak] = thresh*peak
    current_snr = snr(frame, clipped)
    while np.round(current_snr) != MIN_SNR:
        # Adjust threshold
        if current_snr > MIN_SNR:
            upper_thresh = thresh
        else:
            lower_thresh = thresh
        thresh = (upper_thresh + lower_thresh) / 2.
        # Clip
        clipped[:] = frame
        clipped[clipped > thresh*peak] = thresh*peak
        # Re-compute SNR
        current_snr = snr(frame, clipped)

    # Quantize frame
    clipped -= clipped.min()
    clipped /= clipped.max()
    clipped *= 255
    clipped = clipped.astype(np.uint8)
    return clipped


def tx(spectrum, normalize=True):
    '''Create a code for given spectrum.'''
    code = np.fft.irfft2(spectrum, s=spectrum.shape)
    if normalize:
        code = clip_and_quantize(code)
    return code


def rx(rxframe):
    return focus.fft.rfft2(rxframe)


def add_cyclic_prefix(img, pixels):
    row = np.hstack((img, img, img))
    three_by_three = np.vstack((row, row, row))
    offset = img.shape[0] - pixels
    return three_by_three[offset:-offset, offset:-offset]


def strip_cyclic_prefix(img, pixels):
    return img[pixels:-pixels, pixels:-pixels]


def test_add_strip_cyclic_prefix():
    img = np.random.randint(0, 255, 512*512).reshape((512, 512))
    cp = 32
    imgcp = add_cyclic_prefix(img, cp)
    if not np.all(img == strip_cyclic_prefix(imgcp, cp)):
        raise RuntimeError('Adding and stripping cyclic prefix changed the '
                           'input image')
    pass
