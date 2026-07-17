import os
from setuptools import setup, Extension
from wheel.bdist_wheel import bdist_wheel

sources = ['ooz/palooz_bindings.cpp']
sources += ['ooz/dep/ooz/' + x for x in ['bitknit.cpp', 'kraken.cpp', 'lzna.cpp', 'compress.cpp', 'compr_kraken.cpp', 'compr_lzoffset.cpp', 'compr_entropy.cpp', 'compr_match_finder.cpp', 'compr_multiarray.cpp', 'compr_tans.cpp']]

extra_compile_args = ['-O3', '-flto', '-fno-exceptions', '-fno-rtti', '-ffast-math', '-fno-strict-aliasing']
if os.environ.get('DEBUG') == '1':
    extra_compile_args = ['-g', '-O0']

ext_modules = [Extension(name='palooz', sources=sources, define_macros=[('OOZ_BUILD_DLL', 1)], include_dirs=['ooz/dep/ooz/simde'], extra_compile_args=extra_compile_args)]

class bdist_wheel_abi3(bdist_wheel):
    def get_tag(self):
        python, abi, plat = super().get_tag()
        if python.startswith('cp'):
            return (python, 'none', plat)
        return (python, abi, plat)

setup(name='palooz', version='0.2.0', description='palooz compression/decompression bindings for Palworld saves', classifiers=['Development Status :: 3 - Alpha', 'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)', 'Natural Language :: English', 'Programming Language :: Python :: 3 :: Only'], cmdclass={'bdist_wheel': bdist_wheel_abi3}, ext_modules=ext_modules)
