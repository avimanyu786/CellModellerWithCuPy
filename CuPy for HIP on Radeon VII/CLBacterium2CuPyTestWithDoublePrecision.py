import sys
import math
import numpy
import cupy #CuPy Test: Seems to work...fingers crossed
import pyopencl as cl
import pyopencl.array as cl_array
from pyopencl.array import vec
from pyopencl.elementwise import ElementwiseKernel
from pyopencl.reduction import ReductionKernel
import random
import time

ct_map = {}


class CLBacterium2CuPyTestWithDoublePrecision:
    """A rigid body model of bacterial growth implemented using
    OpenCL. Here, gamma, the frictional drag is being calculated
    from mass density, growth rate, frictional drag coefficient
    and the reference area.
    """

    def __init__(self, simulator,
                 max_substeps=8,
                 max_cells=10000,
                 max_contacts=32,
                 max_planes=4,
                 max_sqs=192 ** 2,
                 grid_spacing=5,
                 muA=1.0,
                 rho=1.094,
                 u=0.03,
                 gammacoeff=0.59,
                 refarea=10000,
                 gamma=0,
                 dt=None,
                 cgs_tol=5e-3,
                 reg_param=0.1,
                 jitter_z=True,
                 alternate_divisions=False,
                 printing=True):

        self.frame_no = 0
        self.simulator = simulator
        self.regulator = None
        self.time_begin = time.time()
        self.seconds_elapsed = 0
        self.minutes_elapsed = 0
        self.hours_elapsed = 0
        self.max_cells = max_cells
        self.max_contacts = max_contacts
        self.max_planes = max_planes
        self.max_sqs = max_sqs
        self.grid_spacing = grid_spacing
        self.muA = muA
        self.rho = rho
        self.u = u
        self.gammacoeff = gammacoeff
        self.refarea = refarea
        #self.gamma = cupy.double((rho * u * u * gammacoeff * refarea) / 2)
        self.gamma = cupy.divide (cupy.multiply(rho , cupy.multiply(cupy.power(u, 2) , cupy.multiply(gammacoeff , refarea))) , 2) 
        self.dt = dt
        self.cgs_tol = cgs_tol
        self.reg_param = cupy.double(reg_param)

        self.max_substeps = max_substeps

        self.n_cells = 0
        self.n_cts = 0
        self.n_planes = 0

        self.next_id = 0

        self.grid_x_min = 0
        self.grid_x_max = 0
        self.grid_y_min = 0
        self.grid_y_max = 0
        self.n_sqs = 0

        self.init_cl()
        # self.init_kernels()
        self.init_data()

        self.parents = {}

        self.jitter_z = jitter_z
        self.alternate_divisions = alternate_divisions
        self.printing = printing
        self.progress_initialised = False
        self.sub_tick_initialised = False

    # Biophysical Model interface
    def reset(self):
        self.n_cells = 0
        self.n_cts = 0
        self.n_planes = 0

    def setRegulator(self, regulator):
        self.regulator = regulator
        self.init_kernels()

    def addCell(self, cellState, pos=(0, 0, 0), dir=(1, 0, 0), rad=0.5, **kwargs):
        i = cellState.idx
        self.n_cells += 1
        cid = cellState.id
        self.cell_centers[i] = tuple(pos + (0,))
        self.cell_dirs[i] = tuple(dir + (0,))
        self.cell_lens[i] = cellState.length
        self.cell_rads[i] = rad
        self.initCellState(cellState)
        self.set_cells()
        self.calc_cell_geom()  # cell needs a volume

    # ---
    # Some functions to modify existing cells (e.g. from GUI)
    # Eventually prob better to have a generic editCell() that deals with this stuff
    #
    def moveCell(self, cellState, delta_pos):
        print "cell idx = %d" % cellState.idx
        i = cellState.idx
        cid = cellState.id
        print "cell center = "
        print self.cell_centers[i]
        print "delta_pos"
        print delta_pos
        pos = cupy.array(tuple(self.cell_centers[i]))
        pos[0:3] += cupy.array(tuple(delta_pos))
        self.cell_centers[i] = pos
        self.simulator.cellStates[cid].pos = [self.cell_centers[i][j] for j in range(3)]
        self.set_cells()
        self.updateCellState(cellState)

    def addPlane(self, pt, norm, coeff):
        pidx = self.n_planes
        self.n_planes += 1
        self.plane_pts[pidx] = tuple(pt) + (0,)
        self.plane_norms[pidx] = tuple(norm) + (0,)
        self.plane_coeffs[pidx] = coeff
        self.set_planes()

    def hasNeighbours(self):
        return False

    def divide(self, parentState, daughter1State, daughter2State, *args, **kwargs):
        self.divide_cell(parentState.idx, daughter1State.idx, daughter2State.idx)
        # Initialise cellState data
        self.initCellState(daughter1State)
        self.initCellState(daughter2State)

    def init_cl(self):
        if self.simulator:
            (self.context, self.queue) = self.simulator.getOpenCL()

    def init_kernels(self):
        """Set up the OpenCL kernels."""
        from pkg_resources import resource_string
        #kernel_src = resource_string(__name__, 'CLBacterium2.cl')
        kernel_src = resource_string(__name__, 'CLBacteriumWithDoublePrecision.cl')


        self.program = cl.Program(self.context, kernel_src).build(cache_dir=False)
        # Some kernels that seem like they should be built into pyopencl...
        self.vclearf = ElementwiseKernel(self.context, "double8 *v", "v[i]=0.0", "vecclearf")
        self.vcleari = ElementwiseKernel(self.context, "int *v", "v[i]=0", "veccleari")
        self.vadd = ElementwiseKernel(self.context, "double8 *res, const double8 *in1, const double8 *in2",
                                      "res[i] = in1[i] + in2[i]", "vecadd")
        self.vsub = ElementwiseKernel(self.context, "double8 *res, const double8 *in1, const double8 *in2",
                                          "res[i] = in1[i] - in2[i]", "vecsub")
        self.vaddkx = ElementwiseKernel(self.context,
                                            "double8 *res, const double k, const double8 *in1, const double8 *in2",
                                            "res[i] = in1[i] + k*in2[i]", "vecaddkx")
        self.vsubkx = ElementwiseKernel(self.context,
                                            "double8 *res, const double k, const double8 *in1, const double8 *in2",
                                            "res[i] = in1[i] - k*in2[i]", "vecsubkx")

        # cell geometry kernels
        self.calc_cell_area = ElementwiseKernel(self.context, "double* res, double* r, double* l",
                                           "res[i] = 2.f*3.1415927f*r[i]*(2.f*r[i]+l[i])", "cell_area_kern")
        self.calc_cell_vol = ElementwiseKernel(self.context, "double* res, double* r, double* l",
                                          "res[i] = 3.1415927f*r[i]*r[i]*(2.f*r[i]+l[i])", "cell_vol_kern")

        # A dot product as sum of double4 dot products -
        # i.e. like flattening vectors of double8s into big double vectors
        # then computing dot
        # NB. Some openCLs seem not to implement dot(double8,double8) so split
        # into double4's
        self.vdot = ReductionKernel(self.context, numpy.double, neutral="0",
                reduce_expr="a+b", map_expr="dot(x[i].s0123,y[i].s0123)+dot(x[i].s4567,y[i].s4567)",
                arguments="__global double8 *x, __global double8 *y")

    def init_data(self):
        """Set up the data OpenCL will store on the device."""
        # cell data
        cell_geom = cupy.int(self.max_cells,)
        self.cell_centers = numpy.zeros(cell_geom, vec.double4)
        self.cell_centers_dev = cl_array.zeros(self.queue, cell_geom, vec.double4)
        self.cell_dirs = numpy.zeros(cell_geom, vec.double4)
        self.cell_dirs_dev = cl_array.zeros(self.queue, cell_geom, vec.double4)
        self.cell_lens = numpy.zeros(cell_geom, numpy.double)
        self.cell_lens_dev = cl_array.zeros(self.queue, cell_geom, numpy.double)
        self.pred_cell_centers = numpy.zeros(cell_geom, vec.double4)
        self.pred_cell_centers_dev = cl_array.zeros(self.queue, cell_geom, vec.double4)
        self.pred_cell_dirs = numpy.zeros(cell_geom, vec.double4)
        self.pred_cell_dirs_dev = cl_array.zeros(self.queue, cell_geom, vec.double4)
        self.pred_cell_lens = numpy.zeros(cell_geom, numpy.double)
        self.pred_cell_lens_dev = cl_array.zeros(self.queue, cell_geom, numpy.double)
        self.cell_rads = numpy.zeros(cell_geom, numpy.double)
        self.cell_rads_dev = cl_array.zeros(self.queue, cell_geom, numpy.double)
        self.cell_sqs = numpy.zeros(cell_geom, numpy.int32)
        self.cell_sqs_dev = cl_array.zeros(self.queue, cell_geom, numpy.int32)
        self.cell_n_cts = numpy.zeros(cell_geom, numpy.int32)
        self.cell_n_cts_dev = cl_array.zeros(self.queue, cell_geom, numpy.int32)
        self.cell_dcenters = numpy.zeros(cell_geom, vec.double4)
        self.cell_dcenters_dev = cl_array.zeros(self.queue, cell_geom, vec.double4)
        self.cell_dangs = numpy.zeros(cell_geom, vec.double4)
        self.cell_dangs_dev = cl_array.zeros(self.queue, cell_geom, vec.double4)
        self.cell_dlens = numpy.zeros(cell_geom, numpy.double)
        self.cell_dlens_dev = cl_array.zeros(self.queue, cell_geom, numpy.double)
        self.cell_target_dlens_dev = cl_array.zeros(self.queue, cell_geom, numpy.double)
        self.cell_growth_rates = numpy.zeros(cell_geom, numpy.double)

        # cell geometry calculated from l and r
        self.cell_areas_dev = cl_array.zeros(self.queue, cell_geom, numpy.double)
        self.cell_vols_dev = cl_array.zeros(self.queue, cell_geom, numpy.double)
        self.cell_old_vols_dev = cl_array.zeros(self.queue, cell_geom, numpy.double)

        # gridding
        self.sq_inds = numpy.zeros((self.max_sqs,), numpy.int32)
        self.sq_inds_dev = cl_array.zeros(self.queue, (self.max_sqs,), numpy.int32)
        self.sorted_ids = numpy.zeros(cell_geom, numpy.int32)
        self.sorted_ids_dev = cl_array.zeros(self.queue, cell_geom, numpy.int32)

        # constraint planes
        plane_geom = (self.max_planes,)
        self.plane_pts = numpy.zeros(plane_geom, vec.double4)
        self.plane_pts_dev = cl_array.zeros(self.queue, plane_geom, vec.double4)
        self.plane_norms = numpy.zeros(plane_geom, vec.double4)
        self.plane_norms_dev = cl_array.zeros(self.queue, plane_geom, vec.double4)
        self.plane_coeffs = numpy.zeros(plane_geom, numpy.double)
        self.plane_coeffs_dev = cl_array.zeros(self.queue, plane_geom, numpy.double)

        # contact data
        ct_geom = (cupy.int(self.max_cells), cupy.int(self.max_contacts))
        self.ct_frs = numpy.zeros(ct_geom, numpy.int32)
        self.ct_frs_dev = cl_array.zeros(self.queue, ct_geom, numpy.int32)
        self.ct_tos = numpy.zeros(ct_geom, numpy.int32)
        self.ct_tos_dev = cl_array.zeros(self.queue, ct_geom, numpy.int32)
        self.ct_dists = numpy.zeros(ct_geom, numpy.double)
        self.ct_dists_dev = cl_array.zeros(self.queue, ct_geom, numpy.double)
        self.ct_pts = numpy.zeros(ct_geom, vec.double4)
        self.ct_pts_dev = cl_array.zeros(self.queue, ct_geom, vec.double4)
        self.ct_norms = numpy.zeros(ct_geom, vec.double4)
        self.ct_norms_dev = cl_array.zeros(self.queue, ct_geom, vec.double4)
        self.ct_stiff_dev = cl_array.zeros(self.queue, ct_geom, numpy.double)
        self.ct_overlap_dev = cl_array.zeros(self.queue, ct_geom, numpy.double)

        # where the contacts pointing to this cell are collected
        self.cell_tos = numpy.zeros(ct_geom, numpy.int32)
        self.cell_tos_dev = cl_array.zeros(self.queue, ct_geom, numpy.int32)
        self.n_cell_tos = numpy.zeros(cell_geom, numpy.int32)
        self.n_cell_tos_dev = cl_array.zeros(self.queue, cell_geom, numpy.int32)

        # the constructed 'matrix'
        mat_geom = (self.max_cells * self.max_contacts,)
        self.ct_inds = numpy.zeros(mat_geom, numpy.int32)
        self.ct_inds_dev = cl_array.zeros(self.queue, mat_geom, numpy.int32)
        self.ct_reldists = numpy.zeros(mat_geom, numpy.double)
        self.ct_reldists_dev = cl_array.zeros(self.queue, mat_geom, numpy.double)

        self.fr_ents = numpy.zeros(mat_geom, vec.double8)
        self.fr_ents_dev = cl_array.zeros(self.queue, mat_geom, vec.double8)
        self.to_ents = numpy.zeros(mat_geom, vec.double8)
        self.to_ents_dev = cl_array.zeros(self.queue, mat_geom, vec.double8)

        # vectors and intermediates
        self.deltap = numpy.zeros(cell_geom, vec.double8)
        self.deltap_dev = cl_array.zeros(self.queue, cell_geom, vec.double8)
        self.Mx = numpy.zeros(mat_geom, numpy.double)
        self.Mx_dev = cl_array.zeros(self.queue, mat_geom, numpy.double)
        self.MTMx = numpy.zeros(cell_geom, vec.double8)
        self.MTMx_dev = cl_array.zeros(self.queue, cell_geom, vec.double8)
        self.Minvx_dev = cl_array.zeros(self.queue, cell_geom, vec.double8)

        # CGS intermediates
        self.p_dev = cl_array.zeros(self.queue, cell_geom, vec.double8)
        self.Ap_dev = cl_array.zeros(self.queue, cell_geom, vec.double8)
        self.res_dev = cl_array.zeros(self.queue, cell_geom, vec.double8)
        self.rhs_dev = cl_array.zeros(self.queue, cell_geom, vec.double8)

    def load_from_cellstates(self, cell_states):
        for (cid, cs) in cell_states.items():
            i = cs.idx
            self.cell_centers[i] = tuple(cs.pos) + (0,)
            self.cell_dirs[i] = tuple(cs.dir) + (0,)
            self.cell_rads[i] = cs.radius
            self.cell_lens[i] = cs.length

        self.n_cells = len(cell_states)
        self.set_cells()
        self.calc_cell_area(self.cell_areas_dev, self.cell_rads_dev, self.cell_lens_dev)
        self.calc_cell_vol(self.cell_vols_dev, self.cell_rads_dev, self.cell_lens_dev)

    def load_test_data(self):
        import CellModeller.Biophysics.BacterialModels.CLData as data
        self.cell_centers.put(range(len(data.pos)), data.pos)
        self.cell_dirs.put(range(len(data.dirs)), data.dirs)
        self.cell_lens.put(range(len(data.lens)), data.lens)
        self.cell_rads.put(range(len(data.rads)), data.rads)
        self.n_cells = data.n_cells
        self.set_cells()

    def load_1_cell(self):
        self.cell_centers.put([0], [(0, 0, 0, 0)])
        self.cell_dirs.put([0], [(1, 0, 0, 0)])
        self.cell_lens.put([0], [2.0])
        self.cell_rads.put([0], [0.5])
        self.n_cells = 1
        self.set_cells()

    def load_2_cells(self):
        root2 = cupy.sqrt(2.0)
        self.cell_centers.put([0, 1], [(-root2 - 0.5, 0, 0, 0), (root2 + 0.5, 0, 0, 0)])
        self.cell_dirs.put([0, 1], [(root2 / 2.0, root2 / 2.0, 0, 0), (-root2 / 2.0, root2 / 2.0, 0, 0)])
        self.cell_lens.put([0, 1], [4.0, 4.0])
        self.cell_rads.put([0, 1], [0.5, 0.5])
        self.n_cells = 2
        self.set_cells()

    def load_3_cells(self):
        root2 = cupy.sqrt(2.0)
        self.cell_centers.put([0, 1, 2],
                              [(-root2 - 0.5, 0, 0, 0), (root2 + 0.5, 0, 0, 0), (root2 + 0.5 + 3.3, 0, 0, 0)])
        self.cell_dirs.put([0, 1, 2],
                           [(root2 / 2.0, root2 / 2.0, 0, 0), (-root2 / 2.0, root2 / 2.0, 0, 0), (1, 0, 0, 0)])
        self.cell_lens.put([0, 1, 2], [3.0, 3.0, 3.0])
        self.cell_rads.put([0, 1, 2], [0.5, 0.5, 0.5])
        self.n_cells = 3
        self.set_cells()

    def load_3_cells_1_plane(self):
        root2 = cupy.sqrt(2.0)
        self.cell_centers.put([0, 1, 2],
                              [(-root2 - 0.5, 0, 0, 0), (root2 + 0.5, 0, 0, 0), (root2 + 0.5 + 3.3, 0, 0, 0)])
        self.cell_dirs.put([0, 1, 2],
                           [(root2 / 2.0, root2 / 2.0, 0, 0), (-root2 / 2.0, root2 / 2.0, 0, 0), (1, 0, 0, 0)])
        self.cell_lens.put([0, 1, 2], [3.0, 3.0, 3.0])
        self.cell_rads.put([0, 1, 2], [0.5, 0.5, 0.5])
        self.n_cells = 3
        self.set_cells()

        self.n_planes = 1
        self.plane_pts.put([0], [(0, 0, -0.5, 0)])
        self.plane_norms.put([0], [(0, 0, 1, 0)])
        self.plane_coeffs.put([0], [0.5])
        self.set_planes()

    def load_3_cells_2_planes(self):
        root2 = cupy.sqrt(2.0)
        self.cell_centers.put([0, 1, 2],
                              [(-root2 - 0.5, 0, 0, 0), (root2 + 0.5, 0, 0, 0), (root2 + 0.5 + 3.3, 0, 0, 0)])
        self.cell_dirs.put([0, 1, 2],
                           [(root2 / 2.0, root2 / 2.0, 0, 0), (-root2 / 2.0, root2 / 2.0, 0, 0), (1, 0, 0, 0)])
        self.cell_lens.put([0, 1, 2], [3.0, 3.0, 3.0])
        self.cell_rads.put([0, 1, 2], [0.5, 0.5, 0.5])
        self.n_cells = 3
        self.set_cells()

        self.n_planes = 2
        self.plane_pts.put([0, 1], [(0, 0, -0.5, 0), (0, 0, 0.5, 0)])
        self.plane_norms.put([0, 1], [(0, 0, 1, 0), (0, 0, -1, 0)])
        self.plane_coeffs.put([0, 1], [0.5, 0.1])
        self.set_planes()

    def load_1_cell_1_plane(self):
        self.cell_centers.put([0], [(0, 0, 0, 0)])
        self.cell_dirs.put([0], [(1, 0, 0, 0)])
        self.cell_lens.put([0], [3.0])
        self.cell_rads.put([0], [0.5])
        self.n_cells = 1
        self.set_cells()

        self.plane_pts.put([0], [(4, 0, 0, 0)])
        self.plane_norms.put([0], [(-1, 0, 0, 0)])
        self.plane_coeffs.put([0], [0.5])
        self.n_planes = 1
        self.set_planes()

    def load_1024_cells(self):
        d = 32
        for i in range(-d / 2, d / 2):
            for j in range(-d / 2, d / 2):
                n = (i + d / 2) * d + (j + d / 2)
                x = i * 3.5 + cupy.random.uniform(-0.05, 0.05)
                y = j * 2.0 + cupy.random.uniform(-0.05, 0.05)
                th = cupy.random.uniform(-0.15, 0.15)
                dir_x = cupy.cos(th)
                dir_y = cupy.sin(th)
                self.cell_centers.put([n], [(x, y, 0, 0)])
                self.cell_dirs.put([n], [(dir_x, dir_y, 0, 0)])
                self.cell_lens.put([n], [2])
                self.cell_rads.put([n], 0.5)
        self.n_cells = d * d
        self.set_cells()

    def get_cells(self):
        """Copy cell centers, dirs, lens, and rads from the device."""
        self.cell_centers[0:self.n_cells] = self.cell_centers_dev[0:self.n_cells].get()
        self.cell_dirs[0:self.n_cells] = self.cell_dirs_dev[0:self.n_cells].get()
        self.cell_lens[0:self.n_cells] = self.cell_lens_dev[0:self.n_cells].get()
        self.cell_rads[0:self.n_cells] = self.cell_rads_dev[0:self.n_cells].get()
        self.cell_dlens[0:self.n_cells] = self.cell_dlens_dev[0:self.n_cells].get()
        self.cell_dcenters[0:self.n_cells] = self.cell_dcenters_dev[0:self.n_cells].get()
        self.cell_dangs[0:self.n_cells] = self.cell_dangs_dev[0:self.n_cells].get()

    def set_cells(self):
        """Copy cell centers, dirs, lens, and rads to the device from local."""
        self.cell_centers_dev[0:self.n_cells].set(self.cell_centers[0:self.n_cells])
        self.cell_dirs_dev[0:self.n_cells].set(self.cell_dirs[0:self.n_cells])
        self.cell_lens_dev[0:self.n_cells].set(self.cell_lens[0:self.n_cells])
        self.cell_rads_dev[0:self.n_cells].set(self.cell_rads[0:self.n_cells])
        self.cell_dlens_dev[0:self.n_cells].set(self.cell_dlens[0:self.n_cells])
        self.cell_dcenters_dev[0:self.n_cells].set(self.cell_dcenters[0:self.n_cells])
        self.cell_dangs_dev[0:self.n_cells].set(self.cell_dangs[0:self.n_cells])

    def set_planes(self):
        """Copy plane pts, norms, and coeffs to the device from local."""
        self.plane_pts_dev[0:self.n_planes].set(self.plane_pts[0:self.n_planes])
        self.plane_norms_dev[0:self.n_planes].set(self.plane_norms[0:self.n_planes])
        self.plane_coeffs_dev[0:self.n_planes].set(self.plane_coeffs[0:self.n_planes])

    def get_cts(self):
        """Copy contact froms, tos, dists, pts, and norms from the device."""
        self.ct_frs[0:self.n_cts] = self.ct_frs_dev[0:self.n_cts].get()
        self.ct_tos[0:self.n_cts] = self.ct_tos_dev[0:self.n_cts].get()
        self.ct_dists[0:self.n_cts] = self.ct_dists_dev[0:self.n_cts].get()
        self.ct_pts[0:self.n_cts] = self.ct_pts_dev[0:self.n_cts].get()
        self.ct_norms[0:self.n_cts] = self.ct_norms_dev[0:self.n_cts].get()
        self.cell_n_cts[0:self.n_cells] = self.cell_n_cts_dev[0:self.n_cells].get()

    def matrixTest(self):
        x_dev = cl_array.zeros(self.queue, (self.n_cells,), vec.double8)
        Ax_dev = cl_array.zeros(self.queue, (self.n_cells,), vec.double8)
        opstring = ''
        for i in range(self.n_cells):
            x = cupy.zeros((self.n_cells,), vec.double8)
            for j in range(7):
                if j > 0:
                    x[i][j - 1] = 0.0
                x[i][j] = 1.0
                x_dev.set(x)
                self.calculate_Ax(Ax_dev, x_dev)
                Ax = Ax_dev.get()
                for ii in range(self.n_cells):
                    for jj in range(7):
                        opstring += str(Ax[ii][jj])
                        if ii != self.n_cells - 1 or jj != 6:
                            opstring = opstring + '\t'
                opstring = opstring + '\n'
        print "MTM"
        print opstring
        open('CellModeller/Biophysics/BacterialModels/matrix.mat', 'w').write(opstring)

    def dump_cell_data(self, n):
        import cPickle
        filename = 'data/data-%04i.pickle' % n
        outfile = open(filename, 'wb')
        data = (self.n_cells,
                self.cell_centers_dev.get(),
                self.cell_dirs_dev.get(),
                self.cell_lens_dev.get(),
                self.cell_rads_dev.get(),
                self.parents),
        cPickle.dump(data, outfile, protocol=-1)

    def dydt(self):
        self.set_cells()

    def finish(self):
        # pull cells from the device and update simulator
        if self.simulator:
            self.get_cells()
            for state in self.simulator.cellStates.values():
                self.updateCellState(state)

    def progress_init(self, dt):
        self.set_cells()
        # NOTE: by default self.dt=None, and time step == simulator time step (dt)
        if self.dt:
            self.n_ticks = int(math.ceil(dt / self.dt))
        else:
            self.n_ticks = 1
            # print "n_ticks = %d"%(self.n_ticks)
        self.actual_dt = dt / float(self.n_ticks)
        self.progress_initialised = True

    def progress(self):
        if self.n_ticks:
            if self.tick(self.actual_dt):
                self.n_ticks -= 1
            return False
        else:
            return True

    def progress_finalise(self):
        self.frame_no += 1
        self.progress_initialised = False
        self.seconds_elapsed = numpy.double(time.time() - self.time_begin)
        self.minutes_elapsed = (numpy.double(self.seconds_elapsed) / 60.0)  # + ((numpy.double(self.seconds_elapsed) % 60.0)/60.0)
        self.hours_elapsed = (numpy.double(self.minutes_elapsed) / 60.0)  # + ((numpy.double(self.minutes_elapsed) % 60.0)/60.0)
        if self.frame_no % 10 == 0:
            print '% 8i    % 8i cells    % 8i contacts    %f hour(s) or %f minute(s) or %f second(s)' % (self.frame_no, self.n_cells, self.n_cts, self.hours_elapsed, self.minutes_elapsed, self.seconds_elapsed)

        # pull cells from the device and update simulator
        if self.simulator:
            self.get_cells()
            for state in self.simulator.cellStates.values():
                self.updateCellState(state)

    def step(self, dt):
        """Step forward dt units of time.

        Assumes that:
        cell_centers is up to date when it starts.
        """
        if not self.progress_initialised:
            self.progress_init(dt)
        if self.progress():
            self.progress_finalise()
            return True
        else:
            return False

    def sub_tick_init(self, dt):
        # set target dlens (taken from growth rates set by updateCellStates)
        # self.cell_target_dlens_dev.set(dt*self.cell_growth_rates)
        # self.cell_dlens_dev.set(dt*self.cell_dlens)
        self.cell_dlens_dev.set(dt * self.cell_growth_rates)

        # redefine gridding based on the range of cell positions
        self.cell_centers = self.cell_centers_dev.get()
        self.update_grid()  # we assume local cell_centers is current

        # get each cell into the correct sq and retrieve from the device
        self.bin_cells()

        # sort cells and find sq index starts in the list
        self.cell_sqs = self.cell_sqs_dev.get()  # get updated cell sqs
        self.sort_cells()
        self.sorted_ids_dev.set(self.sorted_ids)  # push changes to the device
        self.sq_inds_dev.set(self.sq_inds)

        self.n_cts = 0
        self.vcleari(self.cell_n_cts_dev)  # clear the accumulated contact count
        self.sub_tick_i = 0
        self.sub_tick_initialised = True

    def tick(self, dt):
        if not self.sub_tick_initialised:
            self.sub_tick_init(dt)
        if self.sub_tick(dt):
            self.sub_tick_finalise()
            return True
        else:
            return False

    def sub_tick(self, dt):
        old_n_cts = self.n_cts
        self.predict()
        # find all contacts
        self.find_contacts()
        # place 'backward' contacts in cells
        self.collect_tos()

        self.sub_tick_i += 1
        new_cts = self.n_cts - old_n_cts
        if (new_cts > 0 or self.sub_tick_i == 0) and self.sub_tick_i < self.max_substeps:
            self.build_matrix()  # Calculate entries of the matrix
            # print "max cell contacts = %i"%cl_array.max(self.cell_n_cts_dev).get()
            self.CGSSolve(dt)  # invert MTMx to find deltap
            self.add_impulse()
            return False
        else:
            return True

    def sub_tick_finalise(self):
        # print "Substeps = %d"%self.sub_tick_i
        self.integrate()
        self.calc_cell_geom()
        self.sub_tick_initialised = False

    def initCellState(self, state):
        cid = state.id
        i = state.idx
        state.pos = [self.cell_centers[i][j] for j in range(3)]
        state.dir = [self.cell_dirs[i][j] for j in range(3)]
        state.radius = self.cell_rads[i]
        state.length = self.cell_lens[i]
        # for effective growth calulations
        state.oldLen = self.cell_lens[i]

        state.volume = state.length  # TO DO: do something better here
        pa = cupy.asnumpy(state.pos)
        da = cupy.asnumpy(state.dir)
        state.ends = (pa - da * state.length * 0.5, pa + da * state.length * 0.5)
        state.strainRate = state.growthRate / state.length
        self.cell_dlens[i] = state.growthRate
        state.startVol = state.volume

    def updateCellState(self, state):
        cid = state.id
        i = state.idx
        state.strainRate = self.cell_dlens[i] / state.length
        state.pos = [self.cell_centers[i][j] for j in range(3)]
        state.dir = [self.cell_dirs[i][j] for j in range(3)]
        state.radius = self.cell_rads[i]
        state.length = self.cell_lens[i]
        # currently the effective growth rate is calculated over the entire history of the cell
        state.effGrowth = ((state.effGrowth * state.cellAge) + state.length - state.oldLen)
        state.cellAge += 1
        state.effGrowth = state.effGrowth / state.cellAge
        state.oldLen = state.length

        state.volume = state.length  # TO DO: do something better here
        pa = cupy.asnumpy(state.pos)
        da = cupy.asnumpy(state.dir)
        state.ends = (pa - da * state.length * 0.5, pa + da * state.length * 0.5)
        # Length vel is linearisation of exponential growth
        self.cell_growth_rates[i] = state.growthRate * state.length

    def update_grid(self):
        """Update our grid_(x,y)_min, grid_(x,y)_max, and n_sqs.

        Assumes that our copy of cell_centers is current.
        """
        coords = self.cell_centers.view(cupy.double).reshape((self.max_cells, 4))

        x_coords = coords[:, 0]
        min_x_coord = x_coords.min()
        max_x_coord = x_coords.max()
        self.grid_x_min = int(math.floor(min_x_coord / self.grid_spacing))
        self.grid_x_max = int(math.ceil(max_x_coord / self.grid_spacing))
        if self.grid_x_min == self.grid_x_max:
            self.grid_x_max += 1

        y_coords = coords[:, 1]
        min_y_coord = y_coords.min()
        max_y_coord = y_coords.max()
        self.grid_y_min = int(math.floor(min_y_coord / self.grid_spacing))
        self.grid_y_max = int(math.ceil(max_y_coord / self.grid_spacing))
        if self.grid_y_min == self.grid_y_max:
            self.grid_y_max += 1

        self.n_sqs = (self.grid_x_max - self.grid_x_min) * (self.grid_y_max - self.grid_y_min)

    def bin_cells(self):
        """Call the bin_cells kernel.

        Assumes cell_centers is current on the device.

        Calculates cell_sqs.
        """
        self.program.bin_cells(self.queue,
                               (self.n_cells,),
                               None,
                               cupy.int32(self.grid_x_min),
                               cupy.int32(self.grid_x_max),
                               cupy.int32(self.grid_y_min),
                               cupy.int32(self.grid_y_max),
                               cupy.double(self.grid_spacing),
                               self.cell_centers_dev.data,
                               self.cell_sqs_dev.data).wait()

    def sort_cells(self):
        """Sort the cells by grid square and find the start of each
        grid square's cells in that list.

        Assumes that the local copy of cell_sqs is current.

        Calculates local sorted_ids and sq_inds.
        """
        self.sorted_ids.put(numpy.arange(self.n_cells), numpy.argsort(self.cell_sqs[:self.n_cells]))
        self.sorted_ids_dev[0:self.n_cells].set(self.sorted_ids[0:self.n_cells])

        # find the start of each sq in the list of sorted cell ids and send to the device
        sorted_sqs = cupy.sort(self.cell_sqs[:self.n_cells])
        self.sq_inds.put(numpy.arange(self.n_sqs),
                         numpy.searchsorted(sorted_sqs, numpy.arange(self.n_sqs), side='left'))
        self.sq_inds_dev.set(self.sq_inds)

    def find_contacts(self, predict=True):
        """Call the find_contacts kernel.

        Assumes that cell_centers, cell_dirs, cell_lens, cell_rads,
        cell_sqs, cell_dcenters, cell_dlens, cell_dangs,
        sorted_ids, and sq_inds are current on the device.

        Calculates cell_n_cts, ct_frs, ct_tos, ct_dists, ct_pts,
        ct_norms, ct_reldists, and n_cts.
        """
        if predict:
            centers = self.pred_cell_centers_dev
            dirs = self.pred_cell_dirs_dev
            lens = self.pred_cell_lens_dev
        else:
            centers = self.cell_centers_dev
            dirs = self.cell_dirs_dev
            lens = self.cell_lens_dev

        self.program.find_plane_contacts(self.queue,
                                         (self.n_cells,),
                                         None,
                                         cupy.int32(self.max_cells),
                                         cupy.int32(self.max_contacts),
                                         cupy.int32(self.n_planes),
                                         self.plane_pts_dev.data,
                                         self.plane_norms_dev.data,
                                         self.plane_coeffs_dev.data,
                                         centers.data,
                                         dirs.data,
                                         lens.data,
                                         self.cell_rads_dev.data,
                                         self.cell_n_cts_dev.data,
                                         self.ct_frs_dev.data,
                                         self.ct_tos_dev.data,
                                         self.ct_dists_dev.data,
                                         self.ct_pts_dev.data,
                                         self.ct_norms_dev.data,
                                         self.ct_reldists_dev.data,
                                         self.ct_stiff_dev.data).wait()

        self.program.find_contacts(self.queue,
                                   (self.n_cells,),
                                   None,
                                   cupy.int32(self.max_cells),
                                   cupy.int32(self.n_cells),
                                   cupy.int32(self.grid_x_min),
                                   cupy.int32(self.grid_x_max),
                                   cupy.int32(self.grid_y_min),
                                   cupy.int32(self.grid_y_max),
                                   cupy.int32(self.n_sqs),
                                   cupy.int32(self.max_contacts),
                                   centers.data,
                                   dirs.data,
                                   lens.data,
                                   self.cell_rads_dev.data,
                                   self.cell_sqs_dev.data,
                                   self.sorted_ids_dev.data,
                                   self.sq_inds_dev.data,
                                   self.cell_n_cts_dev.data,
                                   self.ct_frs_dev.data,
                                   self.ct_tos_dev.data,
                                   self.ct_dists_dev.data,
                                   self.ct_pts_dev.data,
                                   self.ct_norms_dev.data,
                                   self.ct_reldists_dev.data,
                                   self.ct_stiff_dev.data,
                                   self.ct_overlap_dev.data).wait()

        # set dtype to int32 so we don't overflow the int32 when summing
        # self.n_cts = self.cell_n_cts_dev.get().sum(dtype=numpy.int32)
        self.n_cts = cl_array.sum(self.cell_n_cts_dev).get()

    def collect_tos(self):
        """Call the collect_tos kernel.

        Assumes that cell_sqs, sorted_ids, sq_inds, cell_n_cts,
        ct_frs, and ct_tos are current on the device.

        Calculates cell_tos and n_cell_tos.
        """
        self.program.collect_tos(self.queue,
                                 (self.n_cells,),
                                 None,
                                 cupy.int32(self.max_cells),
                                 cupy.int32(self.n_cells),
                                 cupy.int32(self.grid_x_min),
                                 cupy.int32(self.grid_x_max),
                                 cupy.int32(self.grid_y_min),
                                 cupy.int32(self.grid_y_max),
                                 cupy.int32(self.n_sqs),
                                 cupy.int32(self.max_contacts),
                                 self.cell_sqs_dev.data,
                                 self.sorted_ids_dev.data,
                                 self.sq_inds_dev.data,
                                 self.cell_n_cts_dev.data,
                                 self.ct_frs_dev.data,
                                 self.ct_tos_dev.data,
                                 self.cell_tos_dev.data,
                                 self.n_cell_tos_dev.data).wait()

    def build_matrix(self):
        """Build the matrix so we can calculate M^TMx = Ax.

        Assumes cell_centers, cell_dirs, cell_lens, cell_rads,
        ct_inds, ct_frs, ct_tos, ct_dists, and ct_norms are current on
        the device.

        Calculates fr_ents and to_ents.
        """
        self.program.build_matrix(self.queue,
                                  (self.n_cells, self.max_contacts),
                                  None,
                                  cupy.int32(self.max_contacts),
                                  cupy.double(self.muA),
                                  cupy.double(self.gamma),
                                  self.pred_cell_centers_dev.data,
                                  self.pred_cell_dirs_dev.data,
                                  self.pred_cell_lens_dev.data,
                                  self.cell_rads_dev.data,
                                  self.cell_n_cts_dev.data,
                                  self.ct_frs_dev.data,
                                  self.ct_tos_dev.data,
                                  self.ct_pts_dev.data,
                                  self.ct_norms_dev.data,
                                  self.fr_ents_dev.data,
                                  self.to_ents_dev.data,
                                  self.ct_stiff_dev.data).wait()

    def calculate_Ax(self, Ax, x, dt):

        self.program.calculate_Mx(self.queue,
                                  (self.n_cells, self.max_contacts),
                                  None,
                                  cupy.int32(self.max_contacts),
                                  self.ct_frs_dev.data,
                                  self.ct_tos_dev.data,
                                  self.fr_ents_dev.data,
                                  self.to_ents_dev.data,
                                  x.data,
                                  self.Mx_dev.data).wait()
        self.program.calculate_MTMx(self.queue,
                                    (self.n_cells,),
                                    None,
                                    cupy.int32(self.max_contacts),
                                    self.cell_n_cts_dev.data,
                                    self.n_cell_tos_dev.data,
                                    self.cell_tos_dev.data,
                                    self.fr_ents_dev.data,
                                    self.to_ents_dev.data,
                                    self.Mx_dev.data,
                                    Ax.data).wait()
        # Tikhonov test
        # self.vaddkx(Ax, numpy.double(0.01), Ax, x)

        # Energy mimizing regularization
        self.program.calculate_Minv_x(self.queue,
                                      (self.n_cells,),
                                      None,
                                      cupy.double(self.muA),
                                      cupy.double(self.gamma),
                                      self.cell_dirs_dev.data,
                                      self.cell_lens_dev.data,
                                      self.cell_rads_dev.data,
                                      x.data,
                                      self.Minvx_dev.data).wait()

        # this was altered from dt*reg_param
        self.vaddkx(Ax, self.reg_param, Ax, self.Minvx_dev).wait()
        # 1/math.sqrt(self.n_cells) removed from the reg_param NB

        # print(self.Minvx_dev)

    def CGSSolve(self, dt, substep=False):
        # Solve A^TA\deltap=A^Tb (Ax=b)

        # There must be a way to do this using built in pyopencl - what
        # is it?!
        self.vclearf(self.deltap_dev)
        self.vclearf(self.rhs_dev)

        # put M^T n^Tv_rel in rhs (b)
        self.program.calculate_MTMx(self.queue,
                                    (self.n_cells,),
                                    None,
                                    cupy.int32(self.max_contacts),
                                    self.cell_n_cts_dev.data,
                                    self.n_cell_tos_dev.data,
                                    self.cell_tos_dev.data,
                                    self.fr_ents_dev.data,
                                    self.to_ents_dev.data,
                                    self.ct_reldists_dev.data,
                                    self.rhs_dev.data).wait()

        # res = b-Ax
        self.calculate_Ax(self.MTMx_dev, self.deltap_dev, dt)
        self.vsub(self.res_dev, self.rhs_dev, self.MTMx_dev)

        # p = res
        cl.enqueue_copy(self.queue, self.p_dev.data, self.res_dev.data)

        # rsold = l2norm(res)
        rsold = self.vdot(self.res_dev, self.res_dev).get()
        rsfirst = rsold
        if math.sqrt(rsold / self.n_cells) < self.cgs_tol:
            if self.printing and self.frame_no % 10 == 0:
                print '% 5i' % self.frame_no + '% 6i cells  % 6i cts  % 6i iterations  residual = %f' % (self.n_cells,
                                                                                                         self.n_cts, 0,
                                                                                                         rsold)
            return (0.0, rsold)

        # iterate
        # max iters = matrix dimension = 7 (dofs) * num cells
        # dying=False
        max_iters = self.n_cells * 7

        for iter in range(max_iters):
            # Ap
            self.calculate_Ax(self.Ap_dev, self.p_dev, dt)

            # p^TAp
            pAp = self.vdot(self.p_dev, self.Ap_dev).get()

            # alpha = rsold/p^TAp
            alpha = cupy.double(rsold / pAp)

            # x = x + alpha*p, x=self.disp
            self.vaddkx(self.deltap_dev, alpha, self.deltap_dev, self.p_dev)

            # res = res - alpha*Ap
            self.vsubkx(self.res_dev, alpha, self.res_dev, self.Ap_dev)

            # rsnew = l2norm(res)
            rsnew = self.vdot(self.res_dev, self.res_dev).get()

            # Test for convergence
            if math.sqrt(rsnew / self.n_cells) < self.cgs_tol:
                # if math.sqrt(rsnew/rsfirst) < self.cgs_tol:
                break

            # Stopped converging -> terminate
            # if rsnew/rsold>2.0:
            #    break

            # p = res + rsnew/rsold *p
            self.vaddkx(self.p_dev, cupy.double(rsnew / rsold), self.res_dev, self.p_dev)

            rsold = rsnew
            # print '        ',iter,rsold

        if self.printing and self.frame_no % 10 == 0:
            print '% 5i' % self.frame_no + '% 6i cells  % 6i cts  % 6i iterations  residual = %f' % (
            self.n_cells, self.n_cts, iter + 1, rsnew)
        return (iter + 1, math.sqrt(rsnew / self.n_cells))

    def predict(self):
        """Predict cell centers, dirs, lens for a timestep dt based
        on the current velocities.

        Assumes cell_centers, cell_dirs, cell_lens, cell_rads, and
        cell_dcenters, cell_dangs, cell_dlens are current on the device.

        Calculates new pred_cell_centers, pred_cell_dirs, pred_cell_lens.
        """
        self.program.predict(self.queue,
                             (self.n_cells,),
                             None,
                             self.cell_centers_dev.data,
                             self.cell_dirs_dev.data,
                             self.cell_lens_dev.data,
                             self.cell_dcenters_dev.data,
                             self.cell_dangs_dev.data,
                             self.cell_dlens_dev.data,
                             self.pred_cell_centers_dev.data,
                             self.pred_cell_dirs_dev.data,
                             self.pred_cell_lens_dev.data).wait()

    def integrate(self):
        """Integrates cell centers, dirs, lens for a timestep dt based
        on the current deltap.

        Assumes cell_centers, cell_dirs, cell_lens, cell_rads, and
        deltap are current on the device.

        Calculates new cell_centers, cell_dirs, cell_lens.
        """
        self.program.integrate(self.queue,
                               (self.n_cells,),
                               None,
                               self.cell_centers_dev.data,
                               self.cell_dirs_dev.data,
                               self.cell_lens_dev.data,
                               self.cell_dcenters_dev.data,
                               self.cell_dangs_dev.data,
                               self.cell_dlens_dev.data).wait()

    def add_impulse(self):
        self.program.add_impulse(self.queue, (self.n_cells,), None,
                                 cupy.double(self.muA),
                                 cupy.double(self.gamma),
                                 self.deltap_dev.data,
                                 self.cell_dirs_dev.data,
                                 self.cell_lens_dev.data,
                                 self.cell_rads_dev.data,
                                 self.cell_dcenters_dev.data,
                                 self.cell_dangs_dev.data,
                                 self.cell_target_dlens_dev.data,
                                 self.cell_dlens_dev.data).wait()

    def divide_cell(self, i, d1i, d2i):
        """Divide a cell into two equal sized daughter cells.

        Fails silently if we're out of cells.

        Assumes our local copy of cells is current.

        Calculates new cell_centers, cell_dirs, cell_lens, and cell_rads.
        """
        if self.n_cells >= self.max_cells:
            return
        # idxs of the two new cells
        a = d1i
        b = d2i

        # seems to be making shallow copies without the tuple calls
        parent_center = tuple(self.cell_centers[i])
        parent_dir = tuple(self.cell_dirs[i])
        parent_rad = self.cell_rads[i]
        parent_len = self.cell_lens[i]

        daughter_len = parent_len / 2.0 - parent_rad  # - 0.025
        daughter_offset = daughter_len / 2.0 + parent_rad
        center_offset = tuple([parent_dir[k] * daughter_offset for k in range(4)])

        self.cell_centers[a] = tuple([(parent_center[k] - center_offset[k]) for k in range(4)])
        self.cell_centers[b] = tuple([(parent_center[k] + center_offset[k]) for k in range(4)])

        if not self.alternate_divisions:
            cdir = numpy.array(parent_dir)
            jitter = numpy.random.uniform(-0.001, 0.001, 3)
            if not self.jitter_z: jitter[2] = 0.0
            cdir[0:3] += jitter
            cdir /= numpy.linalg.norm(cdir)
            self.cell_dirs[a] = cdir

            cdir = numpy.array(parent_dir)
            jitter = numpy.random.uniform(-0.001, 0.001, 3)
            if not self.jitter_z: jitter[2] = 0.0
            cdir[0:3] += jitter
            cdir /= numpy.linalg.norm(cdir)
            self.cell_dirs[b] = cdir
        else:
            cdir = numpy.array(parent_dir)
            tmp = cdir[0]
            cdir[0] = -cdir[1]
            cdir[1] = tmp
            self.cell_dirs[a] = cdir
            self.cell_dirs[b] = cdir

        self.cell_lens[a] = daughter_len
        self.cell_lens[b] = daughter_len
        self.cell_rads[a] = parent_rad
        self.cell_rads[b] = parent_rad

        self.n_cells += 1

        self.parents[b] = a

        vols = self.cell_vols_dev[0:self.n_cells].get()
        daughter_vol = vols[i] / 2.0
        vols[a] = daughter_vol
        vols[b] = daughter_vol
        self.cell_vols_dev[0:self.n_cells].set(vols)

        # Inherit velocities from parent (conserve momentum)
        parent_dlin = self.cell_dcenters[i]
        self.cell_dcenters[a] = parent_dlin
        self.cell_dcenters[b] = parent_dlin
        parent_dang = self.cell_dangs[i]
        self.cell_dangs[a] = parent_dang
        self.cell_dangs[b] = parent_dang

        # return indices of daughter cells
        return (a, b)

    def calc_cell_geom(self):
        """Calculate cell geometry using lens/rads on card."""
        # swap cell vols and cell_vols old
        tmp = self.cell_old_vols_dev[0:self.n_cells]
        self.cell_old_vols_dev[0:self.n_cells] = self.cell_vols_dev[0:self.n_cells]
        self.cell_vols_dev[0:self.n_cells] = tmp
        # update geometry
        self.calc_cell_area(self.cell_areas_dev[0:self.n_cells], \
                            self.cell_rads_dev[0:self.n_cells], \
                            self.cell_lens_dev[0:self.n_cells])
        self.calc_cell_vol(self.cell_vols_dev[0:self.n_cells], \
                           self.cell_rads_dev[0:self.n_cells], \
                           self.cell_lens_dev[0:self.n_cells])

    def profileGrid(self):
        if self.n_cts == 0:
            return
        import time
        t1 = time.clock()
        for i in range(1000):
            # redefine gridding based on the range of cell positions
            self.cell_centers = self.cell_centers_dev.get()
            self.update_grid()  # we assume local cell_centers is current

            # get each cell into the correct sq and retrieve from the device
            self.bin_cells()

            # sort cells and find sq index starts in the list
            self.cell_sqs = self.cell_sqs_dev.get()  # get updated cell sqs
            self.sort_cells()
            self.sorted_ids_dev.set(self.sorted_ids)  # push changes to the device
            self.sq_inds_dev.set(self.sq_inds)
        t2 = time.clock()
        print "Grid stuff timing for 1000 calls, time per call (s) = %f" % ((t2 - t1) * 0.001)
        open("grid_prof", "a").write("%i, %i, %f\n" % (self.n_cells, self.n_cts, (t2 - t1) * 0.001))

    def profileFindCts(self):
        if self.n_cts == 0:
            return
        import time
        t1 = time.clock()
        dt = 0.005
        for i in range(1000):
            self.n_cts = 0
            self.vcleari(self.cell_n_cts_dev)  # clear the accumulated contact count
            self.predict(dt)
            # find all contacts
            self.find_contacts(dt)
            # place 'backward' contacts in cells
            self.collect_tos()

            # compact the contacts so we can dispatch only enough threads
            # to deal with each
            self.ct_frs = self.ct_frs_dev.get()
            self.ct_tos = self.ct_tos_dev.get()
            self.compact_cts()
            self.ct_inds_dev.set(self.ct_inds)
        t2 = time.clock()
        print "Find contacts timing for 1000 calls, time per call (s) = %f" % ((t2 - t1) * 0.001)
        open("findcts_prof", "a").write("%i, %i, %f\n" % (self.n_cells, self.n_cts, (t2 - t1) * 0.001))

    def profileCGS(self):
        if self.n_cts == 0:
            return
        import time
        t1 = time.clock()
        dt = 0.005
        for i in range(1000):
            self.build_matrix(dt)  # Calculate entries of the matrix
            (iters, res) = self.CGSSolve()
            print "cgs prof: iters=%i, res=%f" % (iters, res)
        t2 = time.clock()
        print "CGS timing for 1000 calls, time per call (s) = %f" % ((t2 - t1) * 0.001)
        open("cgs_prof", "a").write("%i, %i, %i, %f\n" % (self.n_cells, self.n_cts, iters, (t2 - t1) * 0.001))


