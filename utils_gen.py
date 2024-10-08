import os
import cv2
import h5py
import scipy
import numpy as np
from keras.preprocessing.image import ImageDataGenerator
from utils_imgproc import smallize_density_map, fix_singular_shape


def gen_paths_img_dm(path_file_root='data/paths_train_val_test', dataset='A'):
    path_file_root_curr = os.path.join(path_file_root, 'paths_'+dataset)
    img_paths = []
    dm_paths = []
    paths = os.listdir(path_file_root_curr)[:2]
    for i in sorted([os.path.join(path_file_root_curr, p) for p in paths]):
        with open(i, 'r') as fin:
            img_paths.append(
                sorted(
                    [l.rstrip() for l in fin.readlines()],
                    key=lambda x: int(x.split('_')[-1].split('.')[0]))
            )
        with open(i, 'r') as fin:
            dm_paths.append(
                sorted(
                    [l.rstrip().replace('images', 'ground_truth').replace('.jpg', '.h5') for l in fin.readlines()],
                    key=lambda x: int(x.split('_')[-1].split('.')[0]))
            )
    return img_paths, dm_paths


def gen_var_from_paths(paths, stride=1, unit_len=16):
    vars = []
    format_suffix = paths[0].split('.')[-1]
    if format_suffix == 'h5':
        for ph in paths:
            #dm = h5py.File(ph, 'r')['density'].value.astype(np.float32)
            dm = np.asarray(h5py.File(ph, 'r')['density'])
            if unit_len:
                dm = fix_singular_shape(dm, unit_len=unit_len)
            dm = smallize_density_map(dm, stride=stride)
            vars.append(np.expand_dims(dm, axis=-1))
    elif format_suffix == 'jpg':
        for ph in paths:
            raw = cv2.cvtColor(cv2.imread(ph), cv2.COLOR_BGR2RGB).astype(np.float32)
            if unit_len:
                raw = fix_singular_shape(raw, unit_len=unit_len)
            vars.append(raw)
        # vars = norm_by_imagenet(vars)
    else:
        print('Format suffix is wrong.')
    return np.array(vars,dtype=object) ##############modiicado
    #return np.array(vars)


def gen_density_map_gaussian(im, points, sigma=4):
    """
    func: generate the density map
    """
    density_map = np.zeros(im.shape[:2], dtype=np.float32)
    h, w = density_map.shape[:2]
    num_gt = np.squeeze(points).shape[0]
    if num_gt == 0:
        return density_map
    if sigma == 4:
        # Adaptive sigma in CSRNet.
        leafsize = 2048
        tree = scipy.spatial.KDTree(points.copy(), leafsize=leafsize)
        distances, _ = tree.query(points, k=4)
    for idx_p, p in enumerate(points):
        p = np.round(p).astype(int)
        p[0], p[1] = min(h-1, p[1]), min(w-1, p[0])
        gaussian_radius = sigma * 2 - 1
        if sigma == 4:
            # Adaptive sigma in CSRNet.
            sigma = max(int(np.sum(distances[idx_p][1:4]) * 0.1), 1)
            gaussian_radius = sigma * 3
        gaussian_map = np.multiply(
            cv2.getGaussianKernel(int(gaussian_radius*2+1), sigma),
            cv2.getGaussianKernel(int(gaussian_radius*2+1), sigma).T
        )
        x_left, x_right, y_up, y_down = 0, gaussian_map.shape[1], 0, gaussian_map.shape[0]
        # cut the gaussian kernel
        if p[1] < gaussian_radius:
            x_left = gaussian_radius - p[1]
        if p[0] < gaussian_radius:
            y_up = gaussian_radius - p[0]
        if p[1] + gaussian_radius >= w:
            x_right = gaussian_map.shape[1] - (gaussian_radius + p[1] - w) - 1
        if p[0] + gaussian_radius >= h:
            y_down = gaussian_map.shape[0] - (gaussian_radius + p[0] - h) - 1
        gaussian_map = gaussian_map[y_up:y_down, x_left:x_right]
        if np.sum(gaussian_map):
            gaussian_map = gaussian_map / np.sum(gaussian_map)
        density_map[
            max(0, p[0]-gaussian_radius):min(h, p[0]+gaussian_radius+1),
            max(0, p[1]-gaussian_radius):min(w, p[1]+gaussian_radius+1)
        ] += gaussian_map
    density_map = density_map / (np.sum(density_map / num_gt))
    return density_map
