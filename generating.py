from time import sleep 
from utils.utils import *
from utils.plotters import *
import os
import librosa


class AudioGenerator(object):
    def __init__(self, params, generators_list=None, noise_amp_list=None, reconstruction_noise_list=None):
        super(AudioGenerator, self).__init__()
        if type(params) is str:
            path = os.path.join(params, 'log.txt')
            output_folder = params
            params = params_from_log(path)
            params.output_folder = output_folder
            noise_amp_list = noise_amp_list_from_log(path)
            reconstruction_noise_list = torch.load((os.path.join(params.output_folder, 'reconstruction_noise_list.pt')),
                                                   map_location=params.device)
            generators_list = generators_list_from_folder(params)
        else:
            output_folder = params.output_folder
        if params.run_mode == 'transfer':
            print(f' reconstruction noise list has {len(reconstruction_noise_list)} items')
            print(f' noise amp list has {len(noise_amp_list)} items')
        self.generators_list = generators_list
        self.noise_amp_list = noise_amp_list
        self.params = params
        self.reconstruction_noise_list = reconstruction_noise_list
        self.output_folder = output_folder
        if not os.path.exists(os.path.join(output_folder, 'GeneratedSignals')):
            os.mkdir(os.path.join(output_folder, 'GeneratedSignals'))

    def generate(self, nSignals=1, length=20, generate_all_scales=False):
        for sig_idx in range(nSignals):
            # Draws a signal up to current scale, using learned generators
            output_signals_list = draw_signal(self.params, self.generators_list,
                                              [round(f * length) for f in self.params.fs_list], self.params.fs_list,
                                              self.noise_amp_list, output_all_scales=generate_all_scales)
            # Write signals
            if generate_all_scales:
                for scale_idx, sig in enumerate(output_signals_list):
                    write_signal(
                        os.path.join(self.output_folder, 'GeneratedSignals',
                                     'generated@%dHz.wav' % self.params.fs_list[scale_idx]),
                        sig, self.params.fs_list[scale_idx], overwrite=False)
            else:
                write_signal(
                    os.path.join(self.output_folder, 'GeneratedSignals',
                                 'generated@%dHz.wav' % self.params.fs_list[-1]),
                    output_signals_list, self.params.fs_list[-1], overwrite=False)

    def generate_multi(self, nSignals:int=1, length:int=20, generate_all_scales:bool=False, channels:int=1):
        for sig_idx in range(nSignals):
            # Draws a signal up to current scale, using learned generators
            output_signals_list = draw_signal(self.params, self.generators_list,
                                              [round(f * length) for f in self.params.fs_list], self.params.fs_list,
                                              self.noise_amp_list, output_all_scales=generate_all_scales, channels=channels)
            # Write signals
            if generate_all_scales:
                for scale_idx, sig in enumerate(output_signals_list):
                    print(sig.shape)
                    for n, channel in enumerate(sig):
                        write_signal(
                            os.path.join(self.output_folder, 'GeneratedSignals',
                                        f'generated@{self.params.fs_list[scale_idx]}Hz{n}.wav'),
                            channel, self.params.fs_list[scale_idx], overwrite=False)
            else:
                for n, channel in enumerate(output_signals_list):
                    write_signal(
                        os.path.join(self.output_folder, 'GeneratedSignals',
                                    f'generated@{self.params.fs_list[-1]}Hz{n}.wav'),
                        channel, self.params.fs_list[-1], overwrite=False)

    def reconstruct(self, reconstruction_noise_list=None, write=True):
        if reconstruction_noise_list is None:
            reconstruction_noise_list = self.reconstruction_noise_list
        reconstructed_signal = draw_signal(self.params, self.generators_list,
                                           [int(l) for l in self.params.inputs_lengths],
                                           self.params.fs_list, self.noise_amp_list,
                                           reconstruction_noise_list=reconstruction_noise_list)
        if write:
            write_signal(
                os.path.join(self.output_folder, 'GeneratedSignals',
                             'reconstructed@%dHz.wav' % self.params.fs_list[-1]),
                reconstructed_signal, self.params.fs_list[-1], overwrite=False)
        else:
            return reconstructed_signal

    def inpaint(self, new_noise=False):
        reconstruction_noise_list = self.reconstruction_noise_list
        if new_noise:
            pad_size = calc_pad_size(self.params)
            reconstruction_noise_list_new = []
            for idx, (r, fs, noise_amp) in enumerate(
                    zip(reconstruction_noise_list, self.params.fs_list, self.noise_amp_list)):
                new_r = r.clone()
                for hole in self.params.inpainting_indices:
                    start_idx = int(hole[0] + pad_size)
                    end_idx = int(hole[1] + pad_size)
                    new_noise = get_noise(self.params, end_idx - start_idx).expand(1, 1, -1).to(r.device)
                    new_noise = new_noise * noise_amp
                    new_r[:, :, start_idx:end_idx] = new_noise
                reconstruction_noise_list_new.append(new_r)
            reconstruction_noise_list = reconstruction_noise_list_new
        reconstructed_signal = self.reconstruct(reconstruction_noise_list, write=False)
        real_signal, _ = librosa.load(
            os.path.join(self.params.output_folder, 'real@%dHz.wav' % self.params.Fs),
            sr=self.params.Fs)
        stitched_signal = real_signal.copy()
        frame_idcs = []
        window_size = []
        for hole in self.params.inpainting_indices:
            frame_idcs.append(range(hole[0], hole[1]))
            win_size = int((hole[1] - hole[0] + 1) / 2)
            window_size.append(win_size - (1 - win_size % 2))
        stitched_signal = stitch_signals(stitched_signal, reconstructed_signal.squeeze().cpu().numpy(),
                                         frame_idcs, window_size=window_size)
        write_signal(os.path.join(self.params.output_folder, 'GeneratedSignals', 'inpainted'), stitched_signal,
                     self.params.Fs)

    def extend(self, condition:dict, filt_file=None):
        conditioned_signal = self.condition(condition, False)
        stitched_signal = time_freq_stitch_by_fft(condition['condition_signal'].squeeze().cpu().numpy(),
                                                  conditioned_signal.squeeze().cpu().numpy(),
                                                  condition['condition_fs'],
                                                  self.params.Fs, filt_file)
        output_file = os.path.join(self.output_folder, 'GeneratedSignals',
                                   condition['name'] + '_extended')
        write_signal(output_file, stitched_signal, self.params.Fs)
        return stitched_signal

    def condition(self, condition:dict, write:bool=True):
        condition["condition_scale_idx"] = np.where(np.array(self.params.fs_list) <= condition["condition_fs"])[0][
                                               -1] + 1
        condition["condition_signal"] = torch.Tensor(condition["condition_signal"]).expand(1, 1, -1).to(
            self.params.device)
        lengths = [int(condition["condition_signal"].shape[2] / condition["condition_fs"] * fs) for fs in
                   self.params.fs_list]
        conditioned_signal = draw_signal(self.params, self.generators_list, lengths,
                                         self.params.fs_list, self.noise_amp_list, condition=condition)
        if write:
            output_file = os.path.join(self.output_folder, 'GeneratedSignals',
                                       'conditioned_on_' + condition['name'])
            write_signal(output_file, conditioned_signal, self.params.Fs)
        else:
            return conditioned_signal

    def infinite(self, window_length:int=30, generate_mode:str='local'):
        n_signals:int=1
        sleep_time:int=5
        generate_all_scales:bool=True
        hop_ratio:float=0.5

        output_signals_list = draw_signal(self.params, self.generators_list,
                                            [round(f * window_length) for f in self.params.fs_list], self.params.fs_list,
                                            self.noise_amp_list, output_all_scales=generate_all_scales)
        accumulate = output_signals_list[-1]

        write_signal('generate.wav',
                accumulate, 
                self.params.fs_list[-1], 
                overwrite=True)

        sleep(10)
        if generate_mode == 'local':
            n:int=0
        elif generate_mode == 'web':
            print('run the following to connect to youtube \n>ffmpeg -re -stream_loop -1 -i logo.mp4 -f concat -i playlist1.txt -c:a aac -ab 128k -strict experimental  -movflags +faststart  -f flv rtmp://a.rtmp.youtube.com/live2/xxxxxxxxxx ')

        while True:

            output_signals_list = draw_signal2(self.params, self.generators_list,
                                            [round(f * window_length) for f in self.params.fs_list], self.params.fs_list,
                                            self.noise_amp_list, output_all_scales=generate_all_scales,
                                            earlier_signals_list = output_signals_list, hop_ratio = hop_ratio)
            new_window = output_signals_list[-1]
            new_window = new_window[round(len(new_window)*hop_ratio):]
            if generate_mode == 'local':
                fname = f'infinite_generate{n}.wav'
                n += 1
            elif generate_mode == 'web':
                fname == 'infinite_generate.wav'
            output_file = os.path.join(self.output_folder, fname)
            write_signal(output_file,
                new_window, 
                self.params.fs_list[-1], 
                overwrite=True)
            print('wrote', output_file)
            sleep(sleep_time)