circ_pts = [(math.cos(math.radians(th)), math.sin(math.radians(th))) for th in range(-80, 90, 20)]


def display_grid(spacing, x_lo, x_hi, y_lo, y_hi):
    glBegin(GL_LINES)
    for i in range(x_lo, x_hi + 1):
        glVertex3f(i * spacing, y_lo * spacing, 0)
        glVertex3f(i * spacing, y_hi * spacing, 0)
    for i in range(y_lo, y_hi + 1):
        glVertex3f(x_lo * spacing, i * spacing, 0)
        glVertex3f(x_hi * spacing, i * spacing, 0)
    glEnd()


def display_cell(p, d, l, r):
    global quad
    pa = cupy.array([p[i] for i in range(3)])
    da = cupy.array([d[i] for i in range(3)])
    e1 = pa - da * l * 0.5
    e2 = pa + da * l * 0.5
    glEnable(GL_DEPTH_TEST)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glTranslatef(e1[0], e1[1], e1[2])
    zaxis = cupy.array([0, 0, 1])
    rotaxis = numpy.cross(da, zaxis)
    ang = cupy.arccos(cupy.dot(da, zaxis))
    #glRotatef(-ang * 180.0 / math.pi, rotaxis[0], rotaxis[1], rotaxis[2]) #####
    glRotatef(cupy.divide(cupy.multiply(-ang , 180.0),  cupy.pi), rotaxis[0], rotaxis[1], rotaxis[2])
    # glRotatef(90.0, 1, 0, 0)
    gluCylinder(quad, r, r, l, 8, 1)
    gluSphere(quad, r, 8, 8)
    glPopMatrix()
    glPushMatrix()
    glTranslatef(e2[0], e2[1], e2[2])
    gluSphere(quad, r, 8, 8)
    glPopMatrix()
    glDisable(GL_DEPTH_TEST)


