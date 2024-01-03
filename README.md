# Co-Pylot-Widget
Widget for visualizing cad rendered components of hardware related to a stage position

This widget was created to help visualize spatial relation between stage and instrument components such as objectives and mounts. 
The goal of this widget is to be used by as many configurations as possible. 


## Installation
To install this package from the Github in editable mode, from this directory invoke: `pip install -e .`


## Intro and Basic Usage
To initialize the co-pylot widget, the stage position, coordinate transform between stage axes and GLViewWidget axes, 
volume, stage limits,field of view, and tile overlap need to be provided. All input values and widget attributes changed 
outside co-pylot are expected to be in the stage coordinate system. Co-pylot will handle all coordinate system 
transformations internally. Additionally, co-pylot will also return attributes queried from outside the widget in stage 
coordinate system. Users should ideally only consider the coordinate transformation when initializing widget

Stage position can have additional axes not used by the coordinate transformation map e.g. 
{'x':0, 'y':0, 'z':200, 't':0}. This is necessary when needing to create a transformation matrix that is dependent on a 
stage axis not related to x, y, z

An important note is that while attributes and models do not have to be in any particular unit, they MUST all be in the 
same unit in order for co-pylot to be a faithful representation of instrument.

````python
from co_pylot_widget.copylot import CoPylot
from qtpy.QtWidgets import QApplication
import sys

app = QApplication(sys.argv)
stagemap = CoPylot(stage_position= {'x':0, 'y':0, 'z':200, 't':0},
                   coordinate_transformation_map={'x': 'z', 'y': 'x', 'z': '-y'},
                   scanning_volume={'x':50, 'y':50, 'z':50},
                   limits={'x':[-100, 100], 'y':[-200, 200], 'z':[-100, 500]},
                   fov={'x': 20, 'y':20},
                   tile_overlap_pct={'x': 20, 'y':20})
sys.exit(app.exec_())
````

To update map with new stage coordinates, volume, ect., change the correlating attribute. Changing attributes triggers map update:
````python
# Attributes outside of widget are in stage coordinate system
stagemap.scanning_volume = {'x':400, 'y':50, 'z':150}  # Change scanning volume 
stagemap.fov = {'x': 50, 'y':50}  # Change fov
stagemap.coordinate_transformation_map = {'x': 'y', 'y': 'z', 'z': '-x'} # Change coordinate transform
````
To add cad models, call the function add_cad_model with arguments defining the corresponding name, file location,  and 
4x4 transformation matrix. The transformation matrix can contain static values as well as functions of x, y, and z as 
well as addition stage axes. The variables refer to the corresponding stage_position so all variables must be defined in 
the stage_position attribute. Usually, indexes that are functions of position are in the 3rd, 7th, and 11th as these 
refer to the model's position. However, rotational movement can also be simulated based on a stage axis.

Note: previously added models will be opaque when trying to see additionally added models

````python
# Add model that moves up and down with stage position and is centered within the x and z limits
stagemap.add_cad_model('mount', EXAMPLE_MOUNT,
                       (1, 0, 0, (abs(stagemap.limits['x'][1]) - abs(stagemap.limits['x'][0])) / 2, # x transformation
                        0, 1, 0, 'y',                                                               # y transformation
                        0, 0, 1, (abs(stagemap.limits['z'][1]) - abs(stagemap.limits['z'][0])) / 2, # z transformation
                        0, 0, 0, 1))

# Add model with rotational movement in relation to stage 
stagemap.add_cad_model('weirdmount', EXAMPLE_MOUNT,
                       (1, 0, 0, (abs(stagemap.limits['x'][1]) - abs(stagemap.limits['x'][0])) / 2+500,
                        0, 'cos(t)','sin(t)', 'y',
                        0, '-sin(t)', 'cos(t)', (abs(stagemap.limits['z'][1]) - abs(stagemap.limits['z'][0])) / 2,
                        0, 0, 0, 1))
````

To remove models, call the remove_cad_model with the argument defining corresponding name. 
````python
stagemap.remove_cad_model('weirdmount')
````

To add points to graph, click the 'Set Point' button. The dropdown menu allows to pick a color for the point;
textbox, a desired label. Point size will be based on fov size


## Advanced Usage
If editing co-pylot widget, it is important to note that the attributes stage_position, scanning_volume, limits, fov, 
and tile_overlap_pct are singalchangevar variables. The singalchangevar variables have two main features: when changed, 
they trigger the map to update and change coordinate system based on what instance they are called from. When a 
singalchangevar is called or changed from within the co-pylot widget, it is in the map coordinate system. When a 
singalchangevar is called or changed from anywhere outside the co-pylot widget, it is in the stage coordinate system. 
This was done to try and eliminate confusion and reduce manually transforming variables.
