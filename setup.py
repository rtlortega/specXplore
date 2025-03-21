#cython: language_level=3
# From package directory and right environment, install package using: "pip install -e ."   
from setuptools import setup, Extension
from Cython.Build import cythonize
import os

directory_name = './specxplore'

cython_module_name_list = [
    'egonet_cython', 
    'netview_cython', 
    'utils_cython', 
    'importing_cython']
module_paths = [
     Extension(
        f'specxplore.{name}',
        sources = [os.path.join(directory_name, name + '.pyx')],
        language = 'c++'
        ) 
     for name in cython_module_name_list]

# Read the version string from version.py
version = {}
with open(os.path.join('specxplore', 'version.py')) as fp:
    exec(fp.read(), version)

setup(
    name='specxplore',
    version = version["__version__"],
    ext_modules=cythonize(module_paths, compiler_directives = {'language_level': '3'}),
    include_package_data=True, 
    package_data={"specxplore" : [os.path.join("specxplore")]},
    packages=['specxplore'],
    python_requires='>=3.8,<3.9',
    install_requires = [
        'numpy', 
        'jupyter',
        "ipykernel",
        'ms2query==1.3.0',
        'matchms==0.24.1',
        "matchmsextras==0.4.0",
        'spec2vec==0.8.0',
        'ms2deepscore==0.4.0',
        'kmedoids==0.5.0',
        'dash',
        'plotly',
        'dash-cytoscape',
        'pandas',
        'cython',
        'scipy',
        'dash_daq',
        'dash_bootstrap_components',
        'dash<3.0' 
        ],
        extras_require={
            'dev': ['pytest']}
)
# Cleaning out .cpp files that are not needed after .so object construction.
directories = os.listdir(directory_name)
for item in directories:
    if item.endswith('.cpp'):
        os.remove(os.path.join(directory_name, item))
    
