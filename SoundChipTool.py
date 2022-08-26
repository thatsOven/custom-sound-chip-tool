import pygame, numpy, os
from sys       import argv
from scipy     import signal
from mido      import MidiFile
from bitarray  import bitarray
from importlib import import_module
from time      import sleep, time

RESOLUTION = (1280, 720)

CHANNELS          = 16
NOTES_PER_CHANNEL = 16
MIN_NOTE_TIME     = 75
EXPORT            = False

PX_OFFSET_PERCENT     = 10
PRECISION             = 1
FREQUENCY_SAMPLE      = 30000
AMP                   = 500
NOTE_DURATION         = 1
CHANNEL_ENC_BITS      = 8
NOTES_ENC_BITS        = 8

BITS                  = 16
SAWTOOTH_AMP_BITS     = 4
SQUARE_AMP_BITS       = 4
SAWTOOTH_WIDTH_BITS   = 4
SQUARE_PWM_WIDTH_BITS = 4
SOUND_FREQ_BITS       = 13

BG = (  0,   0,   0)
FG = (255, 255, 255)
DV = (  0, 255,   0)

AMP_BITS           = BITS - SOUND_FREQ_BITS
MAX_SAWTOOTH_AMP   = 2 ** SAWTOOTH_AMP_BITS - 1
MAX_SQUARE_AMP     = 2 ** SQUARE_AMP_BITS - 1
SAWTOOTH_WIDTH_DEN = 2 ** SAWTOOTH_WIDTH_BITS - 1
SQUARE_PWM_DEN     = 2 ** SQUARE_PWM_WIDTH_BITS - 1
MAX_AMP            = 2 ** AMP_BITS - 1

SONG_CODE = """fla 0
lib song
loz songlen

:loop
add
snx

ina
ina
ina
add
lax
wtx

ina

dcz
jz end

jmp loop

:end
hlt

:songlen
"""

def translate(value, min_, max_, minResult, maxResult):
    deltaOrig = max_      - min_
    deltaOut  = maxResult - minResult

    scaled = float(value - min_) / float(deltaOrig)

    return int(minResult + (scaled * deltaOut))

def decimalToBinary(n, bits):
    return bin(n)[2:].zfill(bits)

class Instrument:
    def __init__(self, sawtoothWidth = 0, sawtoothAmp = 0, squarePWM = 0, squareAmp = 15):
        if (
            sawtoothWidth < 0 or sawtoothWidth > 15 or
              sawtoothAmp < 0 or   sawtoothAmp > 15 or
                squarePWM < 0 or     squarePWM > 15 or
                squareAmp < 0 or     squareAmp > 15
        ):
            print("Invalid instrument. Using default")

            self.squareAmp     = 15
            self.squarePWM     = 0
            self.sawtoothAmp   = 0
            self.sawtoothWidth = 0
        else:
            self.squareAmp     = squareAmp
            self.squarePWM     = squarePWM
            self.sawtoothAmp   = sawtoothAmp
            self.sawtoothWidth = sawtoothWidth

    def __int__(self):
        return (
            self.sawtoothWidth * 0x1000 +
            self.sawtoothAmp   * 0x100  +
            self.squarePWM     * 0x10   +
            self.squareAmp
        )

    def fromInt(self, number):
        tmp = number // 0x1000
        self.sawtoothWidth = tmp
        number -= tmp * 0x1000

        tmp = number // 0x100
        self.sawtoothAmp = tmp
        number -= tmp * 0x100

        tmp = number // 0x10
        self.squarePWM = tmp
        number -= tmp * 0x10

        self.squareAmp = number

        return self

class Note:
    def __init__(self, value, pos, channel):
        self.value   = value
        self.pos     = pos
        self.channel = channel

class Event:
    def __init__(self, type, note, channel, velocity, sleep):
        self.type     = type
        self.note     = note
        self.channel  = channel
        self.velocity = velocity
        self.time     = sleep

    def __repr__(self):
        return "[" + str(self.channel) + "] " + self.type + " " + str(self.note) + " vel: " + str(self.velocity) + " sleep: " + str(self.time)

