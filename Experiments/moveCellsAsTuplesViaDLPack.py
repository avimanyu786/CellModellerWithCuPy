    def moveCell(self, cellState, delta_pos):
        print "cell idx = %d" % cellState.idx
        i = cellState.idx
        cid = cellState.id
        print "cell center = "
        print self.cell_centers[i]
        print "delta_pos"
        print delta_pos
        #Converting self.cell_centers[i] (tuple) into a CuPy array
        #pos = cupy.array(tuple(self.cell_centers[i]))
        pos = tuple(cupy.fromDlpack(cupy.ndarray.toDlpack(self.cell_centers[i])))
        #Converting pos (CuPy array) into a DLPack Tensor
        #pos_tensor = pos.toDlpack()
        #Converting delta_pos (tuple) into a CuPy array
        #delta_pos_array = cupy.array(tuple(delta_pos))
        #Converting delta_pos_array (CuPy array) into a DLPack Tensor
        #delta_pos_tensor = delta_pos_array.toDlpack()

        delta_pos = tuple(cupy.fromDlpack(cupy.ndarray.toDlpack(delta_pos)))


        #pos[0:3] += cupy.array(tuple(delta_pos))
        #pos_tensor[0:3] += delta_pos_tensor
        pos[0:3] += delta_pos


        self.cell_centers[i] = pos
        #self.cell_centers[i] = pos_tensor
        self.simulator.cellStates[cid].pos = [self.cell_centers[i][j] for j in range(3)]
        #self.simulator.cellStates[cid].pos_tensor = [self.cell_centers[i][j] for j in range(3)]
        self.set_cells()
        self.updateCellState(cellState)

        
    def moveCell2(self, cellState, delta_pos):
        print "cell idx = %d" % cellState.idx
        i = cellState.idx
        cid = cellState.id
        print "cell center = "
        print self.cell_centers[i]
        print "delta_pos"
        print delta_pos
        #Converting self.cell_centers[i] (tuple) into a CuPy array
        pos = cupy.array(tuple(self.cell_centers[i]))
        #Converting pos (CuPy array) into a DLPack Tensor
        pos_tensor = cupy.fromDlpack(pos.toDlpack())

        #pos_tensor = pos.toDlpack()
        #pos_tensor = pos.toDlpack(range(0, 1000, 3))

        #Converting delta_pos (tuple) into a CuPy array
        delta_pos_array = cupy.array(tuple(delta_pos))
        #Converting delta_pos_array (CuPy array) into a DLPack Tensor
        delta_pos_tensor = cupy.fromDlpack(delta_pos_array.toDlpack())

        #delta_pos_tensor = delta_pos_array.toDlpack()


        #pos[0:3] += cupy.array(tuple(delta_pos))
        pos_tensor[0:3] += delta_pos_tensor

        #self.cell_centers[i] = pos
        self.cell_centers[i] = pos_tensor
        #self.simulator.cellStates[cid].pos = [self.cell_centers[i][j] for j in range(3)]
        self.simulator.cellStates[cid].pos_tensor = [self.cell_centers[i][j] for j in range(3)]
        self.set_cells()
