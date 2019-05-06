from CellModeller.Regulation.ModuleRegulator import ModuleRegulator
# from CellModeller.Biophysics.BacterialModels.CLBacterium import CLBacterium
# from CellModeller.Biophysics.BacterialModels.CLBacteriumWithCuPy import CLBacteriumWithCuPy
# from CellModeller.Biophysics.BacterialModels.CLBacteriumWithGammaCuPyDoublePrecision import CLBacteriumWithGammaCuPyDoublePrecision
# from CellModeller.Biophysics.BacterialModels.CLBacteriumMovingCellsAsTensors import CLBacteriumMovingCellsAsTensors

from CellModeller.Biophysics.BacterialModels.CLBacteriumMovingAndDividingCellsAsTensors import CLBacteriumMovingAndDividingCellsAsTensors
from CellModeller.GUI import Renderers
#import numpy
#import math
import cupy
# cell_cols = {0:[0,1.0,0], 1:[1.0,0,0], 2:[0,0,1.0]} #RGB cell colours
# cell_lens = {0:1.0, 1:2.0, 2:3.5} #target cell lengths
# cell_growr = {0:2.0x4, 1:1.1x4, 2:0.8x4} #growth rates

cell_cols = {1: [0.0, 1.0, 1.0]}
#ecoli_diameter=cupy.random.uniform(0.25,1.0)
#cell_lens = {1: cupy.random.uniform(1.5,3.5)}
cell_growr = {1: 12.0}

def setup(sim):
    # Set biophysics, signalling, and regulation models
    # biophys = CLBacterium(sim, jitter_z=True, gamma=20, max_planes=1, max_cells=100000)
    # biophys = CLBacteriumWithGammaCuPyDoublePrecision(sim, jitter_z=True, rho=1.105, u=0.03, gammacoeff=0.59, max_planes=1, max_cells=67081)
    biophys = CLBacteriumMovingAndDividingCellsAsTensors(sim, jitter_z=True, rho=1.105, u=0.03, gammacoeff=0.59, max_planes=1, max_cells=670812)

    biophys.addPlane((0, 0, 0), (0, 0, 1), 1.0)  # Base plane
    # biophys.addPlane((20, 0, 0), (-1, 0, 0), 1.0)
    # biophys.addPlane((-20, 0, 0), (1, 0, 0), 1.0)
    # biophys.addPlane((0, 20, 0), (0, -1, 0), 1.0)
    # biophys.addPlane((0, -20, 0), (0, 1, 0), 1.0)
    # biophys.addPlane((0, 0, 110), (0, 0, -1), 1.0)

    # use this file for reg too
    regul = ModuleRegulator(sim, sim.moduleName)
    # Only biophys and regulation
    sim.init(biophys, regul, None, None)

    # Specify the initial cell and its location in the simulation
    sim.addCell(cellType=1, pos=(0, 0, 0), dir=(1, 0, 0))
    # sim.addCell(cellType=1, pos=(6, 0, 0), dir=(1,0,0))
    # sim.addCell(cellType=2, pos=(-6, 0, 0), dir=(1,0,0))

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


def init(cell):
    # Specify mean and distribution of initial cell size
    #cellVol = cell_lens[cell.cellType]
    #cellVol= ((cell_lens[cell.cellType]**3)*3.14) / 6
    ecoli_diameter = cupy.random.uniform(0.25, 1.0)
    cell_lens = {1: cupy.random.uniform(1.5, 3.5)}
    cellVol = cupy.add(cupy.divide ( cupy.multiply ( cupy.pi, cupy.multiply ( cupy.square (ecoli_diameter) , cell_lens[cell.cellType] ) ) , 4.0 ) , cupy.divide( cupy.multiply ( cupy.pi, cupy.power(ecoli_diameter , 3)) , 6.0 ) )

    cell.targetVol = cupy.add ( cellVol , cupy.random.uniform (0.0, 1.5) )
    #cell.targetVol = cellVol + cupy.random.uniform (0.0, 1.5)

    # Specify growth rate and color of cells
    #cell.growthRate = cell_growr[cell.cellType]
    cell.growthRate = 1.0

    #Variable growth rates from 1.0 to 12.0
    #cell.growthRate = cupy.random.uniform(1.0,cell_growr[cell.cellType])
    cell.color = cell_cols[cell.cellType]


def update(cells):
    # Iterate through each cell and flag cells that reach target size for division
    for (id, cell) in cells.iteritems():
        # Variable growth rates from 1.0 to 12.0
        cell.growthRate = cupy.random.uniform(0.0, cell_growr[cell.cellType])

        cell.color = [0.0 , cupy.random.uniform(0.8, 1.0), 1.0]


        if cell.volume > cell.targetVol:
            cell.divideFlag = True

        if cell.divideFlag == True:
            cell.growthRate = 0.0
            cell.color = [0.0, 0.4, 1.0]


def divide(parent, d1, d2):
    # Specify target cell size that triggers cell division
    #d1.targetVol = cell_lens[parent.cellType] + random.uniform(0.0, 0.5)
    #d2.targetVol = cell_lens[parent.cellType] + random.uniform(0.0, 0.5)

    ecoli_diameter = cupy.random.uniform(0.25, 1.0)
    cell_lens = {1: cupy.random.uniform(1.5, 3.5)}
    d1.targetVol = cupy.add ( cupy.add(cupy.divide(cupy.multiply(cupy.pi, cupy.multiply(cupy.square(ecoli_diameter), cell_lens[parent.cellType])), 4.0), cupy.divide(cupy.multiply(cupy.pi, cupy.power(ecoli_diameter, 3)), 6.0)) , cupy.random.uniform(0.0,1.5))

    ecoli_diameter = cupy.random.uniform(0.25, 1.0)
    cell_lens = {1: cupy.random.uniform(1.5, 3.5)}
    d2.targetVol = cupy.add ( cupy.add(cupy.divide(cupy.multiply(cupy.pi, cupy.multiply(cupy.square(ecoli_diameter), cell_lens[parent.cellType])), 4.0), cupy.divide(cupy.multiply(cupy.pi, cupy.power(ecoli_diameter, 3)), 6.0)), cupy.random.uniform(0.0, 1.5))
