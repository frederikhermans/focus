# Copyright (c) 2016, Frederik Hermans, Liam McNamara
#
# This file is part of FOCUS and is licensed under the 3-clause BSD license.
# The full license can be found in the file COPYING.

import numpy as np


class QPSK(object):
    nan_symbol = np.complex(1, 0)
    bits_to_phases = {0b00: 1/4.*np.pi,  0b01: 3/4.*np.pi,
                      0b11: -3/4.*np.pi, 0b10: -1/4.*np.pi}

    def __init__(self):
        self.bits_to_sym = {bits: np.complex(np.cos(phase), np.sin(phase))
                            for bits, phase in self.bits_to_phases.iteritems()}

        self.lss_lookup = list()
        self.mss_lookup = list()
        for byte in xrange(256):
            mod = self._modulate_byte(byte)
            self.lss_lookup.append(mod)
            self.mss_lookup.append(mod[::-1])

    def _modulate_byte(self, byte):
        return (self.bits_to_sym[(byte >> 0) & 0b11],
                self.bits_to_sym[(byte >> 2) & 0b11],
                self.bits_to_sym[(byte >> 4) & 0b11],
                self.bits_to_sym[(byte >> 6) & 0b11])

    def modulate(self, bytes, lss_first=True):
        lookup = self.lss_lookup if lss_first else self.mss_lookup
        symbols = np.zeros(4*len(bytes), dtype=np.complex)
        for i, byte in enumerate(bytes):
            symbols[4*i:4*(i+1)] = lookup[byte]
        return symbols

    def demodulate(self, symbols):
        assert len(symbols) % 4 == 0, 'Incomplete bytes!'
        # Replace NaN symbols with symbol representing 0b00 and let
        # FEC deal with the errors.
        symbols[np.isnan(symbols)] = np.complex(1, 0)
        assert np.all(np.abs(symbols) > 0), \
            'QPSK cannot decode zero-length symbol.'

        phases = np.angle(symbols)
        # Map symbol phases to bits
        symbits = np.zeros(symbols.shape, np.uint8)
        piq = 1/4.*np.pi
        for bits, phase in self.bits_to_phases.iteritems():
            symbits[(phase-piq <= phases) & (phases < phase+piq)] = bits

        # Pack bits into bytes
        return (symbits[3::4] << 6) | \
               (symbits[2::4] << 4) | \
               (symbits[1::4] << 2) | \
               (symbits[0::4] << 0)


def test_mod_demod(nsymbols=65536):
    data = np.random.randint(0, 255, nsymbols).astype(np.uint8)
    qpsk = QPSK()
    symbols = qpsk.modulate(data)
    demod_data = qpsk.demodulate(symbols)
    if not np.all(data == demod_data):
        raise RuntimeError('Demodulated data does not match input data.')
