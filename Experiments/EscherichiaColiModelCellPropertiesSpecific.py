from CellModeller.Regulation.ModuleRegulator import ModuleRegulator
from CellModeller.Signalling.GridDiffusion import GridDiffusion
from CellModeller.Integration.CLCrankNicIntegrator import CLCrankNicIntegrator
# from CellModeller.Integration.CLCrankNicIntegratorCuPySinglePrecision import CLCrankNicIntegratorCuPySinglePrecision


#from CellModeller.Biophysics.BacterialModels.CLBacterium import CLBacterium
#from CellModeller.Biophysics.BacterialModels.CLBacterium2WithComputeNeighbours import CLBacterium2WithComputeNeighbours
# from CellModeller.Biophysics.BacterialModels.CLBacteriumWithDoublePrecision import CLBacteriumWithDoublePrecision
from CellModeller.Biophysics.BacterialModels.CLBacteriumWithGammaCuPySinglePrecision import CLBacteriumWithGammaCuPySinglePrecision

# from CellModeller.Biophysics.BacterialModels.CLBacteriumWithCuPy import CLBacteriumWithCuPy
# from CellModeller.Biophysics.BacterialModels.CLBacteriumWithGammaCuPyDoublePrecision import CLBacteriumWithGammaCuPyDoublePrecision
# from CellModeller.Biophysics.BacterialModels.CLBacteriumMovingCellsAsTensors import CLBacteriumMovingCellsAsTensors

#from CellModeller.Biophysics.BacterialModels.CLBacteriumMovingAndDividingCellsAsTensors import CLBacteriumMovingAndDividingCellsAsTensors

from CellModeller.GUI import Renderers

# import numpy
# import math
import cupy

# cell_cols = {0:[0,1.0,0], 1:[1.0,0,0], 2:[0,0,1.0]} #RGB cell colours
# cell_lens = {0:1.0, 1:2.0, 2:3.5} #target cell lengths
# cell_growr = {0:2.0x4, 1:1.1x4, 2:0.8x4} #growth rates
# 30-8-18

cell_cols = {1: [0.0, 1.0, 1.0]}
# cell_lens = {0: 0.8}
# Staphylococcus Aureus cell sizes range from 0.8 to 1.0 micrometer
# cell_lens = {0: cupy.random.uniform(0.8,1.0)}
# Maximum growth rate
cell_growr = {1: 12.0}

maximum_cells = 10000

grid_dim = (80, 80, 8)
grid_size = (4, 4, 4)
grid_orig = (-160, -160, -16)

n_signals = 1
n_species = 1


