"""This module implements an abstract base class (ABC) 'BaseDataset' for datasets.

It also includes common transformation functions (e.g., get_transform, __scale_width), which can be later used in subclasses.
"""
import random
import numpy as np
import torch.utils.data as data
from PIL import Image, ImageEnhance, ImageFilter
import torchvision.transforms as transforms
from abc import ABC, abstractmethod


class BaseDataset(data.Dataset, ABC):
    """This class is an abstract base class (ABC) for datasets.

    To create a subclass, you need to implement the following four functions:
    -- <__init__>:                      initialize the class, first call BaseDataset.__init__(self, opt).
    -- <__len__>:                       return the size of dataset.
    -- <__getitem__>:                   get a data point.
    -- <modify_commandline_options>:    (optionally) add dataset-specific options and set default options.
    """

    def __init__(self, opt):
        """Initialize the class; save the options in the class

        Parameters:
            opt (Option class)-- stores all the experiment flags; needs to be a subclass of BaseOptions
        """
        self.opt = opt
        self.root = opt.dataroot
        self.cache = {}

    @staticmethod
    def get_cache_path(self, path):
        if path in self.cache:
            return self.cache[path]
        with open(path, 'rb') as f:
            bts = f.read()
        if self.opt.cache_num > len(self.cache):
            self.cache[path] = bts
        return bts

    @staticmethod
    def modify_commandline_options(parser, is_train):
        """Add new dataset-specific options, and rewrite default values for existing options.

        Parameters:
            parser          -- original option parser
            is_train (bool) -- whether training phase or test phase. You can use this flag to add training-specific or test-specific options.

        Returns:
            the modified parser.
        """
        return parser

    @abstractmethod
    def __len__(self):
        """Return the total number of images in the dataset."""
        return 0

    @abstractmethod
    def __getitem__(self, index):
        """Return a data point and its metadata information.

        Parameters:
            index - - a random integer for data indexing

        Returns:
            a dictionary of data with their names. It ususally contains the data itself and its metadata information.
        """
        pass


def get_params(opt, size):
    w, h = size
    new_h = h
    new_w = w
    if opt.preprocess == 'resize_and_crop':
        new_h = new_w = opt.load_size
    elif opt.preprocess == 'scale_width_and_crop':
        new_w = opt.load_size
        new_h = opt.load_size * h // w
    elif opt.preprocess == 'scale_short_and_crop':
        min_side = min(h,w)
        ratio = opt.load_size/min_side
        new_w = round(w*ratio)
        new_h = round(h*ratio)

    x = random.randint(0, np.maximum(0, new_w - opt.crop_size))
    y = random.randint(0, np.maximum(0, new_h - opt.crop_size))

    flip = random.random() > 0.5
    flip_x = random.random() > 0.5
    
    rotate = random.randint(-opt.rotate, opt.rotate)

    return {'crop_pos': (x, y), 'flip': flip, 'flip_x': flip_x, 'rotate':rotate}


def get_transform(opt, params=None, grayscale=False, method=transforms.InterpolationMode.BICUBIC, convert=True):
    transform_list = []
    if grayscale:
        transform_list.append(transforms.Grayscale(1))
    if params is not None:
        if params['rotate']:
            transform_list.append(transforms.Lambda(lambda img: __rotate(img, params['rotate'])))
    if 'resize' in opt.preprocess:
        osize = [opt.load_size, opt.load_size]
        transform_list.append(transforms.Resize(osize, method))
    elif 'scale_width' in opt.preprocess:
        transform_list.append(transforms.Lambda(lambda img: __scale_width(img, opt.load_size, opt.crop_size, method)))
    elif 'scale_short' in opt.preprocess:
        transform_list.append(transforms.Lambda(lambda img: __scale_short(img, opt.load_size, method)))

    if 'crop' in opt.preprocess:
        if params is None:
            transform_list.append(transforms.RandomCrop(opt.crop_size))
        else:
            transform_list.append(transforms.Lambda(lambda img: __crop(img, params['crop_pos'], opt.crop_size)))

    if opt.preprocess == 'none':
        transform_list.append(transforms.Lambda(lambda img: __make_power_2(img, base=4, method=method)))

    if not opt.no_flip:
        if params is None:
            transform_list.append(transforms.RandomHorizontalFlip())
        else:
          if params['flip']:
            transform_list.append(transforms.Lambda(lambda img: __flip(img, params['flip'])))
          if opt.flip_x and params['flip_x']:
            transform_list.append(transforms.Lambda(lambda img: __flip_x(img, params['flip_x'])))
    if params is not None and params.get('blur', 0.0):
        if random.random() < params.get('blur', 0.0):
            blur_fn = ["gaussian_blur", "median_blur"]
            random.shuffle(blur_fn)
            fn = blur_fn[0]
            if fn == "gaussian_blur":
                transform_list.append(transforms.Lambda(lambda img: gaussian_blur(img)))
            else:
                transform_list.append(transforms.Lambda(lambda img: median_blur(img)))
    if params is not None and params.get('distort', 0.0):
        fs = dict()
        fs["brightness"]={"f":brightness, "range":0.1}
        fs["contrast"]={"f":contrast, "range":0.1}
        fs["saturation"]={"f":saturation, "range":0.1}
        fs["hue"]={"f":hue, "range":0.1}
        fs["sharpness"]={"f":sharpness, "range":0.1}
        for k in fs:
            if random.random() < params.get('distort', 0.0):
                v = fs[k]
                range = v['range']
                fn = v['f']
                if fn == 'brightness':
                    transform_list.append(transforms.Lambda(lambda img:  brightness(img, 1-range, 1+range)))
                elif fn == 'contrast':
                    transform_list.append(transforms.Lambda(lambda img:  contrast(img, 1-range, 1+range)))
                elif fn == 'saturation':
                    transform_list.append(transforms.Lambda(lambda img:  saturation(img, 1-range, 1+range)))
                elif fn == 'hue':
                    transform_list.append(transforms.Lambda(lambda img:  hue(img, 1-range, 1+range)))
                elif fn == 'sharpness':
                    transform_list.append(transforms.Lambda(lambda img:  sharpness(img, 1-range, 1+range)))
    if (not grayscale) and (params is not None) and params.get('grayscale',False):
        transform_list.append(transforms.Grayscale(3))
    if convert:
        transform_list += [transforms.ToTensor()]
        if grayscale:
            transform_list += [transforms.Normalize((0.5,), (0.5,))]
        else:
            transform_list += [transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))]
    return transforms.Compose(transform_list)