'''
def display_cell(p, d, l, r):
    glEnable(GL_DEPTH_TEST)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    ang = math.atan2(d[1], d[0]) * 360.0 / (2.0*3.141593)
    glTranslatef(p[0], p[1], 0.0)
    glRotatef(ang, 0.0, 0.0, 1.0)
    glBegin(GL_POLYGON)
    glVertex3f(-l/2.0, -r, 0)
    glVertex3f(l/2.0, -r, 0)
    for x,y in circ_pts:
        glVertex3f(l/2.0 + x*r, y*r, 0.0)
    glVertex3f(l/2.0, r, 0)
    glVertex3f(-l/2.0, r, 0)
    for x,y in circ_pts:
        glVertex3f(-l/2.0 -x*r, -y*r, 0.0)
    glEnd()
    glPopMatrix()
    glDisable(GL_DEPTH_TEST)
'''


def display_cell_name(p, name):
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glTranslatef(p[0], p[1], p[2])
    glScalef(0.006, 0.006, 0.006)
    display_string(name)
    glPopMatrix()


def display_ct(pt, norm, fr_Lz):
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glTranslatef(pt[0], pt[1], pt[2])
    glBegin(GL_POINTS)
    glVertex3f(0.0, 0.0, 0.0)
    glEnd()
    glPushMatrix()
    glTranslatef(0.1, 0.1, 0.0)
    glScalef(0.004, 0.004, 0.004)
    display_string(fr_Lz)
    glPopMatrix()
    xaxis = cupy.array([1, 0, 0])
    norma = cupy.array([norm[i] for i in range(3)])
    rotaxis = numpy.cross(norma, xaxis)
    ang = cupy.arccos(cupy.dot(norma, xaxis))
    #glRotatef(-ang * 180.0 / math.pi, rotaxis[0], rotaxis[1], rotaxis[2])
    glRotatef(cupy.divide(cupy.multiply(-ang , 180.0),  cupy.pi), rotaxis[0], rotaxis[1], rotaxis[2])
    #    ang = math.atan2(norm[1], norm[0]) * 360.0 / (2.0*3.141593)
    #    glRotatef(ang, 0.0, 0.0, 1.0)
    glBegin(GL_LINES)
    glVertex3f(0.0, 0.0, 0.0)
    glVertex3f(1.0, 0.0, 0.0)
    glEnd()
    glBegin(GL_TRIANGLES)
    glVertex3f(1.0, 0.0, 0.0)
    glVertex3f(0.8, 0.2, 0.0)
    glVertex3f(0.8, -0.2, 0.0)
    glEnd()
    glPopMatrix()