def setup(sim):
    # Set biophysics, signalling, and regulation models
    # biophys = CLBacterium(sim, jitter_z=True, gamma=20, max_planes=1, max_cells=100000)
    #biophys = CLBacterium(sim, jitter_z=True)

    #biophys = CLBacterium2WithComputeNeighbours(sim, jitter_z=True)
    # biophys = CLBacteriumWithDoublePrecision(sim, jitter_z=True) <- fails
    #biophys = CLBacteriumWithGammaCuPySinglePrecision(sim, jitter_z=True) #<- works

    biophys = CLBacteriumWithGammaCuPySinglePrecision(sim, jitter_z=True, rho=1.105, u=0.03, gammacoeff=0.59, max_planes=1, max_cells=10000)

    #biophys = CLBacteriumWithGammaCuPySinglePrecision(sim, jitter_z=True, rho=1.0039, u=0.02, gammacoeff=0.47,max_planes=1, max_cells=10000)  # <- works
    # biophys = CLBacteriumWithGammaCuPyDoublePrecision(sim, jitter_z=True, rho=1.0039, u=0.02, gammacoeff=0.47, max_planes=1, max_cells=6708)
    # biophys = CLBacteriumMovingCellsAsTensors(sim, jitter_z=True, rho=1.0039, u=0.02, gammacoeff=0.47, max_planes=1, max_cells=670812)
    # biophys = CLBacteriumMovingAndDividingCellsAsTensors(sim, jitter_z=True, rho=1.0039, u=0.02, gammacoeff=0.47, max_planes=1, max_cells=10000)
    # biophys = CLBacteriumMovingAndDividingCellsAsTensors(sim, jitter_z=True)

    sig = GridDiffusion(sim, n_signals, grid_dim, grid_size, grid_orig, [1.0,1.0])
    # integ = CLCrankNicIntegratorCuPySinglePrecision(sim, n_signals, n_species, maximum_cells, sig)
    integ = CLCrankNicIntegrator(sim, n_signals, n_species, maximum_cells, sig)

    # biophys = CLBacteriumWithGammaCuPyDoublePrecision(sim, jitter_z=True, gamma=10, max_planes=5, max_cells=67081)
    biophys.addPlane((0, 0, 0), (0, 0, 1), 1.0)  # Base plane
    # biophys.addPlane((20, 0, 0), (-1, 0, 0), 1.0)
    # biophys.addPlane((-20, 0, 0), (1, 0, 0), 1.0)
    # biophys.addPlane((0, 20, 0), (0, -1, 0), 1.0)
    # biophys.addPlane((0, -20, 0), (0, 1, 0), 1.0)
    # biophys.addPlane((0, 0, 110), (0, 0, -1), 1.0)

    # use this file for reg too
    regul = ModuleRegulator(sim, sim.moduleName)

    # Only biophys and regulation
    # sim.init(biophys, regul, None, None)
    sim.init(biophys, regul, sig, integ)

    # Specify the initial cell and its location in the simulation

    sim.addCell(cellType=1, pos=(0, 0, 0), dir=(1, 0, 0))
    # sim.addCell(cellType=1, pos=(6, 0, 0), dir=(1,0,0))
    # sim.addCell(cellType=2, pos=(-6, 0, 0), dir=(1,0,0))

    # Randomly choose positions for the cell. Here, there are six:
    # sim.addCell(cellType=0, pos=(cupy.random.uniform(-20,20), cupy.random.uniform(20,-20), 0), dir=(1, 0, 0))
    # sim.addCell(cellType=0, pos=(cupy.random.uniform(-20,20), cupy.random.uniform(20,-20), 0), dir=(1, 0, 0))
    # sim.addCell(cellType=0, pos=(cupy.random.uniform(-20,20), cupy.random.uniform(20,-20), 0), dir=(1, 0, 0))
    # sim.addCell(cellType=0, pos=(cupy.random.uniform(-20,20), cupy.random.uniform(20,-20), 0), dir=(1, 0, 0))
    # sim.addCell(cellType=0, pos=(cupy.random.uniform(-20,20), cupy.random.uniform(20,-20), 0), dir=(1, 0, 0))
    # sim.addCell(cellType=0, pos=(cupy.random.uniform(-20,20), cupy.random.uniform(20,-20), 0), dir=(1, 0, 0))

    # Add some objects to draw the models
    therenderer = Renderers.GLBacteriumRenderer(sim)
    sim.addRenderer(therenderer)
    sim.pickleSteps = 20


# def max_y_coord(cells):
# finds the largest y-coordinate in the colony
#   my = 0.0
#  for i,cell in cells.items():
#     my = max(my, cell.pos[2])
# return my

# cellVol= (((0.8**3)*3.14) / 6)
# cellVol = cell_lens[cell.cellType]

def init(cell):
    # Specify mean and distribution of initial cell size
    # cellVol = cell_lens[cell.cellType]
    # cellVol= ((cell_lens[cell.cellType]**3)*3.14) / 6
    ecoli_diameter = cupy.random.uniform(0.25, 1.0)
    cell_lens = {1: cupy.random.uniform(1.5, 3.5)}
    cellVol = cupy.add(cupy.divide(cupy.multiply(cupy.pi, cupy.multiply(cupy.square(ecoli_diameter), cell_lens[cell.cellType])), 4.0), cupy.divide(cupy.multiply(cupy.pi, cupy.power(ecoli_diameter, 3)), 6.0))

    cell.targetVol = cupy.add(cellVol, cupy.random.uniform(0.0, 1.5))
    # cell.targetVol = cellVol + cupy.random.uniform (0.0, 1.5)

    # Specify growth rate
    # cell.growthRate = cell_growr[cell.cellType]
    cell.growthRate = 1.0

    # Specify initial concentration of chemical species
    cell.species[:] = [0.0] * n_species
    # Specify initial concentration of signaling molecules
    cell.signals[:] = [0.0] * n_signals

    #color of cells
    cell.color = cell_cols[cell.cellType]


cl_prefix = \
    '''
        const float Da = 1.0f;
        const float ka = 1.f;

        float  alpha_in = species[1];
        float  alpha = signals[1];

        '''


# Da = diffusion rate of alpha through the cell membrane

def specRateCL():  # Add if/else, new species
    global cl_prefix
    return cl_prefix + '''
        if (cellType==1){
            rates[1] = ka + Da*(alpha-alpha_in)*area/gridVolume;

            } else {
            rates[1] = Da*(alpha-alpha_in)*area/gridVolume;
            }
            '''


