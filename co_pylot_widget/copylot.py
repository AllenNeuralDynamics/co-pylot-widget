from qtpy.QtCore import Signal, Slot
from qtpy.QtWidgets import QWidget, QVBoxLayout, QCheckBox, QComboBox, QPushButton, QLineEdit, QHBoxLayout
import pyqtgraph.opengl as gl
from co_pylot_widget.signalchangevar import SignalChangeVar
from pyqtgraph.Qt import QtGui
import numpy as np
import qtpy.QtGui
import stl
from math import ceil
from sympy import symbols
from sympy.parsing.sympy_parser import parse_expr


class CoPylot(QWidget):
    stage_position = SignalChangeVar()
    scanning_volume = SignalChangeVar()
    limits = SignalChangeVar()
    fov = SignalChangeVar()
    tile_overlap_pct = SignalChangeVar()
    valueChanged = Signal((int,))

    def __init__(self, stage_position: dict,
                 coordinate_transformation_map: dict,
                 scanning_volume: dict,
                 limits: dict,
                 fov: dict,
                 tile_overlap_pct: dict):
        """Widget to visualize current stage position, imaging volume, tiles ect. in relation to stage hardware
         :param stage_position: position of stage in stage coordinate system e.g. {x:10, y:10, z:10}
         :param coordinate_transform: how stage coordinates translate to the GLViewWidget corrdinate system.
         Should be in format of GLWidget to stage coordinate mapping e.g. {x:-y, y:z, z:x}.
         :param scanning_volume: volume of scan in stage coordinate system e.g. {x:110, y:60, z:200}
         :param limits: limits of the stage travel used for centering the stl files.
         Limits should be a dictionary of lower and upper limits tuple for each direction
         e.g. {x:[-100, 100], y:[-100, 100], z:[-100, 100]
         :param fov: Size of camera fov in stage coordinate system to correctly draw on map e.g. {x:2304, y:1152}
         :param tile_overlap_pct: Defines how much overlap between tiles in stage coordinate system e.g. {x:15, y:15},
          """
        super().__init__()

        self._set_coordinate_transformation_map(coordinate_transformation_map)
        self.stage_position = stage_position
        self.scanning_volume = scanning_volume
        self.limits = limits
        self.fov = fov
        self.tile_overlap_pct = tile_overlap_pct
        self._cad_models = {}

        self.tiles = []

        # TODO: Add checks so fov and tile overlap have same values

        # Trigger the update of map when SignalChangeVar variable has changed
        self.valueChanged[int].connect(self.update_map)

        # Create map
        self.plot = self.create_map()
        self.tiling_widget = self.create_tiling_widget()
        self.add_point_widget = self.create_point_widget()

        widget = self.create_laid_out_widget('V', plot=self.plot, tile=self.tiling_widget, point=self.add_point_widget)
        self.setLayout(widget.layout())
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
        self.valueChanged.emit(0)  # Trigger update of map if coordinate transform changed

    def transform_variables(self):  # TODO: better name and description and make private maybe?
        """When new coordiante_transformation_map is given, update variables"""
        variables = ['stage_position', 'scanning_volume', 'limits', 'fov', 'tile_overlap_pct']
        for value in variables:
            stage_coords = self.map_to_stage_coord_transform(getattr(self, value))
            setattr(self, value, stage_coords)
            getattr(self, value).coord_sys = 'stage'

    def coord_transform(self, transformation: dict, values: dict):
        """Transform a dictionary of values from one coordinate system to another"""

        remap_values = {}
        for k, v in transformation.items():
            if v.lstrip('-') in values.keys():
                polarity = -1 if '-' in v else 1
                remap_values[k] = [i * polarity for i in values[v.lstrip('-')]] if type(values[v.lstrip('-')]) is list \
                    else polarity * values[v.lstrip('-')]
                if type(values[v.lstrip('-')]) is list:
                    remap_values[k] = list(np.sort(remap_values[k]))
                del values[v.lstrip('-')]
        overlapped_keys = [k for k in values.keys() if k in remap_values.keys()]
        for overlap in overlapped_keys: # Account for stage axis named x, y, z that does not correlate to map x, y, z
            values[overlap+'0'] = values[overlap]
            self._coordinate_transformation_map[overlap+'0'] = overlap
            del values[overlap]
        return {**remap_values, **values} # Add back in axes that aren't used in transformation

    def stage_to_map_coord_transform(self, stage_values: dict):
        """Remap a dictionary of values from stage coordinate system to map coordinate system"""
        return self.coord_transform(self._coordinate_transformation_map, stage_values)

    def map_to_stage_coord_transform(self, map_values: dict):
        """Remap a dictionary of values from map coordinate system to stage coordinate system"""

        map_to_stage = {v if '-' not in v else v.lstrip('-'): k if '-' not in v else '-' + k
                        for k, v in self._coordinate_transformation_map.items()}
        return self.coord_transform(map_to_stage, map_values)

    def create_point_widget(self):
        """Create widget to add points to graph"""

        self.point_color = QComboBox()
        self.point_color.addItems(qtpy.QtGui.QColor.colorNames())  # Add all QtGui Colors to drop down box

        mark = QPushButton('Set Point')
        mark.clicked.connect(self.set_point)  # Add point when button is presses

        self.point_label = QLineEdit()
        self.point_label.setPlaceholderText('point label')
        self.point_label.returnPressed.connect(self.set_point)  # Add text when button is pressed

        point_traits = self.create_laid_out_widget('V', color=self.point_color, label=self.point_label)
        point_widget = self.create_laid_out_widget('H', button=mark, traits=point_traits)
        point_widget.setMaximumSize(500, 100)
        return point_widget

    def set_point(self):

        """Set current position as point on graph"""

        # Remap sample_pos to gui coords and convert 1/10um to mm

        position = [self.stage_position.get('x', 0), self.stage_position.get('y', 0), self.stage_position.get('z', 0)]
        hue = qtpy.QtGui.QColor(self.point_color.currentText())  # Color of point determined by drop down box
        point = gl.GLScatterPlotItem(pos=position,
                                     size=min([abs(.15*v) for v in self.fov.values()]),
                                     color=hue,
                                     pxMode=False)
        info = self.point_label.text()  # Text comes from textbox
        info_point = gl.GLTextItem(pos=position,
                                   text=info,
                                   font=qtpy.QtGui.QFont('Helvetica', 15))
        self.plot.addItem(info_point)  # Add items to plot
        self.plot.addItem(point)

        self.point_label.clear()  # Clear text box

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

        grid_step = {k: (1 - abs(self.tile_overlap_pct.get(k, 0)) / 100.0) * self.fov.get(k, 1) for k in
                     ['x', 'y', 'z']}
        steps = {k: 1 + ceil((self.scanning_volume.get(k, 0) - self.fov.get(k, self.scanning_volume.get(k, 0))) /
                             grid_step.get(k, 0)) for k in ['x', 'y', 'z']}


        steps_order_axes = sorted(steps.keys())  # alphabetical list of keys
        for x in range(steps[steps_order_axes[0]]):  # refers to x axis
            for y in range(steps[steps_order_axes[1]]):  # refers to y axis
                for z in range(steps[steps_order_axes[2]]):  # refers to z axis
                    current_tile = {'x': x, 'y': y, 'z': z}
                    tile_offset = {k: (axis * grid_step[k]) - (.5 * self.fov.get(k, 0))
                                   for k, axis in current_tile.items()}
                    tile_pos = {k: v + self.stage_position[k] for k, v in tile_offset.items()}

                    # num_pos = [tile_pos['x'],
                    #            tile_pos['y'] + (.5 * 0.001 * (self.cfg.tile_specs['y_field_of_view'])),
                    #            tile_pos['z'] - (.5 * 0.001 * (self.cfg.tile_specs['x_field_of_view']))]

                    tile_volume = {k: self.fov.get(k, self.scanning_volume.get(k, 0)) for k in ['x', 'y', 'z']}
                    box = gl.GLBoxItem()  # Representing scan volume
                    box.translate(tile_pos['x'], tile_pos['y'], tile_pos['z'])
                    box.setSize(**tile_volume)
                    self.tiles.append(box)
                    self.tiles[-1].setColor(qtpy.QtGui.QColor('cornflowerblue'))
                    # Remove and add back cad models to see tiles through models
                    self.remove_models_from_plot()
                    self.plot.addItem(self.tiles[-1])
                    self.add_models_to_plot()

                    # self.tiles.append(gl.GLTextItem(pos=num_pos, text=str((self.xtiles*y)+x), font=qtpy.QtGui.QFont('Helvetica', 15)))
                    # self.plot.addItem(self.tiles[-1])       # Can't draw text while moving graph

    def add_cad_model(self, name: str, path: str, orientation):
        """Add cad model and set proper orientation
        :param path: the path of the stl file
        :param  orientation: the QMatrix 4x4 that dictate how stl will move within the map. To specify movement with
        the stage position, use the desired axis. Orientation should be in stage coordinates and will be transformed
        accordingly e. g.  (1, 0, 0, 'x',
                            0, 1, 0, 'y',
                            0, 0, 1, 'z',
                            0, 0, 0, 1) for model whose origin moves with stage position """

        # Load in stl file
        stl_mesh = stl.mesh.Mesh.from_file(path)
        points = stl_mesh.points.reshape(-1, 3)
        faces = np.arange(points.shape[0]).reshape(-1, 3)
        cad_model = gl.GLMeshItem(meshdata=gl.MeshData(vertexes=points, faces=faces),
                                  smooth=True, drawFaces=True, drawEdges=False, color=(0.5, 0.5, 0.5, 0.5),
                                  shader='edgeHilight', glOptions='translucent')
        # Create orientation matrix
        map_orientation = self.model_transform_matrix(orientation)

        cad_model.setTransform(map_orientation)
        self.plot.addItem(cad_model)
        self._cad_models[name] = [cad_model,orientation]

    def model_transform_matrix(self, orientation):
        """Function to create current transform matrix containing x,y,z functions.
        :param orientation: orientation QMatrix identifying the transform of model in stage coord sys e.g.
                                                                                        (1, 0, 0, 'x**2',
                                                                                         0, 1, 0, 'sin(y)',
                                                                                         0, 0, 1, 'z',
                                                                                         0, 0, 0, 1)"""
        matrix_transform = {v.lstrip('-'): k for k, v in self._coordinate_transformation_map.items() if '0' not in k}
        m = {matrix_transform[k]: orientation[i:i + 4] for k, i in zip(sorted(matrix_transform.keys()), range(0, 13, 4))}
        orientation = [*m['x'], *m['y'], *m['z'], *orientation[12:]]
        map_variable = {**matrix_transform, **{k:k for k in self.stage_position.keys() if k not in matrix_transform.keys()}}

        # symbols are still in stage coordinates so include stage and map variables
        variables = symbols(list(set(self.stage_position.keys()) | set(matrix_transform.keys())))
        for i, var in enumerate(orientation):  # Go through coordinates
            if type(var) == str:
                fun = parse_expr(var)
                expression = fun.subs([(var, self.stage_position[map_variable[str(var)]]) for var in variables])
                orientation[i] = expression.evalf()
        return qtpy.QtGui.QMatrix4x4(orientation)

    def remove_cad_model(self, name: str):
        """Remove cad model from widget"""

        self.plot.removeItem(self._cad_models[name][0])
        del self._cad_models[name]

    def remove_models_from_plot(self):
        """Convenience function to remove cad models from plot usually for visibility of other objects"""

        for model in self._cad_models.values():
            self.plot.removeItem(model[0])

    def add_models_to_plot(self):
        """Convenience function to add cad models back into plot usually for visibility of other objects"""

        for model in self._cad_models.values():
            self.plot.addItem(model[0])

    def create_map(self):
        """Create GLViewWidget and upload position, scan area, and cad models into view"""

        plot = gl.GLViewWidget()
        plot.opts['distance'] = 500  # TODO: Distance should be scaled to scan volume size and size of objectives/mount
        plot.opts['center'] = QtGui.QVector3D(self.stage_position['x'],
                                              self.stage_position['y'],
                                              self.stage_position['z'])
        self.scan_vol = gl.GLBoxItem()
        self.scan_vol.setColor(qtpy.QtGui.QColor('gold'))
        plot.addItem(self.scan_vol)

        self.pos = gl.GLBoxItem()
        self.pos.setColor(qtpy.QtGui.QColor('red'))
        plot.addItem(self.pos)

        return plot

    @Slot(int)
    def update_map(self, *args):
        """Update map with new values of key values"""

        shifted_pos = {k: v - (.5 * self.fov.get(k, 0)) for k, v in self.stage_position.items()}

        self.pos.setSize(*[self.fov.get(k, 0)for k in ['x', 'y', 'z']])
        self.pos.setTransform(qtpy.QtGui.QMatrix4x4(1, 0, 0, shifted_pos['x'],
                                                    0, 1, 0, shifted_pos['y'],
                                                    0, 0, 1, shifted_pos['z'],
                                                    0, 0, 0, 1))

        self.scan_vol.setSize(*[self.scanning_volume.get(k, 0)for k in ['x', 'y', 'z']])
        self.scan_vol.setTransform(qtpy.QtGui.QMatrix4x4(1, 0, 0, shifted_pos['x'],
                                                         0, 1, 0, shifted_pos['y'],
                                                         0, 0, 1, shifted_pos['z'],
                                                         0, 0, 0, 1))

        for k, model in self._cad_models.items():
            map_orientation = self.model_transform_matrix(model[1])
            model[0].setTransform(map_orientation)
        if self.tiling_widget.isChecked():
            self.draw_tiles()

    def create_laid_out_widget(self, struct: str, **kwargs):
        """Creates either a horizontal or vertical layout populated with widgets
        :param struct: specifies whether the layout will be horizontal, vertical, or combo
        :param kwargs: all widgets contained in layout"""

        layouts = {'H': QHBoxLayout(), 'V': QVBoxLayout()}
        widget = QWidget()
        if struct == 'V' or struct == 'H':
            layout = layouts[struct]
            for arg in kwargs.values():
                layout.addWidget(arg)

        elif struct == 'VH' or 'HV':
            bin0 = {}
            bin1 = {}
            j = 0
            for v in kwargs.values():
                bin0[str(v)] = v
                j += 1
                if j == 2:
                    j = 0
                    bin1[str(v)] = self.create_laid_out_widget(struct=struct[0], **bin0)
                    bin0 = {}
            return self.create_laid_out_widget(struct=struct[1], **bin1)

        layout.setContentsMargins(0, 0, 0, 0)
        widget.setLayout(layout)
        return widget

    coordinate_transformation_map = property(fget=_get_coordinate_transformation_map,
                                             fset=_set_coordinate_transformation_map)