def display_string(s):
    for ch in s:
        glutStrokeCharacter(GLUT_STROKE_ROMAN, ord(ch))


def cell_color(i):
    global founders
    while i not in founders:
        i = model.parents[i]
    return founders[i]


def display():
    global view_x, view_y, view_z, view_ang
    glEnable(GL_LINE_SMOOTH)
    glEnable(GL_POLYGON_SMOOTH)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    glClearColor(0.7, 0.7, 0.7, 0.7)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(60.0, 1.0, 0.1, 1000.0)

    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    glTranslatef(view_x, view_y, -view_z)
    glRotatef(view_ang, 1, 0, 0)

    glColor3f(0, 0, 0)
    glLineWidth(0.5)
    display_grid(model.grid_spacing, model.grid_x_min, model.grid_x_max, model.grid_y_min, model.grid_y_max)

    model.get_cells()
    for i in range(model.n_cells):
        # glColor3f(0.5, 0.5, 0.5)
        rr, gg, bb = cell_color(i)
        glColor3f(rr, gg, bb)
        # glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
        glPolygonMode(GL_FRONT, GL_FILL)
        display_cell(model.cell_centers[i], model.cell_dirs[i], model.cell_lens[i], model.cell_rads[i])

        glColor3f(0.0, 0.0, 0.0)
        # glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
        glPolygonMode(GL_FRONT, GL_LINE)
        glLineWidth(2.0)
        display_cell(model.cell_centers[i], model.cell_dirs[i], model.cell_lens[i], model.cell_rads[i])

        # glColor3f(0.0, 0.0, 0.0)
        # glLineWidth(1.0)
        # display_cell_name(model.cell_centers[i], str(i))

    glColor3f(0.1, 0.2, 0.4)
    glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
    glPointSize(1.0)
    glLineWidth(1.0)
    global ct_map
    new_ct_map = {}
    model.get_cts()
    for i in range(model.n_cells):
        for j in range(model.cell_n_cts[i]):
            other = model.ct_tos[i][j]
            new_ct_map[i, other] = (model.ct_pts[i][j], model.ct_norms[i][j], '% .4f' % model.ct_dists[i][j])
            if other < 0:
                glColor3f(0.5, 0.5, 0.1)
            elif (i, other) in ct_map:
                glColor3f(0.1, 0.4, 0.2)
            else:
                glColor3f(0.6, 0.1, 0.1)
            if other < 0:
                display_ct(model.ct_pts[i][j], model.ct_norms[i][j], '% .4f' % model.ct_dists[i][j])
    dead_cts_keys = set(ct_map.keys()) - set(new_ct_map.keys())
    for key in dead_cts_keys:
        pt, norm, dist = ct_map[key]
        glColor3f(0.1, 0.1, 0.6)
        display_ct(pt, norm, dist)
    ct_map = new_ct_map

    glFlush()
    glutSwapBuffers()


