#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# Author: kerlomz <kerlomz@gmail.com>
import hashlib
import utils
import utils.sparse
import tensorflow as tf
from constants import RunMode, ModelField, DatasetType, LossFunction
from config import ModelConfig, EXCEPT_FORMAT_MAP
from encoder import Encoder


class DataIterator:
    """数据集迭代类"""
    def __init__(self, model_conf: ModelConfig, mode: RunMode):
        """
        :param model_conf: 工程配置
        :param mode: 运行模式（区分：训练/验证）
        """
        self.model_conf = model_conf
        self.mode = mode
        self.path_map = {
            RunMode.Trains: self.model_conf.trains_path[DatasetType.TFRecords],
            RunMode.Validation: self.model_conf.validation_path[DatasetType.TFRecords]
        }
        self.batch_map = {
            RunMode.Trains: self.model_conf.batch_size,
            RunMode.Validation: self.model_conf.validation_batch_size
        }
        self.data_dir = self.path_map[mode]
        self.next_element = None
        self.image_path = []
        self.label_list = []
        self._label_list = []
        self._size = 0
        self.encoder = Encoder(self.model_conf, self.mode)

    @staticmethod
    def parse_example(serial_example):

        features = tf.io.parse_single_example(
            serial_example,
            features={
                'label': tf.io.FixedLenFeature([], tf.string),
                'input': tf.io.FixedLenFeature([], tf.string),
            }
        )
        _input = tf.cast(features['input'], tf.string)
        _label = tf.cast(features['label'], tf.string)

        return _input, _label

    def read_sample_from_tfrecords(self, path):
        """
        从TFRecords中读取样本
        :param path: TFRecords文件路径
        :return:
        """
        if isinstance(path, list):
            for p in path:
                self._size += len([_ for _ in tf.io.tf_record_iterator(p)])
        else:
            self._size = len([_ for _ in tf.io.tf_record_iterator(path)])

        min_after_dequeue = 1000
        batch = self.batch_map[self.mode]

        dataset_train = tf.data.TFRecordDataset(
            filenames=path,
            num_parallel_reads=20
        ).map(self.parse_example)
        dataset_train = dataset_train.shuffle(
            min_after_dequeue
        ).batch(batch, drop_remainder=True).repeat()
        iterator = tf.compat.v1.data.make_one_shot_iterator(dataset_train)
        self.next_element = iterator.get_next()

    @property
    def size(self):
        """样本数"""
        return self._size

    @property
    def labels(self):
        """标签"""
        return self.label_list

    @staticmethod
    def to_sparse(input_batch, label_batch):
        """密集输入转稀疏"""
        batch_inputs = input_batch
        batch_labels = utils.sparse.sparse_tuple_from_sequences(label_batch)
        return batch_inputs, batch_labels

    def generate_batch_by_tfrecords(self, sess):
        """根据TFRecords生成当前批次，输入为当前TensorFlow会话，输出为稀疏型X和Y"""
        _input, _label = sess.run(self.next_element)
        input_batch = []
        label_batch = []
        for index, (i1, i2) in enumerate(zip(_input, _label)):
            try:
                if self.model_conf.model_field == ModelField.Image:
                    input_array = self.encoder.image(i1)
                else:
                    input_array = self.encoder.text(i1)
                label_array = self.encoder.text(i2, extracted=True)
                label_len_correct = len(label_array) != self.model_conf.max_label_num
                using_cross_entropy = self.model_conf.loss_func == LossFunction.CrossEntropy
                if label_len_correct and using_cross_entropy:
                    tf.logging.warn("The number of labels must be fixed when using cross entropy, label: {}, "
                                    "the number of tags is incorrect, ignored.".format(i2))
                    continue

                input_batch.append(input_array)
                label_batch.append(label_array)
            except OSError:
                random_suffix = hashlib.md5(i1).hexdigest()
                file_format = EXCEPT_FORMAT_MAP[self.model_conf.model_field]
                with open(file="oserror_{}.{}".format(random_suffix, file_format), mode="wb") as f:
                    f.write(i1)
                continue

        # 如果图片尺寸不固定则padding当前批次，使用最大的宽度作为序列最大长度
        if self.model_conf.model_field == ModelField.Image and self.model_conf.resize[0] == -1:
            input_batch = tf.keras.preprocessing.sequence.pad_sequences(
                sequences=input_batch,
                maxlen=None,
                dtype='float32',
                padding='post',
                truncating='post',
                value=0
            )

        self.label_list = label_batch

        return self.to_sparse(input_batch, self.label_list)
