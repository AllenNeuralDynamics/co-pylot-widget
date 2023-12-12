from qtpy.QtCore import Qt, Signal, Slot
from qtpy.QtWidgets import QWidget, QVBoxLayout, QCheckBox
import pyqtgraph.opengl as gl
import inspect
from time import time
from stagemap_widget.signalchangevar import SignalChangeVar
from pyqtgraph.Qt import QtCore, QtGui
import numpy as np
import qtpy.QtGui
import stl
from math import ceil

class StageMap(QWidget):
    stage_position_um = SignalChangeVar()
    scanning_volume_um = SignalChangeVar()
    limits_um = SignalChangeVar()
    fov_um = SignalChangeVar()
    tile_overlap_pct = SignalChangeVar()
    valueChanged = Signal((int,))

    def __init__(self, stage_position_um: dict,
                 coordinate_transformation_map: dict,
                 scanning_volume_um: dict,
                 limits_um: dict,
                 fov_um: dict,
                 tile_overlap_pct: dict,
                 mount_stl_file: str = '',
                 objective_stl_file: str = ''):
        """Widget to visualize current stage position, imaging volume, tiles ect. in relation to stage hardware
         :param stage_position_um: position of stage in stage coordinate system e.g. {x:10, y:10, z:10}
         :param coordinate_transform: how stage coordinates translate to the GLViewWidget corrdinate system.
         Should be in format of GLWidget to stage coordinate mapping e.g. {x:-y, y:z, z:x}.
         :param scanning_volume_um: volume of scan in stage coordinate system e.g. {x:110, y:60, z:200}
         :param limits_um: limits of the stage travel used for centering the stl files.
         Limits should be a dictionary of lower and upper limits tuple for each direction
         e.g. {x:[-100, 100], y:[-100, 100], z:[-100, 100]
         :param fov_um: Size of camera fov in stage coordinate system to correctly draw on map e.g. {x:2304, y:1152}
         :param tile_overlap_pct: Defines how much overlap between tiles in stage coordinate system e.g. {x:15, y:15},
         :param mount_stl_file: optional string where the stl file of the stage mount is located.
         :param objective_stl_file: optional string where the stl file for the objectives is located
          """
        super().__init__()

        self._set_coordinate_transformation_map(coordinate_transformation_map)
        self.stage_position_um = stage_position_um
        self.scanning_volume_um = scanning_volume_um
        self.limits_um = limits_um
        self.fov_um = fov_um
        self.tile_overlap_pct = tile_overlap_pct
        self.mount_stl_file = mount_stl_file
        self.objective_stl_file = objective_stl_file


        self.tiles = []


        # Trigger the update of map when SignalChangeVar variable has changed
        self.valueChanged[int].connect(self.update_map)

        # Create map
        self.plot = self.create_map()
        self.tiling_widget = self.create_tiling_widget()

        layout = QVBoxLayout()
        layout.addWidget(self.plot)
        layout.addWidget(self.tiling_widget)
        self.setLayout(layout)
        self.update_map()
        self.show()

    def _get_coordinate_transformation_map(self):
        return self._coordinate_transformation_map

    def _set_coordinate_transformation_map(self, value: dict):
        if 'x' not in value.keys() or 'y' not in value.keys() or 'z' not in value.keys():
            raise KeyError
        try:
            self.transform_variables()
        except AttributeError:
            pass
        self._coordinate_transformation_map = value
        self.valueChanged.emit(0)   # Trigger update of map if coordinate transform changed

    def transform_variables(self):  #TODO: better name and description
        """When new coordiante_transformation_map is given, update variables"""
        variables = ['stage_position_um', 'scanning_volume_um', 'limits_um', 'fov_um', 'tile_overlap_pct']
        for value in variables:
            stage_coords = self.map_to_stage_coord_transform(getattr(self, value))
            setattr(self, value, stage_coords)
            getattr(self, value).coord_sys = 'stage'

    def coord_transform(self, transformation: dict, values: dict):
        """Transform a dictionary of values from one coordinate system to another"""

        possible_axes = [v.lstrip('-') for v in transformation.values()]
        for k in values.keys():
            if k not in possible_axes:
                raise IndexError(f'Axis {k} is not a possible axis based on current '
                                 f'transformation ({transformation}.')
        remap_values = {}
        for k, v in transformation.items():
            if v.lstrip('-') in values.keys():
                polarity = -1 if '-' in v else 1
                remap_values[k] = [i * polarity for i in values[v.lstrip('-')]] if type(values[v.lstrip('-')]) is list \
                    else polarity*values[v.lstrip('-')]
                if type(values[v.lstrip('-')]) is list:
                    remap_values[k] = list(np.sort(remap_values[k]))
                del values[v.lstrip('-')]
        return remap_values

    def stage_to_map_coord_transform(self, stage_values: dict):
        """Remap a dictionary of values from stage coordinate system to map coordinate system"""
        return self.coord_transform(self._coordinate_transformation_map, stage_values)

    def map_to_stage_coord_transform(self, map_values: dict):
        """Remap a dictionary of values from map coordinate system to stage coordinate system"""

        map_to_stage = { v if '-' not in v else v.lstrip('-'):k if '-' not in v else '-' + k
                        for k, v in self._coordinate_transformation_map.items()}
        return self.coord_transform(map_to_stage, map_values)

    def create_tiling_widget(self):
        """Create checkbox widget to turn on and off tiling"""

        tiling_widget = QCheckBox('See Tiling')
        tiling_widget.stateChanged.connect(self.set_tiling)  # Display tiling of scan when checked
        return tiling_widget
    def set_tiling(self, state):
        """Calculate grid steps and number of tiles for scan volume in config.
        :param state: state of QCheckbox when clicked. State 2 means checkmark is pressed: state 0 unpressed"""

        # State is 2 if checkmark is pressed
        if state == 2:
            self.draw_tiles()

        # State is 0 if checkmark is unpressed
        if state == 0:
            for item in self.tiles:
                if item in self.plot.items:
                    self.plot.removeItem(item)
            self.tiles = []

    def draw_tiles(self):
        """Draw tiles of proposed scan volume"""

        # Remove old tiles
        for item in self.tiles:
            if item in self.plot.items:
                self.plot.removeItem(item)
        self.tiles.clear()

        grid_step_um = {k:(1 - abs(self.tile_overlap_pct.get(k, 0)) / 100.0) * self.fov_um.get(k, 1) for k in ['x','y','z']}
        steps = {k:1+ceil((self.scanning_volume_um[k] - self.fov_um.get(k, self.scanning_volume_um[k]))/
                          grid_step_um[k]) for k in ['x','y','z']}

        steps_order_axes = sorted(steps.keys()) # alphabetical list of keys
        for x in range(steps[steps_order_axes[0]]): # refers to x axis
            for y in range(steps[steps_order_axes[1]]): # refers to y axis
                for z in range(steps[steps_order_axes[2]]): # refers to z axis
                    current_tile = {'x':x, 'y':y, 'z':z}
                    tile_offset = {k:(axis * grid_step_um[k]) - (.5 * self.fov_um.get(k, 0))
                                   for k, axis in current_tile.items()}
                    tile_pos = {k:v+self.stage_position_um[k] for k, v in tile_offset.items()}

                    # num_pos = [tile_pos['x'],
                    #            tile_pos['y'] + (.5 * 0.001 * (self.cfg.tile_specs['y_field_of_view_um'])),
                    #            tile_pos['z'] - (.5 * 0.001 * (self.cfg.tile_specs['x_field_of_view_um']))]

                    tile_volume = {k:self.fov_um.get(k, self.scanning_volume_um[k]) for k in ['x','y','z']}
                    box = gl.GLBoxItem()  # Representing scan volume
                    box.translate(tile_pos['x'], tile_pos['y'], tile_pos['z'])
                    box.setSize(**tile_volume)
                    self.tiles.append(box)
                    self.tiles[-1].setColor(qtpy.QtGui.QColor('cornflowerblue'))
                    #self.plot.removeItem(self.objectives)
                    self.plot.addItem(self.tiles[-1])
                    #self.plot.addItem(self.objectives)  # remove and add objectives to see tiles through objective
                    # self.tiles.append(gl.GLTextItem(pos=num_pos, text=str((self.xtiles*y)+x), font=qtpy.QtGui.QFont('Helvetica', 15)))
                    # self.plot.addItem(self.tiles[-1])       # Can't draw text while moving graph

    def create_map(self):
        """Create GLViewWidget and upload position, scan area, and cad models into view"""

        plot = gl.GLViewWidget()
        plot.opts['distance'] = 500 # TODO: Distance should be scaled to scan volume size and size of objectives/mount
        plot.opts['center'] = QtGui.QVector3D(self.stage_position_um['x'],
                                              self.stage_position_um['y'],
                                              self.stage_position_um['z'])
        self.scan_vol = gl.GLBoxItem()
        self.scan_vol.setColor(qtpy.QtGui.QColor('gold'))
        plot.addItem(self.scan_vol)

        self.pos = gl.GLBoxItem()
        self.pos.setColor(qtpy.QtGui.QColor('red'))
        plot.addItem(self.pos)

        try:
            objectives = stl.mesh.Mesh.from_file(self.objective_stl_file)
            points = objectives.points.reshape(-1, 3)
            faces = np.arange(points.shape[0]).reshape(-1, 3)
            self.objectives = gl.GLMeshItem(meshdata= gl.MeshData(vertexes=points, faces=faces),
                                            smooth=True, drawFaces=True, drawEdges=False, color=(0.5, 0.5, 0.5, 0.5),
                                            shader='edgeHilight', glOptions='translucent')

            mount = stl.mesh.Mesh.from_file(self.mount_stl_file)
            points = mount.points.reshape(-1, 3)
            faces = np.arange(points.shape[0]).reshape(-1, 3)
            self.mount = gl.GLMeshItem(meshdata=gl.MeshData(vertexes=points, faces=faces), smooth=True, drawFaces=True,
                                       drawEdges=False, color=(0.5, 0.5, 0.5, 0.5),shader='edgeHilight',
                                       glOptions='translucent')
            plot.addItem(self.objectives)
            plot.addItem(self.mount)

        except FileNotFoundError:
            # Create self.objectives and self.mount objects but don't add them to graph
            self.objectives = gl.GLBoxItem()
            self.mount = gl.GLBoxItem()

        return plot

    @Slot(int)
    def update_map(self, *args):
        """Update map with new values of key values"""
        shifted_pos = {k: v - (.5 * self.fov_um.get(k, 0)) for k, v in self.stage_position_um.items()}

        self.pos.setSize(self.fov_um.get('x', 0), self.fov_um.get('y', 0), self.fov_um.get('z', 0))
        self.pos.setTransform(qtpy.QtGui.QMatrix4x4(1, 0, 0, shifted_pos['x'],
                                                    0, 1, 0, shifted_pos['y'],
                                                    0, 0, 1, shifted_pos['z'],
                                                    0, 0, 0, 1))
        self.scan_vol.setSize(**self.scanning_volume_um)
        self.scan_vol.setTransform(qtpy.QtGui.QMatrix4x4(1, 0, 0, shifted_pos['x'],
                                                         0, 1, 0, shifted_pos['y'],
                                                         0, 0, 1, shifted_pos['z'],
                                                         0, 0, 0, 1))
        matrix_transform = {v.lstrip('-'): k for k, v in self._coordinate_transformation_map.items()}
        m = {matrix_transform['x']:(1,0,0),
             matrix_transform['y']:(0,1,0),
             matrix_transform['z']:(0,0,1)}
        self.objectives.setTransform(qtpy.QtGui.QMatrix4x4(m['x'][0], m['x'][1], m['x'][2], self.stage_position_um['x'],
                                                           m['y'][0], m['y'][1], m['y'][2], self.stage_position_um['y'],
                                                           m['z'][0], m['z'][1], m['z'][2], self.limits_um['z'][1],
                                                           0, 0, 0, 1))
        self.mount.setTransform(qtpy.QtGui.QMatrix4x4(m['x'][0], m['x'][1], m['x'][2], (abs(self.limits_um['x'][1])-
                                                                                        abs(self.limits_um['x'][0]))/2,
                                                      m['y'][0], m['y'][1], m['y'][2], (abs(self.limits_um['y'][1])-
                                                                                        abs(self.limits_um['y'][0]))/2,
                                                      m['z'][0], m['z'][1], m['z'][2], self.stage_position_um['z'],
                                                      0, 0, 0, 1))
        if self.tiling_widget.isChecked():
            self.draw_tiles()

    coordinate_transformation_map = property(fget=_get_coordinate_transformation_map,
                                             fset=_set_coordinate_transformation_map)

