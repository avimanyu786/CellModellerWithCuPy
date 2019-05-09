# CellModellerWithCuPy
## Enhancing GPU usage and Cell Growth on CellModeller with CuPy

This project starts with an attempt to replace NumPy and Math implementations on the existing Biophysics module on CellModeller with that of CuPy, that is an implementation of a NumPy-compatible multi-dimensional array on GPUs. The main goal here is to make use of CuPy's interoperability with CellModeller's existing and primary backend: PyOpenCL, to maximize GPU parallelization and reduce CPU dependency while simulating cell growth. As separate versions, PyOpenCL and OpenCL based data handling have also been modified for double precision. In another version, arrays used while moving/dividing cells and updating cell neighbours in the Biophysics module have been converted to Tensors via DLPack.
