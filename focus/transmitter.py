# Copyright (c) 2016, Frederik Hermans, Liam McNamara
#
# This file is part of FOCUS and is licensed under the 3-clause BSD license.
# The full license can be found in the file COPYING.

import numpy as np

import imageframer
import rscode

import focus


class Transmitter(object):
    def __init__(self, nsubchannels, nelements_per_subchannel=(64+16)*8/2,
                 parity=16, shape=(512, 512), border=0.15, cyclic_prefix=8):
        self.nsubchannels = nsubchannels
        self.nelements_per_subchannel = nelements_per_subchannel
        self.rs = rscode.RSCode(parity)
        self.qpsk = focus.modulation.QPSK()
        self.idxs = focus.spectrum.subchannel_idxs(nsubchannels,
                                                   nelements_per_subchannel,
                                                   shape)
        self.shape = shape
        self.shape_with_cp = tuple(np.array(shape) + 2*cyclic_prefix)
        self.framer = imageframer.Framer(self.shape_with_cp, border)
        self.cyclic_prefix = cyclic_prefix

    def encode(self, data, debug_info=None):
        ndataelements_per_subchannel = self.nelements_per_subchannel - \
            4*self.rs.parity_len

        if data.dtype != np.uint8 or \
           data.size * 4 != self.nsubchannels * ndataelements_per_subchannel:
            raise ValueError('Data has incorrect format or wrong number of '
                             'elements.')

        fragments = data.reshape((self.nsubchannels, -1))
        for i in xrange(self.nsubchannels):
            focus.link.mask_fragments(fragments[i], i)
        # RS encode
        coded_fragments = np.array([self.rs.encode(f) for f in fragments])
        # Modulate
        symbols = self.qpsk.modulate(coded_fragments.reshape(-1))
        symbols = symbols.reshape((self.nsubchannels, -1))
        # Load spectrum
        spectrum = focus.spectrum.construct(symbols, self.shape, self.idxs)
        # Compute inverse FFT
        code = focus.phy.tx(spectrum)
        # Add cyclic prefix
        code = focus.phy.add_cyclic_prefix(code, self.cyclic_prefix)
        # Add markers
        frame = self.framer.add_markers(code)
        if debug_info is not None:
            debug_info['coded_fragments'] = coded_fragments
            debug_info['symbols'] = symbols
        return frame


def test_tx_rx():
    data = np.random.randint(0, 255, 64*16).astype(np.uint8)

    shape = (512, 512)

    transmitter = Transmitter(16, shape=shape)
    frame = transmitter.encode(data.copy())

    receiver = focus.receiver.Receiver(16, shape=shape)
    rxdata = receiver.decode(frame)

    rxdata = np.array(rxdata['fragments'])
    data = data.reshape((16, -1))

    if not np.all(rxdata == data):
        raise RuntimeError('RX data does not match TX data.')