def sigRateCL():  # Add
    global cl_prefix
    return cl_prefix + '''
        rates[1] = -Da*(alpha-alpha_in)*area/gridVolume;

        '''

    # cell.signals = [0]
    # cell.species = [0, 0, 0, 0, 0]

    # Variable growth rates from 1.0 to 12.0
    # cell.growthRate = cupy.random.uniform(1.0,cell_growr[cell.cellType])


def update(cells):
    v_max = 0.9
    Km = 0.0
    # Iterate through each cell and flag cells that reach target size for division
    for (id, cell) in cells.iteritems():
        # Variable growth rates from 1.0 to 12.0
        # cell.growthRate = cupy.random.uniform(0.0, cell_growr[cell.cellType])

        # cell.growthRate = cell.species[0] / (1 + cell.species[0])
        if cell.cellType == 1:
            # cell.color = [0.1 + cell.species[0] / 3.0, 0.1 + cell.species[0] / 3.0, 0.1]
            #cell.growthRate = 0.1 + v_max * cell.species[0] / (Km + cell.species[0])
            #cell.growthRate = cupy.add(0.1 , cupy.divide((v_max * cell.species[0]), (Km + cell.species[0])))
        #else:
            #cell.growthRate = 0.1 + cupy.divide((v_max * cell.species[0]), (Km + cell.species[0]))
            cell.growthRate = cell.signals[0] / (1 + cell.signals[0])


        # Fixed growth rate
        # cell.growthRate = 1.0

        # For all B&W shades and equalized RGB ranges starting from (0.0, 0.0, 0.0) to (1.0, 1.0, 1.0)
        # cell.growthRate = cupy.random.uniform(0.0,1.0)

        # Trying to check random growth rate...this one will rotate around b&w shades:
        # cell.color = [cupy.double(cell.growthRate)/12.0, cupy.double(cell.growthRate)/12.0, cupy.double(cell.growthRate)/12.0]

        # Checking again:
        # cell.color = [cupy.double(cell.growthRate)/12.0, cupy.double(cell.growthRate)/12.0, 0.0]

        # Checking with fixed color:
        # cell.color = [0.5, 0.5, 0.0]

        cell.color = [0.0 , cupy.random.uniform(0.8, 1.0), 1.0]
        # cell.color = [1.0, 0.7, 1.0]

        if cell.volume > cell.targetVol:
            # cell.growthRate = 0.0
            # cell.color = [1.0, 0.1, 1.0]
            # cell.color = [1.0, cupy.random.uniform(0.1, 0.2), 1.0]

            cell.divideFlag = True
            # cell.color = [0.8, 1.0, 0.7]
            # cell.color = [1.0, 0.1, 1.0]

        # Make cell division more noticeable with a saturated color of the cell:
        if cell.divideFlag == True:
            #cell.growthRate = 0.0
            cell.color = [0.0, 0.4, 1.0]
            # cell.color = [cupy.random.uniform(0.0, 1.0), cupy.random.uniform(0.0, 1.0), cupy.random.uniform(0.0, 1.0)]

        # if cell.growthRate == cupy.random.uniform(1.0,12.0):

        # else:
        # cell.color = [0.8, 1.0, 0.7]

        # If cell growth rate is very high, medium or low then add cells/conditions??
        #
        # Start with more cells?


def divide(parent, d1, d2):
    # Specify target cell size that triggers cell division
    # d1.targetVol = (((cell_lens[parent.cellType]**3)*3.14) / 6) + cupy.random.uniform(0.0,1.5)
    # d2.targetVol = (((cell_lens[parent.cellType]**3)*3.14) / 6) + cupy.random.uniform(0.0,1.5)
    ecoli_diameter = cupy.random.uniform(0.25, 1.0)
    cell_lens = {1: cupy.random.uniform(1.5, 3.5)}
    d1.targetVol = cupy.add(cupy.add ( cupy.divide(cupy.multiply(cupy.pi, cupy.multiply(cupy.square(ecoli_diameter), cell_lens[parent.cellType])), 4.0), cupy.divide(cupy.multiply(cupy.pi, cupy.power(ecoli_diameter, 3)), 6.0)), cupy.random.uniform(0.0, 1.5))

    ecoli_diameter = cupy.random.uniform(0.25, 1.0)
    cell_lens = {1: cupy.random.uniform(1.5, 3.5)}
    d2.targetVol = cupy.add(cupy.add ( cupy.divide(cupy.multiply(cupy.pi, cupy.multiply(cupy.square(ecoli_diameter), cell_lens[parent.cellType])), 4.0), cupy.divide(cupy.multiply(cupy.pi, cupy.power(ecoli_diameter, 3)), 6.0)), cupy.random.uniform(0.0, 1.5))