def reshape(w, h):
    l = min(w, h)
    glViewport(0, 0, l, l)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    glutPostRedisplay()


from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *

display_flag = False
quad = gluNewQuadric()


def idle():
    global frame_no
    global display_flag
    model.tick(0.01)
    model.get_cells()
    if model.frame_no % 100 == 0:
        # self.dump_cell_data(frame_no/100)
        print '% 8i    % 8i cells    % 8i contacts' % (model.frame_no, model.n_cells, model.n_cts)

    if model.frame_no % 100 == 0:
        for i in range(model.n_cells):
            if model.cell_lens[i] > 3.0 + random.uniform(0.0, 1.0):
                model.divide_cell(i)
    model.set_cells()

    if model.frame_no % 500 == 0 or display_flag:
        display()
        display_flag = False

    if model.frame_no % 1001 == 0:
        model.profileCGS()
        model.profileFindCts()
        model.profileGrid()

    model.frame_no += 1


view_x = 0
view_y = 0
view_z = 50
view_ang = 45.0


def key_pressed(*args):
    global view_x, view_y, view_z, view_ang, display_flag
    if args[0] == 'j':
        view_x += 2
    elif args[0] == 'l':
        view_x -= 2
    elif args[0] == 'i':
        view_y -= 2
    elif args[0] == 'k':
        view_y += 2
    elif args[0] == 'e':
        view_z -= 2
    elif args[0] == 'd':
        view_z += 2
    elif args[0] == 'z':
        view_ang += 2
    elif args[0] == 'x':
        view_ang -= 2
    elif args[0] == '\x1b':
        exit()
    elif args[0] == 'f':
        display_flag = True


