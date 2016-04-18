# Copyright (c) 2016, Frederik Hermans, Liam McNamara
#
# This file is part of FOCUS and is licensed under the 3-clause BSD license.
# The full license can be found in the file COPYING.

import numpy as np

import focus.mapping


def subchannel_idxs(nsubchannels, nelements_per_subchannel, shape):
    mapping = focus.mapping.halfring(nsubchannels*nelements_per_subchannel,
                                     shape)
    res = np.zeros((nsubchannels, ) + shape, dtype=np.bool)

    for i in xrange(nsubchannels):
        start = i*nelements_per_subchannel
        stop = start + nelements_per_subchannel
        for u, v in mapping[start:stop]:
            res[i, u, v] = True

    return res


def load_subchannel(spectrum, subchannel_idx, symbols):
    spectrum_flat = spectrum.reshape((-1, ))
    idx_flat = subchannel_idx.reshape((-1, ))
    spectrum_flat[idx_flat] = symbols


def unload_subchannel(spectrum, subchannel_idx):
    spectrum_flat = spectrum.reshape((-1, ))
    idx_flat = subchannel_idx.reshape((-1, ))
    return spectrum_flat[idx_flat]


def construct(symbols, shape, idxs=None):
    '''Pack the symbols for each sub-channel into a `shape`-sized matrix.'''
    if idxs is None:
        nsubchannels, nelements_per_subchannel = symbols.shape
        idxs = subchannel_idxs(nsubchannels, nelements_per_subchannel, shape)

    spectrum = np.zeros(shape, dtype=np.complex)
    for i, channel_symbols in enumerate(symbols):
        load_subchannel(spectrum, idxs[i], channel_symbols)

    return spectrum


def unload(spectrum, idxs):
    symbols = list()
    # Create a copy of the spectrum; the copy can be reshaped in place
    # (as unload() will do); if we don't pass a copy to unload(), then
    # unload() would create a copy on each call -- huge overhead!
    spectrum = spectrum.copy()
    for idx in idxs:
        symbols.append(unload_subchannel(spectrum, idx))

    return symbols


def test_construct_unload(nsubchannels=16, nelements_per_subchannel=512,
                          shape=(512, 512)):
    idxs = subchannel_idxs(nsubchannels, nelements_per_subchannel, shape)

    symbols = np.arange(nsubchannels*nelements_per_subchannel)
    symbols = symbols.reshape(nsubchannels, -1)
    spectrum = construct(symbols, shape, idxs)
    unloaded_symbols = unload(spectrum, idxs)
    if not np.all(symbols == unloaded_symbols):
        raise RuntimeError('test_construct_unload: Input does not match '
                           'output.')


def construct_many(symbols, shape):
    '''Convenience function to create multiple spectra.'''
    symbols = np.array(symbols)
    nframes, nsubchannels, nelems = symbols.shape
    idx = subchannel_idxs(nsubchannels, nelems, shape)
    spectra = list()
    for frame_symbols in symbols:
        spectra.append(construct(frame_symbols, shape, idx=idx))
    return spectra


def get_bbox(idxs):
    # Find the max x and max y coordinates in the
    # last channel. They indicate where to clip.

    allchannels = idxs.any(0)  # collapse all channels into single matrix
    first_col = allchannels[:, 0]
    first_row = allchannels[0, :]
    height = max(np.where(first_col)[0]) + 1
    width = max(np.where(first_row)[0]) + 1

    return height, width


def test_bbox(nchannels=321, shape=(512, 512)):
    try:
        focus.receiver.Receiver(nchannels, shape=shape, use_hints=False)
    except:
        raise RuntimeError('Building large Receiver failed, bbox likely bad.')


def crop(a, height, width):
    return np.vstack((a[:height, :width],
                      a[-height:, :width]))
