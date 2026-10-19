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


class WindowsVoice:
    """Independent waveOut voice; retains PCM buffers until the device is done."""
    def __init__(self,path):
        import ctypes as c
        from ctypes import wintypes as w
        class Format(c.Structure):
            _fields_=[('tag',w.WORD),('channels',w.WORD),('rate',w.DWORD),('bytes_per_second',w.DWORD),('align',w.WORD),('bits',w.WORD),('extra',w.WORD)]
        class Header(c.Structure):
            _fields_=[('data',c.c_void_p),('length',w.DWORD),('recorded',w.DWORD),('user',c.c_size_t),('flags',w.DWORD),('loops',w.DWORD),('next',c.c_void_p),('reserved',c.c_size_t)]
        self.c=c;self.api=c.WinDLL('winmm');self.handle=c.c_void_p();self.opened=False;self.prepared=False
        self.api.waveOutOpen.argtypes=[c.POINTER(c.c_void_p),w.UINT,c.POINTER(Format),c.c_size_t,c.c_size_t,w.DWORD]
        self.api.waveOutPrepareHeader.argtypes=[c.c_void_p,c.POINTER(Header),w.UINT]
        self.api.waveOutWrite.argtypes=[c.c_void_p,c.POINTER(Header),w.UINT]
        self.api.waveOutUnprepareHeader.argtypes=[c.c_void_p,c.POINTER(Header),w.UINT]
        self.api.waveOutReset.argtypes=[c.c_void_p];self.api.waveOutClose.argtypes=[c.c_void_p]
        with wave.open(str(path),'rb') as audio:
            channels=audio.getnchannels();rate=audio.getframerate();size=audio.getsampwidth();pcm=audio.readframes(audio.getnframes())
        self.buffer=c.create_string_buffer(pcm);self.header=Header(c.cast(self.buffer,c.c_void_p),len(pcm),0,0,0,0,None,0)
        fmt=Format(1,channels,rate,rate*channels*size,channels*size,size*8,0)
        try:
            if self.api.waveOutOpen(c.byref(self.handle),0xffffffff,c.byref(fmt),0,0,0):raise OSError('Cannot open audio device')
            self.opened=True
            if self.api.waveOutPrepareHeader(self.handle,c.byref(self.header),c.sizeof(self.header)):raise OSError('Cannot prepare audio')
            self.prepared=True
            if self.api.waveOutWrite(self.handle,c.byref(self.header),c.sizeof(self.header)):raise OSError('Cannot play audio')
        except Exception:
            self.close();raise

    def poll(self):return 0 if self.header.flags&1 else None
    def close(self):
        if not self.opened:return
        self.api.waveOutReset(self.handle)
        if self.prepared:self.api.waveOutUnprepareHeader(self.handle,self.c.byref(self.header),self.c.sizeof(self.header))
        self.api.waveOutClose(self.handle);self.opened=False


class SoundEffects:
    def __init__(self,options=None,polyphonic=False,max_voices=16,directory=None):
        self.options=options or (lambda:(True,1.))
        self.polyphonic=polyphonic;self.max_voices=max_voices;self.voices=[]
        self.cache=None;self.scaled={}
        self.directory=Path(directory) if directory is not None else Path(__file__).resolve().parent.parent/'assets'/'sounds'
        self.jobs=queue.Queue();self.generation=0;self.closed=False
        self.processes=[];self.windows_playing=False
        self.worker=threading.Thread(target=self.run,daemon=True,name='WireJudgeSound')
        self.worker.start()

    def play(self,name,gain=1.):
        enabled,volume=self.options()
        volume=max(0.,min(1.,volume*gain))
        if not self.closed and enabled and volume>0:
            self.jobs.put((name,self.generation,time.monotonic(),float(volume)))

    def stop(self):
        if not self.closed:
            self.generation+=1;self.jobs.put(('stop',self.generation,0,0))

    def close(self):
        if not self.closed:
            self.closed=True;self.generation+=1;self.jobs.put((None,self.generation,0,0))

    def reap_voices(self):
        active=[]
        for voice in self.voices:
            if voice.poll() is None:active.append(voice)
            else:voice.close()
        self.voices=active

    def stop_audio(self):
        for voice in self.voices:voice.close()
        self.voices=[]
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
        gain=max(0,min(1000,round(volume*1000)))
        if gain>50:gain=round(gain/10)*10
        if gain==1000:return source
        key=(name,gain)
        if key not in self.scaled:
            if self.cache is None:self.cache=tempfile.TemporaryDirectory(prefix='wire_judge_audio_')
            target=Path(self.cache.name)/(name+f'_{gain}.wav')
            with wave.open(str(source),'rb') as audio:
                params=audio.getparams()
                if params.sampwidth!=2:return source
                samples=np.frombuffer(audio.readframes(params.nframes),dtype='<i2')
            scaled=np.rint(samples.astype(float)*gain/1000).astype('<i2')
            with wave.open(str(target),'wb') as audio:
                audio.setparams(params);audio.writeframes(scaled.tobytes())
            self.scaled[key]=target
        return self.scaled[key]

    def run(self):
        while True:
            try:name,generation,requested,volume=self.jobs.get(timeout=.05)
            except queue.Empty:
                self.reap_voices();continue
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
                if sys.platform=='win32' and self.polyphonic:
                    self.reap_voices()
                    if len(self.voices)>=self.max_voices:continue
                    self.voices.append(WindowsVoice(path))
                elif sys.platform=='win32':
                    import winsound
                    winsound.PlaySound(str(path),winsound.SND_FILENAME|winsound.SND_ASYNC|winsound.SND_NODEFAULT)
                    self.windows_playing=True
                else:
                    player='/usr/bin/afplay' if sys.platform=='darwin' else shutil.which('paplay') or shutil.which('aplay')
                    if not player:continue
                    self.processes=[process for process in self.processes if process.poll() is None]
                    if len(self.processes)>=self.max_voices:continue
                    self.processes.append(subprocess.Popen([player,str(path)],stdin=subprocess.DEVNULL,
                                                          stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL))
            except (OSError,RuntimeError,ImportError,ValueError,wave.Error):
                # A missing sound device must not interrupt replay or animation.
                if name is None:return
