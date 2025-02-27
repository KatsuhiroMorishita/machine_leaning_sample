# purpose: kerasによる画像識別の学習のサンプル
# author: Katsuhiro MORISHITA　森下功啓
# created: 2018-08-15
import keras
from keras.models import Sequential, load_model, Model
from keras.layers import Dense, Dropout, Activation, Flatten
from keras.layers import Conv2D, MaxPooling2D
from keras.optimizers import SGD
from keras.preprocessing.image import ImageDataGenerator
from keras.applications.vgg16 import VGG16
from keras.applications.xception import Xception
from keras.backend import tensorflow_backend
import tensorflow as tf
from PIL import Image
import numpy as np
import sys
import os

from mlcore import *


# 学習上の条件
np.random.seed(seed=1)

# GPUの設定
config = tf.ConfigProto(gpu_options=tf.GPUOptions(allow_growth=True))
session = tf.Session(config=config)
tensorflow_backend.set_session(session)




def preprocessing(imgs):
    """ 画像の前処理
    必要なら呼び出して下さい。
    
    imgs: ndarray, 画像が複数入っている多次元配列
    """
    return imgs / 255


def build_model_simple(input_shape, output_dim, data_format):
    """ 機械学習のモデルを作成する
    入力は画像、出力はラベルという構造を想定しています。
    """
    # モデルの作成
    model = Sequential()
    model.add(Conv2D(32, (3, 3), padding="same", data_format=data_format, input_shape=input_shape))  # カーネル数32, カーネルサイズ(3,3), input_shapeは1層目なので必要。https://keras.io/ja/layers/convolutional/#conv2d
    model.add(Activation('relu'))
    model.add(Conv2D(24, (3, 3)))
    model.add(Activation('relu'))
    model.add(MaxPooling2D(pool_size=(2, 2)))
    model.add(Dropout(0.25))
    model.add(Conv2D(64, (3, 3), padding='same'))
    model.add(Activation('relu'))
    model.add(Conv2D(64, (3, 3)))
    model.add(Activation('relu'))
    model.add(MaxPooling2D(pool_size=(2, 2)))
    model.add(Dropout(0.25))
    model.add(Flatten())
    model.add(Dense(200))
    model.add(Activation('relu'))
    model.add(Dropout(0.5))
    model.add(Dense(output_dim))                      # 出力層のユニット数は2
    model.add(Activation('sigmoid'))
    model.add(Activation('softmax'))
    opt = keras.optimizers.Adam(lr=0.0005, beta_1=0.9, beta_2=0.999, epsilon=1e-08, decay=0.0003) # 最適化器のセット。lrは学習係数
    model.compile(optimizer=opt,             # コンパイル
          loss='categorical_crossentropy',   # 損失関数は、判別問題なのでcategorical_crossentropyを使う
          metrics=['accuracy'])
    print(model.summary())

    return model



def main():
	# 調整することの多いパラメータを集めた
    image_shape = (32, 32)
    epochs = 50              # 1つのデータ当たりの学習回数
    batch_size = 10          # 学習係数を更新するために使う教師データ数
    initial_epoch = 0       # 再開時のエポック数。途中から学習を再開する場合は、0以外を指定しないとhistryのグラフの横軸が0空になる
    if epochs <= initial_epoch:  # 矛盾があればエラー
        raise ValueError("epochs <= initial_epoch")

    # 教師データを無限に用意するオブジェクトを作成
    datagen = ip.MyImageDataGenerator(       # 自作のImageDataGenerator
        rotation_range = 45,                    # 回転角度[degree]
        horizontal_flip=True,                   # 水平方向への反転
        vertical_flip=True,                     # 垂直方向での反転
        #crop=True,
        #random_erasing=True,
        mixup = 0.5,                            # 画像の混合確率
        shape=image_shape)                      # 出力する画像のサイズ

    
    # 教師データの読み込みと、モデルの構築。必要なら、callbackで保存していた結合係数を読み込む
    load_flag = False
    if len(sys.argv) > 1 and sys.argv[1] == "retry":
        x_train, y_train, y_train_o, x_test, y_test, y_test_o, weights_dict, label_dict, model = reload()
    else:
        data_format = "channels_last"
        
        # pattern 1, flower
        dir_names_dict = {"yellow":["sample_image_flower/1_train"], 
                          "white":["sample_image_flower/2_train"]} 
        param = {"dir_names_dict":dir_names_dict, "data_format":data_format, "size":image_shape, "mode":"RGB", "resize_filter":Image.NEAREST, "preprocess_func":ip.preprocessing2}
        x_train, y_train_o, x_test, y_test_o, weights_dict, label_dict, y_train, y_test, output_dim = ip.load_save_images(ip.read_images1, param, validation_rate=0.2)
        model = build_model_simple(input_shape=x_train.shape[1:], output_dim=output_dim, data_format=data_format)   # モデルの作成

    # 諸々を確認のために表示
    print(x_train.shape, y_train.shape)
    print(x_test.shape, y_test.shape)
    print(weights_dict)
    print(label_dict)
    print(y_train, y_test_o)
    print("layer size", len(model.layers))

    # モデルの調整（最適化器や、学習係数や、結合係数の調整など）
    #for i, layer in enumerate(model.layers):  # 結合係数を更新させるか、させないか調整
    #    if i > 5:
    #        layer.trainable = True     # Trueで更新して、Falseで更新しない
    #    else:
    #        layer.trainable = False

    # re-compile
    #model.compile(optimizer=SGD(lr=0.0001, momentum=0.9),    # コンパイル
    #        loss='categorical_crossentropy',   # 損失関数は、判別問題なのでcategorical_crossentropyを使う
    #        metrics=['accuracy'])

    # 学習
    cb_stop = keras.callbacks.EarlyStopping(monitor='val_loss', patience=5, mode='auto')  # 学習を適当なタイミングで止める仕掛け
    cb_save = keras.callbacks.ModelCheckpoint("cb_model.hdf5", monitor='val_loss', verbose=0, save_best_only=True, save_weights_only=False, mode='auto', period=5)  # 学習中に最高の成績が出るたびに保存

    history = model.fit_generator(   # ImageDataGeneratorを使った学習
        datagen.flow(x_train, y_train, batch_size=batch_size, shuffle=True),  # シャッフルは順序によらない学習のために重要
        epochs=epochs,
        steps_per_epoch=int(x_train.shape[0] / batch_size),
        verbose=1,
        class_weight=weights_dict,
        callbacks=[cb_stop, cb_save],
        validation_data=(x_test, y_test),  # ここにジェネレータを渡すことも出来る
        initial_epoch=initial_epoch
        ) # 返り値には、学習中のlossやaccなどが格納される（metricsに指定する必要がある）

    # 学習成果のチェックとして、検証データに対して分割表を作成する
    check_validation(0.4, model, x_test, y_test_o, label_dict)

    # 学習結果を保存
    print(model.summary())      # レイヤー情報を表示(上で表示させると流れるので)
    model.save('model.hdf5')    # 獲得した結合係数を保存
    plot_history(history)       # lossの変化をグラフで表示


if __name__ == "__main__":
    main()


