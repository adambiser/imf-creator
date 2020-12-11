# IMF Creator

**This project is still a work-in-progress.**

A program to create IMF music used by several classic ID and Apogee games such as Wolfenstein 3D and Commander Keen.

## Getting Started

### Prerequisites

You need Python 3.6 or higher to run this.

### Installing

Clone or download this repository.

#### Windows
While running the command prompt as system administrator:

    pip install watchdog

##### PyAudio
	
PyAudio also needs to be installed and if you have Python 3.6, you can use

    pip install PyAudio

However, for Python 3.7 or later use the wheel for your version from here:
https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio

Example:

    pip install PyAudio-0.2.11-cp37-cp37m-win32.whl.whl

For convenience, compiled versions can also be found in the base folder of this project.

#### Linux
On Linux you will need to install some dependencies to run this.

##### Ubuntu / Debian
```bash
sudo apt install tix-dev python3-tk python3-pyaudio python3-watchdog
```

## License

This project is dual licensed under the MIT License and GPL 3 License - see the [LICENSE](LICENSE) file for details.

## Acknowledgements
* Adam Nielsen (Malvineous) for his [PyOPL](https://github.com/Malvineous/pyopl) library.
* [FreeDoom](https://github.com/freedoom/freedoom) for its GENMIDI.OP2 file.
* [Kenney.nl](https://opengameart.org/content/game-icons) for the button icons. (CC0 License)
