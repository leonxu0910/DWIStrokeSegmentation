from keras.models import Model
from keras.layers import *
from keras.applications.vgg16 import *
import keras.backend as K
import tensorflow as tf
from keras.utils.data_utils import get_file
from keras.losses import binary_crossentropy
from keras.optimizers import Adam
import os
#
def mean_iou(label, prediction):
    prediction_ = tf.to_int32(prediction > 0.5)
    score, conf_matrix = tf.metrics.mean_iou(label, prediction_, 2)
    K.get_session().run(tf.local_variables_initializer())
    with tf.control_dependencies([conf_matrix]):
        score = tf.identity(score)
    return score

def get_weights_path_vgg16():
    TF_WEIGHTS_PATH = 'https://github.com/fchollet/deep-learning-models/releases/download/v0.1/vgg16_weights_tf_dim_ordering_tf_kernels.h5'
    weights_path = get_file('vgg16_weights_tf_dim_ordering_tf_kernels.h5',TF_WEIGHTS_PATH,cache_subdir='models')
    #weights_path = '../ckpt/vgg16_weights_tf_dim_ordering_tf_kernels_notop.h5'
    return weights_path

def transfer_FCN_Vgg16():
    input_shape = (256, 256, 1)
    img_input = Input(shape=input_shape)
    # Block 1
    conv1_1 = Conv2D(64, (3, 3), activation='relu', padding='same', name='conv1_1')(img_input)
    conv1_2 = Conv2D(64, (3, 3), activation='relu', padding='same', name='conv1_2')(conv1_1)
    pool1 = MaxPooling2D((2, 2), strides=(2, 2), padding='same', name='pool1')(conv1_2)

    # Block 2
    conv2_1 = Conv2D(128, (3, 3), activation='relu', padding='same', name='conv2_1')(pool1)
    conv2_2 = Conv2D(128, (3, 3), activation='relu', padding='same', name='conv2_2')(conv2_1)
    pool2 = MaxPooling2D((2, 2), strides=(2, 2), padding='same', name='pool2')(conv2_2)

    # Block 3
    conv3_1 = Conv2D(256, (3, 3), activation='relu', padding='same', name='conv3_1')(pool2)
    conv3_2 = Conv2D(256, (3, 3), activation='relu', padding='same', name='conv3_2')(conv3_1)
    conv3_3 = Conv2D(256, (3, 3), activation='relu', padding='same', name='conv3_3')(conv3_2)
    pool3 = MaxPooling2D((2, 2), strides=(2, 2), padding='same', name='pool3')(conv3_3)

    # Block 4
    conv4_1 = Conv2D(512, (3, 3), activation='relu', padding='same', name='conv4_1')(pool3)
    conv4_2 = Conv2D(512, (3, 3), activation='relu', padding='same', name='conv4_2')(conv4_1)
    conv4_3 = Conv2D(512, (3, 3), activation='relu', padding='same', name='conv4_3')(conv4_2)
    pool4 = MaxPooling2D((2, 2), strides=(2, 2), padding='same', name='pool4')(conv4_3)

    # Block 5
    conv5_1 = Conv2D(512, (3, 3), activation='relu', padding='same', name='block5_conv1')(pool4)
    conv5_2 = Conv2D(512, (3, 3), activation='relu', padding='same', name='block5_conv2')(conv5_1)
    conv5_3 = Conv2D(512, (3, 3), activation='relu', padding='same', name='block5_conv3')(conv5_2)
    pool5 = MaxPooling2D((2, 2), strides=(2, 2), padding='same', name='block5_pool')(conv5_3)

    # Convolutional layers transfered from fully-connected layers
    o = Conv2D(4096, (7, 7), activation='relu', padding='same', name='conv6', data_format="channels_last")(pool5)
    conv7 = Conv2D(4096, (1, 1), activation='relu', padding='same', name='conv7', data_format="channels_last")(o)
    # conv_out = Conv2D(2, (1, 1), activation='linear', name='predictions_1000')(fc2)

    ## 4 times upsamping for pool4 layer
    conv7_4 = Conv2DTranspose(1, kernel_size=(4, 4), strides=(4, 4), use_bias=False, data_format="channels_last")(conv7)

    ## 2 times upsampling for pool411
    pool4up = Conv2D(1, (1, 1), activation='relu', padding='same', name="pool4up", data_format="channels_last")(pool4)
    pool4up2 = Conv2DTranspose(2, kernel_size=(2, 2), strides=(2, 2), use_bias=False, data_format="channels_last")(pool4up)
    pool3up = Conv2D(1, (1, 1), activation='relu', padding='same', name="pool3up", data_format="channels_last")(pool3)

    # vgg = Model(img_input, pool5)
    # vgg.load_weights(get_weights_path_vgg16())  ## loading VGG weights for the encoder parts of FCN8

    o = Add(name="add")([pool4up2, pool3up, conv7_4])
    o = Conv2DTranspose(1, kernel_size=(8, 8), strides=(8, 8), use_bias=False, data_format="channels_last")(o)
    o = (Activation('sigmoid'))(o)

    model = Model(img_input, o)

    #Create model
    #model = Model(img_input,conv_out)
    weights_path = get_weights_path_vgg16()
    
    # transfer if weights have not been created
    if os.path.isfile(weights_path) == False:
        print("in if statement")
        flattened_layers = model.layers
        index = {}
        for layer in flattened_layers:
            if layer.name:
                index[layer.name]=layer
        vgg16 = VGG16()
        for layer in vgg16.layers:
            weights = layer.get_weights()
            if layer.name == 'fc1':
                weights[0] = np.reshape(weights[0], (7,7,512,4096))
            elif layer.name == 'fc2':
                weights[0] = np.reshape(weights[0], (1,1,4096,4096))
            elif layer.name == 'predictions':
                layer.name = 'predictions_1000'
                weights[0] = np.reshape(weights[0], (1,1,4096,1000))
            if layer.name in index:
                index[layer.name].set_weights(weights)
        model.save_weights(weights_path)
        print( 'Successfully transformed!')
        #else load weights
    else:
        model.load_weights(weights_path, by_name=True)
        print( 'Already transformed!')
    model.compile(loss=binary_crossentropy, optimizer=Adam(lr=0.0002), metrics=[mean_iou])
    return model