# CellModellerWithCuPy
## Enhancing GPU usage on CellModeller with CuPy

This project starts with an attempt to replace NumPy implementations on the existing Biophysics module on CellModeller with that of CuPy, that is an implementation of a NumPy-compatible multi-dimensional array on CUDA. The main goal here is to make use of CuPy's interoperability with CellModeller's existing and primary backend: PyOpenCL, thus increasing parallelization and reducing CPU dependency while simulating cell growth. PyOpenCL and OpenCL based data handling has not been modified.
