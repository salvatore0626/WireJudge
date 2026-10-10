"""Small asynchronous sound player using the operating system's audio tools."""
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import time
import tempfile
import wave
import numpy as np


class SoundEffects:
    def __init__(self,options=None):
        self.options=options or (lambda:(True,1.))
        self.cache=None;self.scaled={}
        self.directory=Path(__file__).resolve().parent/'assets'/'sounds'
        self.jobs=queue.Queue();self.generation=0;self.closed=False
        self.processes=[];self.windows_playing=False
        self.worker=threading.Thread(target=self.run,daemon=True,name='WireJudgeSound')
        self.worker.start()

    def play(self,name):
        enabled,volume=self.options()
        if not self.closed and enabled and volume>0:
            self.jobs.put((name,self.generation,time.monotonic(),float(volume)))

    def stop(self):
        if not self.closed:
            self.generation+=1;self.jobs.put(('stop',self.generation,0,0))

    def close(self):
        if not self.closed:
            self.closed=True;self.generation+=1;self.jobs.put((None,self.generation,0,0))

    def stop_audio(self):
        if self.windows_playing:
            import winsound
            winsound.PlaySound(None,0);self.windows_playing=False
        for process in self.processes:
            if process.poll() is None:
                try:
                    process.terminate();process.wait(timeout=.2)
                except subprocess.TimeoutExpired:
                    process.kill();process.wait()
                except OSError:pass
        self.processes=[]

    def sound_path(self,name,volume):
        source=self.directory/(name+'.wav')
        if not source.is_file():return None
        gain=max(0,min(100,round(volume*100)))
        if gain==100:return source
        key=(name,gain)
        if key not in self.scaled:
            if self.cache is None:self.cache=tempfile.TemporaryDirectory(prefix='wire_judge_audio_')
            target=Path(self.cache.name)/(name+f'_{gain}.wav')
            with wave.open(str(source),'rb') as audio:
                params=audio.getparams()
                if params.sampwidth!=2:return source
                samples=np.frombuffer(audio.readframes(params.nframes),dtype='<i2')
            scaled=np.rint(samples.astype(float)*gain/100).astype('<i2')
            with wave.open(str(target),'wb') as audio:
                audio.setparams(params);audio.writeframes(scaled.tobytes())
            self.scaled[key]=target
        return self.scaled[key]

    def run(self):
        while True:
            name,generation,requested,volume=self.jobs.get()
            try:
                if name is None:
                    self.stop_audio()
                    if self.cache is not None:self.cache.cleanup()
                    return
                if name=='stop':
                    self.stop_audio();continue
                # Never catch up by playing a backlog of laser bursts.
                if generation!=self.generation or time.monotonic()-requested>.3:continue
                path=self.sound_path(name,volume)
                if path is None:continue
                if sys.platform=='win32':
                    import winsound
                    winsound.PlaySound(str(path),winsound.SND_FILENAME|winsound.SND_ASYNC|winsound.SND_NODEFAULT)
                    self.windows_playing=True
                else:
                    player='/usr/bin/afplay' if sys.platform=='darwin' else shutil.which('paplay') or shutil.which('aplay')
                    if not player:continue
                    self.processes=[process for process in self.processes if process.poll() is None]
                    self.processes.append(subprocess.Popen([player,str(path)],stdin=subprocess.DEVNULL,
                                                          stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL))
            except (OSError,RuntimeError,ImportError,ValueError,wave.Error):
                # A missing sound device must not interrupt replay or animation.
                if name is None:return
