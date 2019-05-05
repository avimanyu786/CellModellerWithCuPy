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
