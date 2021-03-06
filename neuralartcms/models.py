from django.db import models
from django.core.files.images import get_image_dimensions
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from uuid import uuid4 as uuid
from io import BytesIO
from accounts.models import User
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill
from imagekit.processors import ResizeToFit
from PIL import Image

import json
import os


class UUIDFileSystemStorage(FileSystemStorage):
    def get_valid_name(self, name):
        '''
        return the new filename using uuid(except hyphen) and original extension.
        '''
        fn, ext = os.path.splitext(name)
        return uuid().hex + (ext or '')


uuidfs = UUIDFileSystemStorage()

def default_parameters():
    parameters = {}

    parameters["content_weight"] = "5e0"
    parameters["style_weight"] = "1e2"
    parameters["max_iter"] = "1000"

    return json.dumps(parameters)


class Material(models.Model):
    """
    画風変換にて入力する情報
    """
    user = models.ForeignKey(User, related_name='materials', on_delete=models.CASCADE)
    material_name = models.CharField(max_length=100)

    # TODO: 幅は縮小する処理をしているが、高さに関する処理がない
    # ResizeToFillやSmartResizeを使えばよいかも。調査の必要あり。
    content_image = models.ImageField(upload_to='images/material/content/', storage=uuidfs)
    content_image_xs = ImageSpecField(source='content_image',
                                             processors=[ResizeToFit(width='150')],
                                             format='JPEG',
                                             options={"quality": 60})
    content_image_sm = ImageSpecField(source='content_image',
                                         processors=[ResizeToFit(width='500', upscale=False)],
                                         format='JPEG',)

    use_content_segmap = models.BooleanField(default=True)
    content_segmap = models.ImageField(upload_to='images/material/content_segmap', blank=True, storage=uuidfs)
    content_segmap_xs = ImageSpecField(source='content_segmap',
                                              processors=[ResizeToFit(width='150')],
                                              format='JPEG',
                                              options={"quality": 60})
    content_segmap_sm = ImageSpecField(source='content_segmap',
                                          processors=[ResizeToFit(width='500', upscale=False)],
                                          format='JPEG',)

    style_image = models.ImageField(upload_to='images/material/style/', storage=uuidfs)
    style_image_xs = ImageSpecField(source='style_image',
                                           processors=[ResizeToFit(width='150')],
                                           format='JPEG',
                                           options={"quality": 60})
    style_image_sm = ImageSpecField(source='style_image',
                                       processors=[ResizeToFit(width='500', upscale=False)],
                                       format='JPEG',)

    style_segmap_setting = models.CharField(max_length=30)
    style_segmap = models.ImageField(upload_to='images/material/style_segmap', blank=True, storage=uuidfs)
    style_segmap_xs = ImageSpecField(source='style_segmap',
                                            processors=[ResizeToFit(width='150')],
                                            format='JPEG',
                                            options={"quality": 60})
    style_segmap_sm = ImageSpecField(source='style_segmap',
                                        processors=[ResizeToFit(width='500', upscale=False)],
                                        format='JPEG',)

    parameters = models.TextField(blank=True, default=default_parameters)  # パラメータ調整値、Jsonで格納すること
    start_at = models.DateTimeField(blank=False)
    great_result = models.CharField(max_length=100)

    def save(self, *args, **kwargs):

        # style_segmapを使わない設定の時に、白い画像を自動で生成する
        if self.style_segmap_setting != "use":

            ss_w, ss_h = get_image_dimensions(self.style_image)

            if self.style_segmap_setting == "white":
                color = (255, 255, 255)
            elif self.style_segmap_setting == "black":
                color = (0, 0, 0)
            elif self.style_segmap_setting == "red":
                color = (255, 0, 0)
            elif self.style_segmap_setting == "green":
                color = (0, 255, 0)
            else:
                color = (0, 0, 255)

            style_segmap_ = Image.new('RGB', (ss_w, ss_h), color)

            style_segmap_io = BytesIO()
            style_segmap_.save(style_segmap_io, format='JPEG')

            tmp_name = "style_segmap.jpg"
            self.style_segmap.save(
                tmp_name,
                content=ContentFile(style_segmap_io.getvalue()),
                save=False
            )

        # content_segmapを使わないときは、content_imageと同一になる
        if self.use_content_segmap is False:
            self.content_segmap = self.content_image

        super(Material, self).save(*args, **kwargs)

    def __repr__(self):
        # 主キーとnameを返して見やすくする
        # ex: 1 : material_01
        return "{}: {}".format(self.pk, self.material_name)

    __str__ = __repr__


class Result(models.Model):
    """
    画風変換による出力画像'1枚'を保持する
    """
    material = models.ForeignKey(Material, related_name='results', on_delete=models.CASCADE)
    result_image = models.ImageField(upload_to='images/result/')
    result_image_xs = ImageSpecField(source='result_image',
                                            processors=[ResizeToFit(width='150')],
                                            format='JPEG',
                                            options={"quality": 60})
    result_image_sm = ImageSpecField(source='result_image',
                                        processors=[ResizeToFit(width='300', upscale=False)],
                                        format='JPEG',)

    iteration = models.IntegerField()
    result_info = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    result_name = models.CharField(blank=True, max_length=70)  # 作品名(is_public=Trueの時は必須となる)
    is_public = models.BooleanField(default=False)  # 共有するかどうか

    def __repr__(self):
        # 主キーとカウント数を返して見やすくする
        # ex: 1 : iteration()
        return "{}: iteration({:5d})".format(self.pk, self.iteration)

    __str__ = __repr__
