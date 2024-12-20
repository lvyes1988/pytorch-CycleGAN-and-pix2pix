import os
import json
import random
import io

from data.base_dataset import BaseDataset, get_params, get_transform, transparent_to_whiteBK
from data.image_folder import make_dataset
from PIL import Image


class AlignedDataset(BaseDataset):
    """A dataset class for paired image dataset.

    It assumes that the directory '/path/to/data/train' contains image pairs in the form of {A,B}.
    During test time, you need to prepare a directory '/path/to/data/test'.
    """

    def __init__(self, opt):
        """Initialize this dataset class.

        Parameters:
            opt (Option class) -- stores all the experiment flags; needs to be a subclass of BaseOptions
        """
        BaseDataset.__init__(self, opt)
        self.dir_AB = os.path.join(opt.dataroot, opt.phase)  # get the image directory
        self.AB_paths = sorted(make_dataset(self.dir_AB, opt.max_dataset_size))  # get image paths
        if opt.repeat_dataset_count > 1:
            temp = self.AB_paths.copy()
            for n in range(opt.repeat_dataset_count-1):
                self.AB_paths.extend(temp)
        assert(self.opt.load_size >= self.opt.crop_size)   # crop_size should be smaller than the size of loaded image
        self.input_nc = self.opt.output_nc if self.opt.direction == 'BtoA' else self.opt.input_nc
        self.output_nc = self.opt.input_nc if self.opt.direction == 'BtoA' else self.opt.output_nc

    def __getitem__(self, index):
        """Return a data point and its metadata information.

        Parameters:
            index - - a random integer for data indexing

        Returns a dictionary that contains A, B, A_paths and B_paths
            A (tensor) - - an image in the input domain
            B (tensor) - - its corresponding image in the target domain
            A_paths (str) - - image paths
            B_paths (str) - - image paths (same as A_paths)
        """
        # read a image given a random integer index
        AB_path = self.AB_paths[index]
        AB = Image.open(io.BytesIO(self.get_cache_path(self, AB_path)))
        # split AB image into A and B
        w, h = AB.size
        w2 = int(w / 2)
        A = AB.crop((0, 0, w2, h))
        B = AB.crop((w2, 0, w, h))
        
        
        if random.random() < self.opt.agument_whiteBK_A:
            A = transparent_to_whiteBK(A)
        A = A.convert('RGB')
        B = B.convert('RGB')


        # apply the same transform to both A and B
        transform_params_A = get_params(self.opt, A.size)
        transform_params_B = json.loads(json.dumps(transform_params_A))
        transform_params_A['grayscale'] = random.random() < self.opt.agument_grayscale_A
        transform_params_B['grayscale'] = random.random() < self.opt.agument_grayscale_B
        transform_params_A['blur'] = random.random() < self.opt.agument_blur_A
        transform_params_B['blur'] = random.random() < self.opt.agument_blur_B
        transform_params_A['distort'] = random.random() < self.opt.agument_distort_A
        transform_params_B['distort'] = random.random() < self.opt.agument_distort_B
        transform_params_B['whiteBK'] = random.random() < self.opt.agument_whiteBK_A

        A_transform = get_transform(self.opt, transform_params_A, grayscale=(self.input_nc == 1))
        B_transform = get_transform(self.opt, transform_params_B, grayscale=(self.output_nc == 1))

        A = A_transform(A)
        B = B_transform(B)

        return {'A': A, 'B': B, 'A_paths': AB_path, 'B_paths': AB_path}

    def __len__(self):
        """Return the total number of images in the dataset."""
        return len(self.AB_paths)

