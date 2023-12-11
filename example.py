from stagemap_widget.stagemap import StageMap
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
                 tile_overlap_pct,
                    r'C:\Users\micah.woodard\Downloads\dispim_files\di-spim-holder.STL',
                    r'C:\Users\micah.woodard\Downloads\dispim_files\di-spim-tissue-map.STL')
# stagemap = StageMap(coordinate_transformation_map)
# print('1', stagemap.coordinate_transformation_map)
# #stagemap.coordinate_transformation_map = {'x': 'z', 'y': 'x', 'z': 'y'}
# print('2', stagemap.stage_position_um)
# stagemap.stage_position_um['x'] = 80
# print('3', stagemap.stage_position_um['x'])
# print('4', stagemap.stage_position_um)
# stagemap.coordinate_transformation_map = {'x': 'z', 'y': 'x', 'z': '-y'}
# print('outside', stagemap.scanning_volume_um)
# print('outside', stagemap.limits_um)
# print('outside', stagemap.fov_um)
# print('outside', stagemap.tile_overlap_pct)
# print(stagemap.stage_position_um)
# print(stagemap.coordinate_transformation_map, stagemap.stage_position_um, stagemap.fov_um,
#       stagemap.scanning_volume_um, stagemap.limits_um, stagemap.fov_um, stagemap.tile_overlap_pct)
x = randomwalk1D(stagemap.stage_position_um['x'], 100)
y = randomwalk1D(stagemap.stage_position_um['y'], 100)
z = randomwalk1D(stagemap.stage_position_um['z'], 100)
t1 = threading.Thread(target=stagewalk, args=(x,y,z))
t1.start()
sys.exit(app.exec_())