import time


class state:
    pass


if __name__ == '__main__':
    numpy.set_printoptions(precision=8,
                           threshold=10000,
                           linewidth=180)

    ct_map = {}

    glutInit(sys.argv)
    glutInitWindowSize(1400, 1400)
    glutInitWindowPosition(0, 0)
    glutCreateWindow('CLBacterium2CuPyTest')
    glutDisplayFunc(display)
    glutReshapeFunc(reshape)
    glutKeyboardFunc(key_pressed)
    glutIdleFunc(idle)

    from CellModeller.Simulator import Simulator

    sim = Simulator(None, 0.01)
    model = CLBacterium2CuPyTest(sim, max_cells=2 ** 15, max_contacts=32, max_sqs=64 * 16, jitter_z=False, reg_param=2,
                         gamma=5.0)
    model.addPlane((0, -16, 0), (0, 1, 0), 1)
    model.addPlane((0, 16, 0), (0, -1, 0), 1)
    # model = CLBacterium2(None)

    # model.load_test_data()
    # model.load_3_cells_2_planes()
    # model.load_1024_cells()
    # model.load_3_cells()

    cs = state()
    cs.id = 0
    cs.idx = 0
    cs.growthRate = 0.5
    model.addCell(cs)
    founders = {0: (0.5, 0.3, 0.3),
                1: (0.3, 0.5, 0.3),
                2: (0.3, 0.3, 0.5)}
    # model.load_3_cells_2_planes()
    # model.load_1024_cells()
    model.load_3_cells()

    glutMainLoop()

