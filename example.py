from copylot_widget.copylot import StageMap
import sys
from qtpy.QtWidgets import QApplication
import random
from time import sleep
import threading

def randomwalk1D(start_num, n):
    x = start_num
    xposition = [x]
    probabilities = [-10, 10]
    for i in range(1, n + 1):
        x += random.choice(probabilities)
        xposition.append(x)
    return xposition

def stagewalk(x, y, z):
    for i in range(0, 100):
        if i == 25:
            print('changing scanning volume')
            stagemap.scanning_volume_um = {'x':400, 'y':50, 'z':150}
        if i == 50:
            print('changing fov')
            stagemap.fov_um = {'x': 50, 'y':50}
        if i ==75:
            print('changing coordinate transform')
            stagemap.coordinate_transformation_map = {'x': 'y', 'y': 'z', 'z': '-x'}
        stagemap.stage_position_um = {'x':x[i], 'y':y[i], 'z':z[i]}
        sleep(.5)

stage_position_um = {'x':0, 'y':0, 'z':200}
coordinate_transformation_map = {'x': 'z', 'y': 'x', 'z': '-y'}
scanning_volume_um = {'x':50, 'y':50, 'z':50}
limits_um = {'x':[-100,100], 'y':[-200,200], 'z':[-100,500]}
fov_um = {'x': 20, 'y':20}
tile_overlap_pct = {'x': 20, 'y':20}

app = QApplication(sys.argv)
stagemap = StageMap(stage_position_um,
                 coordinate_transformation_map,
                 scanning_volume_um,
                 limits_um,
                 fov_um,
                 tile_overlap_pct,)

stagemap.add_cad_model('mount', r'C:\Users\micah.woodard\Downloads\dispim_files\di-spim-holder.STL',
                       (1, 0, 0, (abs(stagemap.limits_um['x'][1])-abs(stagemap.limits_um['x'][0]))/2,
                        0, 1, 0, 'y',
                        0, 0, 1, (abs(stagemap.limits_um['z'][1])-abs(stagemap.limits_um['z'][0]))/2,
                        0, 0, 0, 1))
stagemap.add_cad_model('objectives', r'C:\Users\micah.woodard\Downloads\dispim_files\di-spim-tissue-map.STL',
                       (1, 0, 0, 'x',
                        0, 1, 0, stagemap.limits_um['y'][1],
                        0, 0, 1, 'z',
                        0, 0, 0, 1))
x = randomwalk1D(stagemap.stage_position_um['x'], 100)
y = randomwalk1D(stagemap.stage_position_um['y'], 100)
z = randomwalk1D(stagemap.stage_position_um['z'], 100)
t1 = threading.Thread(target=stagewalk, args=(x,y,z))
t1.start()
sys.exit(app.exec_())


