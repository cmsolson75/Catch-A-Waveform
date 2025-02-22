import torch

class Params(object):
    def __init__(self):
        ######################
        # Running Parameters #
        ######################
        self.start_time = 0
        self.segments_to_train = []
        self.min_length = 20
        self.max_length = 25
        self.plot_signals = True
        self.manual_random_seed = -1 # -1 for no setting
        self.plot_losses = True
        self.init_sample_rate = 44100
        self.fs_list = [250, 320, 400, 500, 640, 880, 1000, 1280, 1600, 2000, 2500, 3200, 4000, 5000, 8000, 10000, 12000, 14400, 16000, 20000, 25000, 32000, 40000, 44100]
        self.run_mode = 'normal'
        self.speech = False
        self.set_first_scale_by_energy = True
        self.add_cond_noise = True
        self.min_energy_th = 0.0025  # minimum mean energy for first scale
        self.is_cuda = torch.cuda.is_available()
        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        self.initial_noise_amp = 1
        self.noise_amp_factor = 0.01
        self.scale_crop = False
        self.scale_crop_idx = 0
        self.batch_size = 88

        #####################
        # Losses Parameters #
        #####################
        self.lambda_grad = 0.01
        self.alpha1 = 10
        self.alpha2 = 1e-4
        self.multispec_loss_n_fft = (2048, 1024, 512)
        self.multispec_loss_hop_length = (240, 120, 50)
        self.multispec_loss_window_size = (1200, 600, 240)

        ###########################
        # Optimization Parameters #
        ###########################
        self.num_epochs = 2000
        self.learning_rate = 0.0015
        self.learning_rate_d = 0.0019
        self.learning_rate_g = 0.000475
        self.scheduler_lr_decay = 0.1
        self.beta1 = 0.5
        self.lite = False
        self.ttur = False
        self.learn_milestones = False

        ####################
        # Model Parameters #
        ####################
        self.filter_size = 9
        self.num_layers = 8
        self.hidden_channels_init = 16
        self.growing_hidden_channels_factor = 6
        self.skip_connections = False

