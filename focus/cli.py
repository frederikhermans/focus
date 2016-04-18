# Copyright (c) 2016, Frederik Hermans, Liam McNamara
#
# This file is part of FOCUS and is licensed under the 3-clause BSD license.
# The full license can be found in the file COPYING.

import inspect

import click

import focus
import focus.simpletxrx


def _nop():
    pass


def _get_type(default):
    if type(default) == tuple:
        return tuple(_get_type(e) for e in default)
    else:
        return type(default)


def build_command(name, func):
    args, varargs, keywords, defaults = inspect.getargspec(func)
    args = args if args else list()
    defaults = defaults if defaults else list()
    if varargs is not None or keywords is not None:
        raise RuntimeError('Cannot build CLI for function with kwargs or '
                           'varags.')
    if len(args) != len(defaults):
        raise RuntimeError('Cannot build CLI for function with argument '
                           'without default values.')
    for arg, default in reversed(zip(args, defaults)):
        func = click.option('--'+arg, type=_get_type(default),
                            default=default)(func)
    return click.command(name)(func)


def build_group(name, *commands):
    group = click.group(name)(_nop)
    for cmd in commands:
        group.add_command(cmd)
    return group


def main():
    benchmark = build_group('benchmark',
                            build_command('fft', focus.fft.benchmark),
                            build_command('multiprocreceiver',
                                          focus.multiprocreceiver.benchmark),
                            build_command('receiver', focus.receiver.benchmark))

    build_group('main',
                benchmark,
                build_command('test', focus.tests.run_tests),
                focus.receiver.main,
                focus.simpletxrx.tx,
                focus.simpletxrx.rx,
                focus.video.rx,
                focus.video.tx,
                focus.video.multirate,
                build_command('fft_init', focus.fft.wisdom))()


if __name__ == '__main__':
    main()