class Sound:
    def __init__(self, freqAmp, mix, sleep):
        self.freqAmp  = freqAmp
        self.mix      = mix
        self.duration = sleep
        self.sleep    = sleep

class Channel:
    BASE = numpy.zeros(FREQUENCY_SAMPLE, dtype = numpy.int16)

    def __init__(self, id_, ch):
        self.channel = pygame.mixer.Channel(id_)
        self.waveform = Channel.BASE
        self.pos = ((id_ - (ch * NOTES_PER_CHANNEL)) * CHANNEL_SIZE[0], ch * CHANNEL_SIZE[1])

    def play(self, wave):
        wave = wave.astype(numpy.int16)
        self.channel.play(pygame.sndarray.make_sound(wave), -1)

        self.waveform = wave[0:FREQUENCY_SAMPLE:PRECISION]

    def stop(self):
        self.waveform = Channel.BASE
        self.channel.stop()

    def draw(self, surface : pygame.Surface):
        pointsSurf = pygame.Surface(CHANNEL_SIZE)

        pygame.draw.lines(
            pointsSurf, 
            FG, False, 
            tuple((i, 
                int(translate(self.waveform[i], -AMP, AMP, CHANNEL_PX_OFFSET, CHANNEL_SIZE[1] - CHANNEL_PX_OFFSET))) 
                for i in range(min(len(self.waveform), CHANNEL_SIZE[0]))
            )
        )
        
        pygame.draw.rect(pointsSurf, DV, (0, 0) + CHANNEL_SIZE, 1)
        surface.blit(pointsSurf, self.pos)

