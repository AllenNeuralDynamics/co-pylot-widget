from co_pylot_widget.copylot import CoPylot
import sys
from qtpy.QtWidgets import QApplication
import random
from time import sleep
import threading
from pathlib import Path
import os

RESOURCES_DIR = (
    Path(os.path.dirname(os.path.realpath(__file__))) / "resources"
)
EXAMPLE_OBJECTIVE = RESOURCES_DIR / "di-spim-tissue-map.STL"
EXAMPLE_MOUNT = RESOURCES_DIR / "di-spim-holder.STL"

def randomwalk1D(start_num, n, prob=10):
    x = start_num
    xposition = [x]
    probabilities = [-prob, prob]
    for i in range(1, n + 1):
        x += random.choice(probabilities)
        xposition.append(x)
    return xposition

def stagewalk(x, y, z, t):

    for i in range(0, 100):
        if i == 25:
            print('changing scanning volume')
            stagemap.scanning_volume = {'x':400, 'y':50, 'z':150}
        if i == 50:
            print('changing fov')
            stagemap.fov = {'x': 50, 'y':50}
        if i ==75:
            print('changing coordinate transform')
            stagemap.coordinate_transformation_map = {'x': 'y', 'y': 'z', 'z': '-x'}
        if i ==99:
            print('Removing objectives')
            stagemap.remove_cad_model('objectives')
        stagemap.stage_position = {'x':x[i], 'y':y[i], 'z':z[i], 't':t[i]}
        sleep(.5)

stage_position = {'x':0, 'y':0, 'z':200, 't':0}
coordinate_transformation_map = {'x': 'z', 'y': 'x', 'z': '-y'}
scanning_volume = {'x':50, 'y':50, 'z':50}
limits = {'x':[-100, 100], 'y':[-200, 200], 'z':[-100, 500]}
fov = {'x': 20, 'y':20}
tile_overlap_pct = {'x': 20, 'y':20}

app = QApplication(sys.argv)
stagemap = CoPylot(stage_position,
                   coordinate_transformation_map,
                   scanning_volume,
                   limits,
                   fov,
                   tile_overlap_pct)

stagemap.add_cad_model('mount', EXAMPLE_MOUNT,
                       (1, 0, 0, (abs(stagemap.limits['x'][1]) - abs(stagemap.limits['x'][0])) / 2,
                        0, 1, 0, 'y',
                        0, 0, 1, (abs(stagemap.limits['z'][1]) - abs(stagemap.limits['z'][0])) / 2,
                        0, 0, 0, 1))
stagemap.add_cad_model('objectives', EXAMPLE_OBJECTIVE,
                       (1, 0, 0, 'x',
                        0, 1, 0, stagemap.limits['y'][1],
                        0, 0, 1, 'z',
                        0, 0, 0, 1))
stagemap.add_cad_model('weirdmount', EXAMPLE_MOUNT,
                       (1, 0, 0, (abs(stagemap.limits['x'][1]) - abs(stagemap.limits['x'][0])) / 2+500,
                        0, 'cos(t)','sin(t)', 'y',
                        0, '-sin(t)', 'cos(t)', (abs(stagemap.limits['z'][1]) - abs(stagemap.limits['z'][0])) / 2,
                        0, 0, 0, 1))
x = randomwalk1D(stagemap.stage_position['x'], 100)
y = randomwalk1D(stagemap.stage_position['y'], 100)
z = randomwalk1D(stagemap.stage_position['z'], 100)
t = randomwalk1D(90, 100, 100)
t1 = threading.Thread(target=stagewalk, args=(x, y, z, t))
t1.start()
sys.exit(app.exec_())


