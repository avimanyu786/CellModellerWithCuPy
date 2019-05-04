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
        
    def progress_finalise(self):
        self.frame_no += 1
        self.progress_initialised = False
        self.seconds_elapsed = numpy.double(time.time() - self.time_begin)
        self.minutes_elapsed = (numpy.double(self.seconds_elapsed) / 60.0)
        self.hours_elapsed = (numpy.double(self.minutes_elapsed) / 60.0)
        if self.frame_no % 10 == 0:
            print '% 8i    % 8i cells    % 8i contacts    %f hour(s) or %f minute(s) or %f second(s)' % (
            self.frame_no, self.n_cells, self.n_cts, self.hours_elapsed, self.minutes_elapsed, self.seconds_elapsed)
        # pull cells from the device and update simulator
        if self.simulator:
            self.get_cells()
            # TJR: added incremental construction of this dict to same places as idToIdx - not fully tested
            #idxToId = {idx: id for id, idx in self.simulator.idToIdx.iteritems()}
            idxToId = {idx: id for id, idx in self.simulator.idToIdx.iteritems()}
            # TJR: add flag for this cos a bit time consuming
            if self.computeNeighbours:
                self.updateCellNeighbours(self.simulator.idxToId)
            for state in self.simulator.cellStates.values():
                self.updateCellState(state)
                
                
      def progress_finalise(self):
        self.frame_no += 1
        self.progress_initialised = False
        self.seconds_elapsed = numpy.double(time.time() - self.time_begin)
        self.minutes_elapsed = (numpy.double(self.seconds_elapsed) / 60.0)
        self.hours_elapsed = (numpy.double(self.minutes_elapsed) / 60.0)
        if self.frame_no % 10 == 0:
            print '% 8i    % 8i cells    % 8i contacts    %f hour(s) or %f minute(s) or %f second(s)' % (
            self.frame_no, self.n_cells, self.n_cts, self.hours_elapsed, self.minutes_elapsed, self.seconds_elapsed)
        # pull cells from the device and update simulator
        if self.simulator:
            self.get_cells()
            # TJR: added incremental construction of this dict to same places as idToIdx - not fully tested
            #idxToId = {idx: id for id, idx in self.simulator.idToIdx.iteritems()}

            #sim_items = list(self.simulator.cellStates.iteritems())

            #iidxToId = list(self.simulator.idxToId)

            #idxToId = {idx: id for id, idx in sim_items}

            #abc = cupy.array(sim_items)

            #idxToId = {idx: id for id, idx in cupy.fromDlpack(cupy.ndarray.toDlpack(sim_item))}

            # TJR: add flag for this cos a bit time consuming
            if self.computeNeighbours:
                #self.updateCellNeighbours(self.simulator.abc)
                self.updateCellNeighbours(self.simulator.idxToId)

            for state in self.simulator.cellStates.values():
                self.updateCellState(state)              