class SoundChipTool:
    def __init__(self):
        self.playing     = []
        self.channels    = None
        self.instruments = [Instrument() for _ in range(CHANNELS)]

    def parseInstruments(self, fileName):
        with open(fileName, "r") as txt:
            self.instruments = eval("[" + txt.read() + "]")

    @classmethod
    def getFreq(self, note):
        return int(440 * 2 ** ((note - 69) / 12))

    def channelFilter(self, channel):
        return channel

    def readMidi(self, fileName):
        mid = MidiFile(fileName)

        events = []

        for message in mid:
            if message.type in ("note_on", "note_off"):
                events.append(Event(
                    message.type,
                    message.note,
                    self.channelFilter(message.channel),
                    int(translate(message.velocity, 0, 127, 0, MAX_AMP)), 
                    message.time
                ))
            elif message.type == "end_of_track":
                events.append(Event("", 0, 0, 0, message.time))
                break
            elif len(events) != 0:
                events[-1].time += message.time

        for i in range(len(events) - 1):
            events[i].time = events[i + 1].time
        events.pop(-1)

        return events

    def getFreeNote(self, channel):
        for i in range(len(self.channels[channel])):
            if not self.channels[channel][i].channel.get_busy():
                return i
        return 0

    def search(self, note, channel):
        for i in range(len(self.playing)):
            if self.playing[i].value == note and self.playing[i].channel == channel:
                return i

    def getMixedWave(self, baseArray, channel):
        instrument = self.instruments[channel]

        if instrument.squarePWM == 0:
            return (((  instrument.squareAmp /   MAX_SQUARE_AMP) * signal.square(baseArray)) +
                    ((instrument.sawtoothAmp / MAX_SAWTOOTH_AMP) * signal.sawtooth(baseArray, instrument.sawtoothWidth / SAWTOOTH_WIDTH_DEN)))
        else:
            return (((  instrument.squareAmp /   MAX_SQUARE_AMP) * signal.square(baseArray, signal.sawtooth(baseArray, instrument.squarePWM / SQUARE_PWM_DEN))) +
                    ((instrument.sawtoothAmp / MAX_SAWTOOTH_AMP) * signal.sawtooth(baseArray, instrument.sawtoothWidth / SAWTOOTH_WIDTH_DEN)))

    def __writeEvent(self, event):
        res  = decimalToBinary(            event.note, 7)
        res += decimalToBinary(         event.channel, 8)
        res += decimalToBinary(        event.velocity, AMP_BITS)
        res += decimalToBinary(int(event.time * 1000), BITS)

        return res

    def export(self, events):
        data = decimalToBinary(CHANNELS, CHANNEL_ENC_BITS) + decimalToBinary(NOTES_PER_CHANNEL, NOTES_ENC_BITS)

        for i in range(CHANNELS):
            data += decimalToBinary(int(self.instruments[i]), 16)

        for i in range(len(events) - 1):
            if events[i].type == "note_on":
                data += "00"
            else:
                data += "01"

            data += self.__writeEvent(events[i])

        if events[-1].type == "note_on":
            data += "10"
        else:
            data += "11"

        data += self.__writeEvent(events[-1])

        return bitarray(data)

    def load(self, data : bitarray):
        global CHANNELS, NOTES_PER_CHANNEL

        data = data.to01()

        CHANNELS = int(data[:8], 2)
        NOTES_PER_CHANNEL = int(data[8:16], 2)

        self.instruments = []

        ptr = 16
        for _ in range(CHANNELS):
            self.instruments.append(Instrument().fromInt(int(data[ptr:ptr + 16], 2)))
            ptr += 16

        events = []
        while ptr < len(data):
            end = data[ptr]
            ptr += 1
            onOff = data[ptr]
            ptr += 1

            note = int(data[ptr:ptr + 7], 2)
            ptr += 7

            channel = int(data[ptr:ptr + 8], 2)
            ptr += 8

            velocity = int(data[ptr:ptr + AMP_BITS], 2)
            ptr += AMP_BITS

            eTime = int(data[ptr:ptr + BITS], 2) / 1000
            ptr += BITS

            events.append(Event(
                "note_on" if onOff == "0" else "note_off",
                note, channel, velocity, eTime
            ))

            if end == "1": break

        return events

    def oscilloscopeView(self, fileName):
        global PRECISION, CHANNEL_SIZE, CHANNEL_PX_OFFSET

        pygame.mixer.init(FREQUENCY_SAMPLE, -16, 1)
        pygame.init()
        surface = pygame.display.set_mode(RESOLUTION)
        pygame.display.set_caption("Custom sound chip tool - Oscilloscope view")

        if fileName.split(".")[-1] == "mid":
            events = self.readMidi(fileName)

            if EXPORT:
                with open(f"{fileName.split('.')[0]}.scts", "wb") as file:
                    self.export(events).tofile(file)
        else:
            with open(fileName, "rb") as file:
                data = bitarray()
                data.fromfile(file)
                events = self.load(data)

        PRECISION *= NOTES_PER_CHANNEL
        CHANNEL_SIZE       = (RESOLUTION[0] // NOTES_PER_CHANNEL, RESOLUTION[1] // CHANNELS)
        CHANNEL_PX_OFFSET  = CHANNEL_SIZE[1] // PX_OFFSET_PERCENT

        pygame.mixer.set_num_channels(CHANNELS * NOTES_PER_CHANNEL)

        self.playing = []

        self.channels = [
            [Channel(NOTES_PER_CHANNEL * j + i, j) 
            for i in range(NOTES_PER_CHANNEL)] 
            for j in range(CHANNELS)
        ]

        sample = numpy.arange(0, NOTE_DURATION, 1 / FREQUENCY_SAMPLE)

        updates = []
        for event in events:
            sTime = time()

            if event.type == "note_on":
                channel = self.getFreeNote(event.channel)
                self.playing.append(Note(event.note, channel, event.channel))

                self.channels[event.channel][channel].play(
                    translate(event.velocity, 0, MAX_AMP, 0, AMP) *
                    self.getMixedWave(
                        2 * numpy.pi * sample * self.getFreq(event.note),
                        event.channel
                    )
                )

                updates.append((event.channel, channel))
            else:
                note = self.playing.pop(self.search(event.note, event.channel))

                self.channels[note.channel][note.pos].stop()

                updates.append((note.channel, note.pos))

            if event.time == 0: continue

            while len(updates) > 0:
                self.channels[updates[-1][0]][updates[-1][1]].draw(surface)
                updates.pop()

            pygame.display.update()
            pygame.event.get()

            sTime = event.time - (time() - sTime)

            if sTime > 0:
                sleep(sTime)

    def addTime(self, song, time):
        for note in self.playing:
            song[note.pos].duration += time

    def convert(self, fileName):
        self.playing = []
        song = []

        for event in self.readMidi(fileName):
            print(event)

            if event.type == "note_on":
                self.addTime(song, event.time)

                self.playing.append(Note(event.note, len(song), event.channel))

                song.append(Sound(
                    (event.velocity << SOUND_FREQ_BITS) + 
                    self.getFreq(event.note),
                    int(self.instruments[event.channel]), event.time
                ))
            else:
                self.playing.pop(self.search(event.note, event.channel))

                if event.time != 0 and len(song) != 0:
                    self.addTime(song, event.time)
                    song[-1].sleep += event.time

        for i in range(len(song)):
            if song[i].duration < MIN_NOTE_TIME:
                song[i].duration = MIN_NOTE_TIME

            song[i].duration = int(song[i].duration * 1000)
            song[i].sleep    = int(song[i].sleep    * 1000)

        print("Writing to file...")
        with open(f"{fileName.split('.', maxsplit = 1)[0]}.ocpu", "w") as out:
            out.write(SONG_CODE)
            out.write(str(len(song)) + "\n:song\n")

            for sound in song:
                out.write(str(sound.freqAmp)  + "\n")
                out.write(str(sound.mix)      + "\n")
                out.write(str(sound.duration) + "\n")
                out.write(str(sound.sleep)    + "\n")
                
def getIntArg(name, shName):
    if name in argv:
        idx = argv.index(name)
        argv.pop(idx)
        value = argv.pop(idx)

        try:
            value = int(value)
        except ValueError:
            print(f"Invalid {shName} value given. Using default.")
        else:
            return value

if __name__ == "__main__":
    if len(argv) == 1:
        print("Custom sound chip tool - thatsOven")
    else:   
        tmp = getIntArg("--channels", "channel")
        if tmp is not None:
            CHANNELS = tmp

        tmp = getIntArg("--notes", "notes per channel")
        if tmp is not None:
            NOTES_PER_CHANNEL = tmp

        tmp = getIntArg("--min-note-time", "minimum note time")
        if tmp is not None:
            MIN_NOTE_TIME = tmp

        if "--export" in argv:
            argv.remove("--export")
            EXPORT = True

        tool = SoundChipTool()

        if "--instruments" in argv:
            idx = argv.index("--instruments")
            argv.pop(idx)
            tool.parseInstruments(argv.pop(idx))

        if "--filter" in argv:
            idx = argv.index("--filter")
            argv.pop(idx)
            file = argv.pop(idx)

            module = import_module(file.replace(".py", "").replace(os.sep, "."))

            try:
                tmp = module.channelFilter
            except NameError:
                print("Invalid filter code. Using default.")
            else:
                tool.channelFilter = module.channelFilter

            del module

        if "--resolution" in argv:
            idx = argv.index("--resolution")
            argv.pop(idx)

            res = argv.pop(idx).lower().split("x")

            if len(res) != 2:
                print("Invalid resolution value given. Using default.")
            else:
                try:
                    tmp = (int(res[0]), int(res[1]))
                except ValueError:
                    print("Invalid resolution value given. Using default.")
                else:
                    RESOLUTION = tmp

        MIN_NOTE_TIME /= 1000

        if argv[1] == "visualize":
            tool.oscilloscopeView(argv[2])
        elif argv[1] == "convert":
            tool.convert(argv[2])
        else:
            print("unknown command")
       