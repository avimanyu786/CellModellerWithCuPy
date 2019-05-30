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
# 30-8-18

cell_cols = {0: [0.0, 1.0, 1.0]}
#cell_lens = {0: 0.8}
#Staphylococcus Aureus cell sizes range from 0.8 to 1.0 micrometer
#cell_lens = {0: cupy.random.uniform(0.8,1.0)}
#Maximum growth rate
cell_growr = {0: 12.0}



def setup(sim):
    # Set biophysics, signalling, and regulation models
    # biophys = CLBacterium(sim, jitter_z=True, gamma=20, max_planes=1, max_cells=100000)
    #biophys = CLBacteriumWithGammaCuPyDoublePrecision(sim, jitter_z=True, rho=1.0039, u=0.02, gammacoeff=0.47, max_planes=1, max_cells=6708)
    #biophys = CLBacteriumMovingCellsAsTensors(sim, jitter_z=True, rho=1.0039, u=0.02, gammacoeff=0.47, max_planes=1, max_cells=670812)
    biophys = CLBacteriumMovingAndDividingCellsAsTensors(sim, jitter_z=True, rho=1.0039, u=0.02, gammacoeff=0.47, max_planes=1, max_cells=20000)



    #biophys = CLBacteriumWithGammaCuPyDoublePrecision(sim, jitter_z=True, gamma=10, max_planes=5, max_cells=67081)
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


    sim.addCell(cellType=0, pos=(0, 0, 0), dir=(1, 0, 0))
    # sim.addCell(cellType=1, pos=(6, 0, 0), dir=(1,0,0))
    # sim.addCell(cellType=2, pos=(-6, 0, 0), dir=(1,0,0))

    #Randomly choose positions for the cell. Here, there are six:
    #sim.addCell(cellType=0, pos=(cupy.random.uniform(-20,20), cupy.random.uniform(20,-20), 0), dir=(1, 0, 0))
    #sim.addCell(cellType=0, pos=(cupy.random.uniform(-20,20), cupy.random.uniform(20,-20), 0), dir=(1, 0, 0))
    #sim.addCell(cellType=0, pos=(cupy.random.uniform(-20,20), cupy.random.uniform(20,-20), 0), dir=(1, 0, 0))
    #sim.addCell(cellType=0, pos=(cupy.random.uniform(-20,20), cupy.random.uniform(20,-20), 0), dir=(1, 0, 0))
    #sim.addCell(cellType=0, pos=(cupy.random.uniform(-20,20), cupy.random.uniform(20,-20), 0), dir=(1, 0, 0))
    #sim.addCell(cellType=0, pos=(cupy.random.uniform(-20,20), cupy.random.uniform(20,-20), 0), dir=(1, 0, 0))





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

#cellVol= (((0.8**3)*3.14) / 6)
#cellVol = cell_lens[cell.cellType]

def init(cell):
    # Specify mean and distribution of initial cell size
    #cellVol = cell_lens[cell.cellType]
    #cellVol= ((cell_lens[cell.cellType]**3)*3.14) / 6
    cell_lens = {0: cupy.random.uniform(0.8, 1.0)}
    cellVol = cupy.divide ( cupy.multiply ( cupy.power ( cell_lens[cell.cellType] , 3 ) , cupy.pi ) , 6.0 )

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

        #Fixed growth rate
        #cell.growthRate = 1.0

        #For all B&W shades and equalized RGB ranges starting from (0.0, 0.0, 0.0) to (1.0, 1.0, 1.0)
        #cell.growthRate = cupy.random.uniform(0.0,1.0)


        #Trying to check random growth rate...this one will rotate around b&w shades:
        #cell.color = [cupy.double(cell.growthRate)/12.0, cupy.double(cell.growthRate)/12.0, cupy.double(cell.growthRate)/12.0]

        #Checking again:
        #cell.color = [cupy.double(cell.growthRate)/12.0, cupy.double(cell.growthRate)/12.0, 0.0]

        #Checking with fixed color:
        #cell.color = [0.5, 0.5, 0.0]


        cell.color = [0.0 , cupy.random.uniform(0.8, 1.0), 1.0]
        #cell.color = [1.0, 0.7, 1.0]

        if cell.volume > cell.targetVol:
            #cell.growthRate = 0.0
            #cell.color = [1.0, 0.1, 1.0]
            #cell.color = [1.0, cupy.random.uniform(0.1, 0.2), 1.0]

            cell.divideFlag = True
            #cell.color = [0.8, 1.0, 0.7]
            #cell.color = [1.0, 0.1, 1.0]

        # Make cell division more noticeable with a saturated color of the cell:
        if cell.divideFlag == True:
            cell.growthRate = 0.0
            cell.color = [0.0, 0.4, 1.0]
            #cell.color = [cupy.random.uniform(0.0, 1.0), cupy.random.uniform(0.0, 1.0), cupy.random.uniform(0.0, 1.0)]

        #if cell.growthRate == cupy.random.uniform(1.0,12.0):

        #else:
            #cell.color = [0.8, 1.0, 0.7]

        # If cell growth rate is very high, medium or low then add cells/conditions??
        #
        # Start with more cells?
        #
        # Put darker shades as cells age?
        
def divide(parent, d1, d2):
    # Specify target cell size that triggers cell division
    #d1.targetVol = (((cell_lens[parent.cellType]**3)*3.14) / 6) + cupy.random.uniform(0.0,1.5)
    #d2.targetVol = (((cell_lens[parent.cellType]**3)*3.14) / 6) + cupy.random.uniform(0.0,1.5)
    cell_lens = {0: cupy.random.uniform(0.8, 1.0)}
    d1.targetVol = cupy.add ( cupy.divide ( cupy.multiply ( cupy.power ( cell_lens[parent.cellType] , 3 ) , cupy.pi ) , 6.0 ) , cupy.random.uniform (0.0 , 1.5) )
    cell_lens = {0: cupy.random.uniform(0.8, 1.0)}
    d2.targetVol = cupy.add ( cupy.divide ( cupy.multiply ( cupy.power ( cell_lens[parent.cellType] , 3 ) , cupy.pi ) , 6.0 ) , cupy.random.uniform (0.0 , 1.5) )