def __transforms2pil_resize(method):
    mapper = {transforms.InterpolationMode.BILINEAR: Image.BILINEAR,
              transforms.InterpolationMode.BICUBIC: Image.BICUBIC,
              transforms.InterpolationMode.NEAREST: Image.NEAREST,
              transforms.InterpolationMode.LANCZOS: Image.LANCZOS,}
    return mapper[method]


def __make_power_2(img, base, method=transforms.InterpolationMode.BICUBIC):
    method = __transforms2pil_resize(method)
    ow, oh = img.size
    h = int(round(oh / base) * base)
    w = int(round(ow / base) * base)
    if h == oh and w == ow:
        return img

    __print_size_warning(ow, oh, w, h)
    return img.resize((w, h), method)


def __scale_width(img, target_size, crop_size, method=transforms.InterpolationMode.BICUBIC):
    method = __transforms2pil_resize(method)
    ow, oh = img.size
    if ow == target_size and oh >= crop_size:
        return img
    w = target_size
    h = int(max(target_size * oh / ow, crop_size))
    return img.resize((w, h), method)

def __scale_short(img, target_size, method=transforms.InterpolationMode.BICUBIC):
    method = __transforms2pil_resize(method)
    ow, oh = img.size
    min_side = min(ow,oh)
    if min_side == target_size:
        return img
    ratio = target_size/min_side
    new_w = round(ow*ratio)
    new_h = round(oh*ratio)
    return img.resize((new_w, new_h), method)

def __crop(img, pos, size):
    ow, oh = img.size
    x1, y1 = pos
    tw = th = size
    if (ow > tw or oh > th):
        return img.crop((x1, y1, x1 + tw, y1 + th))
    return img

def __rotate(img, rotate):
    if rotate:
        return img.rotate(rotate, fillcolor='white')
    return img

def __flip(img, flip):
    if flip:
        return img.transpose(Image.FLIP_LEFT_RIGHT)
    return img

def __flip_x(img, flip):
    if flip:
        return img.transpose(Image.FLIP_TOP_BOTTOM)
    return img

def __print_size_warning(ow, oh, w, h):
    """Print warning information about image size(only print once)"""
    if not hasattr(__print_size_warning, 'has_printed'):
        print("The image size needs to be a multiple of 4. "
              "The loaded image size was (%d, %d), so it was adjusted to "
              "(%d, %d). This adjustment will be done to all images "
              "whose sizes are not multiples of 4" % (ow, oh, w, h))
        __print_size_warning.has_printed = True

def gaussian_blur(im, radius=2):
    im = im.filter(ImageFilter.GaussianBlur(radius = radius))
    return im

def median_blur(im, size=3):
    im = im.filter(ImageFilter.MedianFilter(size))
    return im

def brightness(im, brightness_lower, brightness_upper):
    brightness_delta = np.random.uniform(brightness_lower, brightness_upper)
    im = ImageEnhance.Brightness(im).enhance(brightness_delta)
    return im

def contrast(im, contrast_lower, contrast_upper):
    contrast_delta = np.random.uniform(contrast_lower, contrast_upper)
    im = ImageEnhance.Contrast(im).enhance(contrast_delta)
    return im

def saturation(im, saturation_lower, saturation_upper):
    saturation_delta = np.random.uniform(saturation_lower, saturation_upper)
    im = ImageEnhance.Color(im).enhance(saturation_delta)
    return im

def hue(im, hue_lower, hue_upper):
    hue_delta = np.random.uniform(hue_lower, hue_upper)
    im = np.array(im.convert('HSV'))
    im[:, :, 0] = im[:, :, 0] + hue_delta
    im = Image.fromarray(im, mode='HSV').convert('RGB')
    return im

def sharpness(im, sharpness_lower, sharpness_upper):
    sharpness_delta = np.random.uniform(sharpness_lower, sharpness_upper)
    im = ImageEnhance.Sharpness(im).enhance(sharpness_delta)
    return im


def transparent_to_whiteBK(image:Image.Image):
    if image.mode == 'P':
        if image.palette.mode[-1] == 'A':
            image = image.convert(image.palette.mode)

    if image.mode[-1] == 'A':
        new_mode = image.mode[:-1]
        color = [255]*len(new_mode)
        new_image = Image.new(new_mode, image.size, color=tuple(color))
        new_image.paste(image, None, image)
        return new_image
    else:
        return image
