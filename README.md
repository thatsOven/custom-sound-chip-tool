# Custom sound chip tool
A tool used to emulate my [custom computer](https://github.com/thatsOven/custom-emulated-computer)'s sound chip, and convert midi files to code for the computer to run.
# Commands
- `visualize`
	- Shows an oscilloscope view of the sound chip's channels while playing the given midi or scts file.
	- **Usage**: visualize [file name]
- `convert`
	- Converts midi or scts files to runnable code for the [custom computer](https://github.com/thatsOven/custom-emulated-computer) that plays the song.
	- **Usage**: convert [file name]
# Command line arguments
- `--channels`
	- Sets the number of channels (or instruments) that will be emulated and visualized. Default is 16. Make sure to use the correct amount of channels for the midi you're playing to avoid exceptions. This argument is only effective when using the program in visualization mode or when using the `--export` argument.
	- **Usage**: --channels [number of channels]
- `--notes`
	- Sets the number of notes that can play on the same channel at the same time. Default is 16. This argument is only effective when using the program in visualization mode or when using the `--export` argument.
	- **Usage**: --notes [number of notes]
- `--min-note-time`
	- Sets the minimum duration (in milliseconds) of a note. Default is 75. This argument is only effective when using the program in conversion mode.
	- **Usage** --min-note-time [duration]
- `--mixer-words`
	- Sets the amount of words dedicated to each mixer code. Default is 1.
	- Usage: --mixer-words [word count]
- `--instruments` 
	- Reads an [instrument set file](https://github.com/thatsOven/custom-sound-chip-tool#instrument-set-file) and assigns each instrument to the corresponding channel index. By default, the instrument set will be square waves for every channel.
	- **Usage**: --instruments [file name]
- `--extract-instruments`
	- Creates an [instrument set file](https://github.com/thatsOven/custom-sound-chip-tool#instrument-set-file) based on the current instruments that the sound chip is using. Useful for extracting the instrument set of a scts file.
	- **Usage**: --extract-instruments [output file name]
- `--detect-channels`
	- Automatically sets the number of channels based on the length of the given instrument set (it's not effective if no instruments are given). This argument is only effective when using the program in visualization mode or when using the `--export` argument.
	- **Usage**: --detect-channels
- `--filter`
	- Sets a channel index filter, useful when a midi file has empty channels in between used ones, or when the first channels are empty. Expects a `.py` file containing a `channelFilter` function that takes exactly one argument (the channel) and returns an integer.
	- **Usage**: --filter [file name]
- `--export`
	- Generates a Sound Chip Tool Song ("scts") file containing all parameters given when playing a song in visualization mode. Useful to avoid writing the same parameters every time a song gets played.
	- **Usage**: --export
- `--resolution`
	- Sets the window resolution. Default is 1280x720. This argument is only effective when using the program in visualization mode.
	- **Usage**: --resolution [width]x[height]
# Instruments
An instrument is composed as explained in the [Sound code section](https://github.com/thatsOven/custom-emulated-computer#sound-code) of my custom computer project.
To create an instrument in this program, you can create an instance of the `Instrument` class, and pass it the corresponding arguments.
## Instrument set file
An instrument set file is a list of instruments, each assigned to the corresponding midi channel index. For example:
```
Instrument(0, 0, 0, 15),
Instrument(0, 15, 0, 0)
```
is a valid instrument set.
